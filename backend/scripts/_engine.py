"""Shared async engine factory for standalone seed scripts.

asyncpg does not parse 'sslmode' from the connection URL; leaving it in
causes a ConnectionResetError during TLS handshake on Fly.io (and other
managed Postgres hosts).  This helper strips sslmode and maps it to the
correct asyncpg connect_args ssl value.
"""
import os
import re
import ssl as _ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _resolve(raw: str) -> tuple[str, dict]:
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


def make_session_factory(database_url: str | None = None):
    raw = database_url or os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://utms:utms@localhost:5432/utms"
    )
    url, connect_args = _resolve(raw)
    engine = create_async_engine(url, echo=False, connect_args=connect_args)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
