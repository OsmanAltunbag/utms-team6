"""
Shared pytest fixtures for UTMS test suite.

RSA key pair is generated once per session so all auth tests use the same
keys without hitting the filesystem or environment.
"""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.base import Base
from app.domain.enums import UserRole
from app.domain.user import User


# ---------------------------------------------------------------------------
# RSA key pair — generated once for the whole test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def rsa_keys():
    """Generate a throwaway RSA-2048 key pair for JWT signing in tests."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture(autouse=True)
def patch_jwt_keys(rsa_keys, monkeypatch):
    """Patch settings so every test uses the session-scoped test RSA keys."""
    private_pem, public_pem = rsa_keys
    monkeypatch.setattr("app.core.config.settings.JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setattr("app.core.config.settings.JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setattr("app.core.config.settings.JWT_ALGORITHM", "RS256")
    # Also patch the security module's key accessors
    monkeypatch.setattr("app.core.security._private_key", lambda: private_pem)
    monkeypatch.setattr("app.core.security._public_key", lambda: public_pem)


# ---------------------------------------------------------------------------
# Mock Redis — no real Redis needed in unit/integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis_store():
    """In-memory dict that simulates the Redis JTI store."""
    return {}


@pytest.fixture
def patch_redis(mock_redis_store):
    """Patch all three redis helpers used by AuthService and dependencies."""

    async def _store(jti, ttl_seconds):
        mock_redis_store[jti] = True

    async def _revoke(jti):
        mock_redis_store.pop(jti, None)

    async def _is_valid(jti):
        return mock_redis_store.get(jti, False)

    with (
        patch("app.services.auth_service.store_jti", side_effect=_store),
        patch("app.services.auth_service.revoke_jti", side_effect=_revoke),
        patch("app.services.auth_service.is_jti_valid", side_effect=_is_valid),
        patch("app.core.dependencies.is_jti_valid", side_effect=_is_valid),
    ):
        yield mock_redis_store


# ---------------------------------------------------------------------------
# Sample user factories
# ---------------------------------------------------------------------------

def make_user(
    role: UserRole = UserRole.APPLICANT,
    failed_attempts: int = 0,
    locked_until=None,
    is_active: bool = True,
    password_hash: str = "$2b$12$placeholder",
) -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = f"{role.value.lower()}@test.com"
    u.password_hash = password_hash
    u.role = role
    u.first_name = "Test"
    u.last_name = "User"
    u.is_active = is_active
    u.is_verified = True
    u.failed_attempts = failed_attempts
    u.locked_until = locked_until
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


# ---------------------------------------------------------------------------
# FastAPI test client (integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(patch_redis) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient wired to the FastAPI app.
    DB dependency is overridden with a mock async session so no real
    PostgreSQL is needed for the integration tests in this spec.
    """
    from app.core.database import get_db
    from app.main import app

    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
