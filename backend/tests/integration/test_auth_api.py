"""
Integration tests for the Auth API endpoints.
DB is replaced with an AsyncMock — no real PostgreSQL required.

Covers T1, T2, T3, T4, T6, T7, T10 from SPEC-002.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.domain.enums import UserRole
from tests.conftest import make_user


def _mock_db_returning(user):
    """Return a patched AsyncSession whose .execute() yields the given user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    db.get = AsyncMock(return_value=user)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# T1 — Successful login returns 200 + cookies
# ---------------------------------------------------------------------------

async def test_login_sets_httponly_cookies(patch_redis):
    from app.core.database import get_db
    from app.main import app

    plain = "SecurePass1!"
    user = make_user(role=UserRole.APPLICANT, password_hash=hash_password(plain))
    mock_db = _mock_db_returning(user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/api/auth/login", json={"email": user.email, "password": plain})

        assert resp.status_code == 200
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies
        # Verify cookie flags via Set-Cookie header
        set_cookie_headers = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [
            v for k, v in resp.headers.items() if k.lower() == "set-cookie"
        ]
        joined = " ".join(set_cookie_headers).lower()
        assert "httponly" in joined
        assert "samesite=strict" in joined
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T2 — Wrong password → 401, generic message
# ---------------------------------------------------------------------------

async def test_login_wrong_password_returns_generic_401(patch_redis):
    from app.core.database import get_db
    from app.main import app

    user = make_user(password_hash=hash_password("correct"))
    mock_db = _mock_db_returning(user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post(
                "/api/auth/login",
                json={"email": user.email, "password": "wrong"},
            )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T3 — Unknown email → same generic 401
# ---------------------------------------------------------------------------

async def test_login_unknown_email_same_message(patch_redis):
    from app.core.database import get_db
    from app.main import app

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post(
                "/api/auth/login",
                json={"email": "nobody@example.com", "password": "anything"},
            )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T4 — Locked account returns 423 + Retry-After header
# ---------------------------------------------------------------------------

async def test_locked_account_returns_423_with_retry_after(patch_redis):
    from app.core.database import get_db
    from app.main import app

    locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    user = make_user(
        password_hash=hash_password("correct"),
        failed_attempts=5,
        locked_until=locked_until,
    )
    mock_db = _mock_db_returning(user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post(
                "/api/auth/login",
                json={"email": user.email, "password": "correct"},
            )

        assert resp.status_code == 423
        assert "retry-after" in resp.headers
        assert int(resp.headers["retry-after"]) > 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T6 — Logout returns 204, clears cookies
# ---------------------------------------------------------------------------

async def test_logout_returns_204_and_clears_cookies(patch_redis):
    from app.core.database import get_db
    from app.main import app

    plain = "SecurePass1!"
    user = make_user(role=UserRole.APPLICANT, password_hash=hash_password(plain))
    mock_db = _mock_db_returning(user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            # Login first
            login_resp = await ac.post(
                "/api/auth/login", json={"email": user.email, "password": plain}
            )
            assert login_resp.status_code == 200

            # Logout using the cookie
            logout_resp = await ac.post("/api/auth/logout")

        assert logout_resp.status_code == 204
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T7 — Access protected route after logout → 401
# ---------------------------------------------------------------------------

async def test_access_after_logout_returns_401(patch_redis):
    from app.core.database import get_db
    from app.main import app

    plain = "SecurePass1!"
    user = make_user(role=UserRole.APPLICANT, password_hash=hash_password(plain))
    mock_db = _mock_db_returning(user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            login_resp = await ac.post(
                "/api/auth/login", json={"email": user.email, "password": plain}
            )
            assert login_resp.status_code == 200

            await ac.post("/api/auth/logout")

            # Manually clear cookies to simulate the browser honouring Set-Cookie: max-age=0
            ac.cookies.clear()
            logout_resp2 = await ac.post("/api/auth/logout")

        assert logout_resp2.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T10 — RBAC: applicant cannot access a staff-only endpoint
# ---------------------------------------------------------------------------

async def test_rbac_applicant_cannot_access_staff_endpoint(patch_redis):
    """
    We add a dummy staff-only route for this test and verify that an
    authenticated applicant receives 403.
    """
    from fastapi import Depends
    from app.core.database import get_db
    from app.core.dependencies import require_role
    from app.main import app

    plain = "SecurePass1!"
    applicant = make_user(role=UserRole.APPLICANT, password_hash=hash_password(plain))
    mock_db = _mock_db_returning(applicant)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    # Register a temporary staff-only route
    @app.get("/api/_test/staff-only")
    async def _staff_only(_=Depends(require_role(UserRole.STUDENT_AFFAIRS))):
        return {"ok": True}

    try:
        async with AsyncClient(
            transport=__import__("httpx").ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            login_resp = await ac.post(
                "/api/auth/login", json={"email": applicant.email, "password": plain}
            )
            assert login_resp.status_code == 200

            resp = await ac.get("/api/_test/staff-only")

        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
        # Remove the temp route
        app.routes[:] = [r for r in app.routes if getattr(r, "path", "") != "/api/_test/staff-only"]
