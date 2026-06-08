import re
import ssl as _ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _asyncpg_url_and_ssl(raw_url: str) -> tuple[str, dict]:
    """Strip sslmode from URL and map it to asyncpg connect_args ssl.

    asyncpg does not parse 'sslmode' from the connection URL; passing it causes
    a ConnectionResetError during TLS handshake.  We extract the value, strip
    the parameter, then pass an explicit 'ssl' keyword argument instead.
    """
    url = raw_url
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
        ssl_val = True  # encrypt, skip cert verification (matches psycopg2 'require')
    else:
        ssl_val = False  # disable / allow / prefer / unset → no TLS

    return url, {"ssl": ssl_val}


_db_url, _connect_args = _asyncpg_url_and_ssl(settings.DATABASE_URL)

engine = create_async_engine(
    _db_url,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
