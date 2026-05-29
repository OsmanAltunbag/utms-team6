"""
Unit tests for OfficerApplicationService (SPEC-006).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.application import Application
from app.domain.enums import AppStatus
from app.services.officer_service import OfficerApplicationService


@pytest.fixture
def db():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _make_application(status: AppStatus = AppStatus.SUBMITTED) -> MagicMock:
    app = MagicMock(spec=Application)
    app.id = uuid.uuid4()
    app.applicant_id = uuid.uuid4()
    app.program_id = uuid.uuid4()
    app.period_id = uuid.uuid4()
    app.status = status
    app.tracking_number = "APP-2026-00001"
    app.submitted_at = datetime.now(timezone.utc)
    app.created_at = datetime.now(timezone.utc)
    app.correction_deadline = None
    app.correction_requested_at = None
    app.eligibility_checks = []
    app.documents = []
    return app


def _make_service(db, application=None):
    service = OfficerApplicationService(db)
    service._app_repo = AsyncMock()
    service._notif_service = AsyncMock()
    service._notif_service.enqueue = AsyncMock()
    service._app_service = AsyncMock()

    if application is not None:
        service._app_repo.get_by_id = AsyncMock(return_value=application)
        updated = _make_application()
        updated.status = AppStatus.UNDER_REVIEW
        service._app_service.change_status = AsyncMock(return_value=updated)

    return service


async def test_approve_verification_updates_status_and_logs(db):
    app = _make_application(AppStatus.SUBMITTED)
    service = _make_service(db, app)

    updated = _make_application(AppStatus.UNDER_REVIEW)
    updated.status = AppStatus.UNDER_REVIEW
    service._app_service.change_status = AsyncMock(return_value=updated)

    officer_id = uuid.uuid4()
    result = await service.approve_verification(app.id, officer_id)

    assert result.status == AppStatus.UNDER_REVIEW
    service._app_service.change_status.assert_awaited_once()
    db.add.assert_called()
    service._notif_service.enqueue.assert_awaited_once()


async def test_request_correction_sets_deadline(db):
    app = _make_application(AppStatus.SUBMITTED)
    service = _make_service(db, app)

    updated = _make_application(AppStatus.CORRECTION_REQUESTED)
    updated.status = AppStatus.CORRECTION_REQUESTED
    service._app_service.change_status = AsyncMock(return_value=updated)

    officer_id = uuid.uuid4()
    result = await service.request_correction(
        app.id, officer_id, "Please re-upload transcript"
    )

    assert result.status == AppStatus.CORRECTION_REQUESTED
    assert updated.correction_deadline is not None
    assert updated.correction_requested_at is not None
    service._notif_service.enqueue.assert_awaited_once()


async def test_request_correction_without_note_raises_422(db):
    app = _make_application(AppStatus.SUBMITTED)
    service = _make_service(db, app)

    with pytest.raises(HTTPException) as exc_info:
        await service.request_correction(app.id, uuid.uuid4(), "   ")

    assert exc_info.value.status_code == 422


async def test_reject_application_from_submitted(db):
    app = _make_application(AppStatus.SUBMITTED)
    service = _make_service(db, app)

    updated = _make_application(AppStatus.REJECTED)
    updated.status = AppStatus.REJECTED
    service._app_service.change_status = AsyncMock(return_value=updated)

    officer_id = uuid.uuid4()
    result = await service.reject_application(
        app.id, officer_id, "INVALID_DOCUMENT", "Transcript unreadable"
    )

    assert result.status == AppStatus.REJECTED
    service._notif_service.enqueue.assert_awaited_once()


async def test_reject_after_correction_deadline(db):
    app = _make_application(AppStatus.CORRECTION_REQUESTED)
    app.correction_deadline = datetime.now(timezone.utc) - timedelta(days=1)
    service = _make_service(db, app)

    updated = _make_application(AppStatus.REJECTED)
    updated.status = AppStatus.REJECTED
    service._app_service.change_status = AsyncMock(return_value=updated)

    result = await service.reject_application(
        app.id, uuid.uuid4(), "MISSED_DEADLINE", "Deadline passed"
    )

    assert result.status == AppStatus.REJECTED


async def test_reject_before_correction_deadline_raises_422(db):
    app = _make_application(AppStatus.CORRECTION_REQUESTED)
    app.correction_deadline = datetime.now(timezone.utc) + timedelta(days=3)
    service = _make_service(db, app)

    with pytest.raises(HTTPException) as exc_info:
        await service.reject_application(
            app.id, uuid.uuid4(), "MISSED_DEADLINE", "Too early"
        )

    assert exc_info.value.status_code == 422


async def test_reject_application_invalid_reason_code_raises_422(db):
    app = _make_application(AppStatus.SUBMITTED)
    service = _make_service(db, app)

    with pytest.raises(HTTPException) as exc_info:
        await service.reject_application(app.id, uuid.uuid4(), "BAD_CODE", "note")

    assert exc_info.value.status_code == 422


async def test_approve_verification_wrong_status_raises_422(db):
    app = _make_application(AppStatus.DRAFT)
    service = _make_service(db, app)

    with pytest.raises(HTTPException) as exc_info:
        await service.approve_verification(app.id, uuid.uuid4())

    assert exc_info.value.status_code == 422
