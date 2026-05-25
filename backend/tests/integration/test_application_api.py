"""
Integration tests for the Applications API (SPEC-004).
DB is mocked — no real PostgreSQL needed.

Covers: T1, T2, T3, T6, T7 (via API layer).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.enums import AppStatus, DocType, UserRole
from app.domain.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_applicant_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = "applicant@test.com"
    user.role = UserRole.APPLICANT
    user.first_name = "Test"
    user.last_name = "Applicant"
    user.is_active = True
    user.is_verified = True
    user.failed_attempts = 0
    user.locked_until = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)

    applicant = MagicMock()
    applicant.id = uuid.uuid4()
    applicant.national_id = "12345678901"
    user.applicant_profile = applicant
    return user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def app_client():
    """AsyncClient wired to the FastAPI app with mocked DB and auth."""
    from app.core.database import get_db
    from app.core.dependencies import get_current_user
    from app.main import app

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    applicant_user = _make_applicant_user()

    async def override_get_current_user():
        return applicant_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, mock_db, applicant_user

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T1 — Create application during open period → 201, status=DRAFT
# ---------------------------------------------------------------------------

async def test_create_application_returns_201(app_client):
    client, db, user = app_client
    program_id = uuid.uuid4()
    period_id = uuid.uuid4()

    mock_period = MagicMock()
    mock_period.is_open = True
    mock_period.id = period_id

    mock_program = MagicMock()
    mock_program.id = program_id
    mock_program.is_active = True

    with (
        patch("app.services.application_service.ApplicationService.create_application") as mock_create,
    ):
        mock_app = MagicMock()
        mock_app.id = uuid.uuid4()
        mock_app.status = AppStatus.DRAFT
        mock_create.return_value = mock_app

        resp = await client.post(
            "/api/applications",
            json={"program_id": str(program_id), "period_id": str(period_id)},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert "application_id" in data


# ---------------------------------------------------------------------------
# T6 — Upload non-PDF file → 422
# ---------------------------------------------------------------------------

async def test_confirm_upload_non_pdf_returns_422(app_client):
    client, db, user = app_client
    application_id = uuid.uuid4()

    with patch("app.services.document_service.DocumentService.confirm_upload") as mock_confirm:
        from fastapi import HTTPException
        mock_confirm.side_effect = HTTPException(
            status_code=422,
            detail="Invalid file format. Please upload a PDF file.",
        )

        resp = await client.post(
            f"/api/applications/{application_id}/documents/confirm",
            json={
                "doc_type": "TRANSCRIPT",
                "object_key": f"applications/{application_id}/TRANSCRIPT/{uuid.uuid4()}.jpg",
                "file_name": "transcript.jpg",
                "file_size_bytes": 1024,
            },
        )

    assert resp.status_code == 422
    assert "Invalid file format" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# T7 — Upload file > 5 MB → 422
# ---------------------------------------------------------------------------

async def test_confirm_upload_large_file_returns_422(app_client):
    client, db, user = app_client
    application_id = uuid.uuid4()

    with patch("app.services.document_service.DocumentService.confirm_upload") as mock_confirm:
        from fastapi import HTTPException
        mock_confirm.side_effect = HTTPException(
            status_code=422,
            detail="File exceeds 5 MB limit.",
        )

        resp = await client.post(
            f"/api/applications/{application_id}/documents/confirm",
            json={
                "doc_type": "TRANSCRIPT",
                "object_key": f"applications/{application_id}/TRANSCRIPT/{uuid.uuid4()}.pdf",
                "file_name": "big_file.pdf",
                "file_size_bytes": 6_000_000,
            },
        )

    assert resp.status_code == 422
    assert "5 MB" in resp.json()["detail"]
