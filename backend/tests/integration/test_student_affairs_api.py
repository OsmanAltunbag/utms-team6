"""
Integration tests for the Student Affairs API (SPEC-006).
"""

import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.enums import AppStatus, UserRole
from app.domain.user import Applicant, User


def _make_officer_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = "officer@test.com"
    user.role = UserRole.STUDENT_AFFAIRS
    user.first_name = "Officer"
    user.last_name = "Test"
    user.is_active = True
    user.is_verified = True
    user.failed_attempts = 0
    user.locked_until = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _make_applicant_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = "applicant@test.com"
    user.role = UserRole.APPLICANT
    user.first_name = "Applicant"
    user.last_name = "Test"
    user.is_active = True
    user.is_verified = True
    user.failed_attempts = 0
    user.locked_until = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def officer_client():
    from app.core.database import get_db
    from app.core.dependencies import get_current_user
    from app.main import app

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    officer = _make_officer_user()

    async def override_get_current_user():
        return officer

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, mock_db, officer

    app.dependency_overrides.clear()


@pytest.fixture
async def applicant_client():
    from app.core.database import get_db
    from app.core.dependencies import get_current_user
    from app.main import app

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    async def override_get_db():
        yield mock_db

    applicant = _make_applicant_user()

    async def override_get_current_user():
        return applicant

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def test_approve_verification_returns_verified_display_status(officer_client):
    client, db, officer = officer_client
    application_id = uuid.uuid4()

    mock_app = MagicMock()
    mock_app.id = application_id
    mock_app.status = AppStatus.UNDER_REVIEW

    with patch(
        "app.api.student_affairs.OfficerApplicationService.approve_verification",
        new_callable=AsyncMock,
        return_value=mock_app,
    ):
        start = time.perf_counter()
        resp = await client.post(
            f"/api/staff/applications/{application_id}/approve-verification"
        )
        elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UNDER_REVIEW"
    assert data["display_status"] == "Verified"
    assert elapsed < 2.0


async def test_request_correction_returns_200(officer_client):
    client, db, officer = officer_client
    application_id = uuid.uuid4()

    mock_app = MagicMock()
    mock_app.id = application_id
    mock_app.status = AppStatus.CORRECTION_REQUESTED

    with patch(
        "app.api.student_affairs.OfficerApplicationService.request_correction",
        new_callable=AsyncMock,
        return_value=mock_app,
    ):
        resp = await client.post(
            f"/api/staff/applications/{application_id}/request-correction",
            json={"note": "Please fix your transcript"},
        )

    assert resp.status_code == 200
    assert resp.json()["display_status"] == "Correction Requested"


async def test_request_correction_empty_note_returns_422(officer_client):
    client, db, officer = officer_client
    application_id = uuid.uuid4()

    resp = await client.post(
        f"/api/staff/applications/{application_id}/request-correction",
        json={"note": ""},
    )

    assert resp.status_code == 422


async def test_reject_application_returns_200(officer_client):
    client, db, officer = officer_client
    application_id = uuid.uuid4()

    mock_app = MagicMock()
    mock_app.id = application_id
    mock_app.status = AppStatus.REJECTED

    with patch(
        "app.api.student_affairs.OfficerApplicationService.reject_application",
        new_callable=AsyncMock,
        return_value=mock_app,
    ):
        resp = await client.post(
            f"/api/staff/applications/{application_id}/reject",
            json={"reason_code": "INVALID_DOCUMENT", "note": "Unreadable scan"},
        )

    assert resp.status_code == 200
    assert resp.json()["display_status"] == "Rejected"


async def test_applicant_cannot_access_staff_endpoints(applicant_client):
    resp = await applicant_client.get("/api/staff/applications")
    assert resp.status_code == 403


async def test_preview_corrupted_document_returns_srs_error_message(officer_client):
    client, db, officer = officer_client
    application_id = uuid.uuid4()
    document_id = uuid.uuid4()

    mock_doc = MagicMock()
    mock_doc.application_id = application_id

    with (
        patch(
            "app.repositories.document_repository.DocumentRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=mock_doc,
        ),
        patch(
            "app.api.student_affairs.DocumentService.generate_preview_url_with_status",
            new_callable=AsyncMock,
            return_value=("https://minio/preview", False, "application/pdf"),
        ),
    ):
        resp = await client.get(
            f"/api/staff/applications/{application_id}/documents/{document_id}/preview"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["viewable"] is False
    assert data["error_message"] == (
        "Document Cannot Be Viewed – File May Be Corrupted."
    )


async def test_get_application_includes_applicant_and_validation_results(officer_client):
    client, db, officer = officer_client
    application_id = uuid.uuid4()

    mock_user = _make_applicant_user()
    mock_applicant = Applicant()
    mock_applicant.id = mock_user.id
    mock_applicant.national_id = "12345678901"
    mock_applicant.phone = "5551234567"
    mock_applicant.user = mock_user

    mock_app = MagicMock()
    mock_app.id = application_id
    mock_app.applicant_id = mock_user.id
    mock_app.program_id = uuid.uuid4()
    mock_app.period_id = uuid.uuid4()
    mock_app.status = AppStatus.SUBMITTED
    mock_app.tracking_number = "APP-2026-00001"
    mock_app.submitted_at = datetime.now(timezone.utc)
    mock_app.created_at = datetime.now(timezone.utc)
    mock_app.updated_at = datetime.now(timezone.utc)
    mock_app.correction_deadline = None
    mock_app.applicant = mock_applicant
    mock_app.eligibility_checks = []
    mock_app.documents = []
    mock_app.get_progress = MagicMock(return_value={"percentage": 20})

    with patch(
        "app.api.student_affairs.OfficerApplicationService.get_application",
        new_callable=AsyncMock,
        return_value=mock_app,
    ):
        resp = await client.get(f"/api/staff/applications/{application_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["applicant"]["email"] == mock_user.email
    assert data["applicant"]["national_id"] == "12345678901"
    assert "auto_validation_results" in data
