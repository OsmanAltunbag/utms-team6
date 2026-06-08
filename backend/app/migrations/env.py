import asyncio
import os
import re
import ssl as _ssl
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.domain.base import Base  # noqa: E402
import app.domain  # noqa: E402, F401

target_metadata = Base.metadata


def _resolve_db_url() -> tuple[str, dict]:
    """Return (clean_url, connect_args) for asyncpg.

    Reads DATABASE_URL env var first (Fly secret), falls back to alembic.ini.
    Strips 'sslmode' — asyncpg doesn't parse it from the URL; a
    ConnectionResetError during start_tls is the symptom when it's left in.
    """
    raw = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")

    url = raw
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    m = re.search(r"[?&]sslmode=([^&]+)", url)
    sslmode = m.group(1) if m else None
    url = re.sub(r"([?&])sslmode=[^&]+", lambda mo: "" if mo.group(1) == "?" else mo.group(1), url)
    url = url.rstrip("?&")

    if sslmode in ("verify-ca", "verify-full"):
        ssl_val: bool | _ssl.SSLContext = _ssl.create_default_context()
    elif sslmode == "require":
        ssl_val = True
    else:
        ssl_val = False

    return url, {"ssl": ssl_val}


def run_migrations_offline() -> None:
    url, _ = _resolve_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url, connect_args = _resolve_db_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
