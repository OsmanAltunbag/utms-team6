"""
Integration tests for results publication API (SPEC-007).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.officer import ResultsListResponse
from app.domain.user import User


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


async def test_get_results_returns_read_only_lists(officer_client):
    client, _, _ = officer_client
    period_id = uuid.uuid4()
    program_id = uuid.uuid4()

    mock_response = ResultsListResponse(
        period_id=period_id,
        program_id=program_id,
        program_name="Computer Engineering",
        period_label="2025-2026 Spring",
        ranking_status=RankStatus.APPROVED.value,
        published_at=None,
        is_read_only=True,
        can_publish=True,
        primary=[],
        waitlisted=[],
    )

    with patch(
        "app.api.student_affairs.OfficerApplicationService.get_results",
        new=AsyncMock(return_value=mock_response),
    ):
        resp = await client.get(f"/api/staff/results/{period_id}/{program_id}")

    assert resp.status_code == 200


async def test_publish_results_returns_announced_count(officer_client):
    client, _, officer = officer_client
    period_id = uuid.uuid4()
    program_id = uuid.uuid4()

    published_at = datetime.now(timezone.utc)
    mock_result = MagicMock()
    mock_result.announced_count = 3
    mock_result.notifications_enqueued = 3
    mock_result.published_at = published_at

    with patch(
        "app.api.student_affairs.OfficerApplicationService.publish_results",
        new=AsyncMock(return_value=mock_result),
    ) as mock_publish:
        resp = await client.post(
            f"/api/staff/results/{period_id}/{program_id}/publish"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["announced_count"] == 3
    assert data["notifications_enqueued"] == 3
    mock_publish.assert_awaited_once_with(period_id, program_id, officer.id)


async def test_applicant_cannot_publish_results():
    from app.core.database import get_db
    from app.core.dependencies import get_current_user
    from app.main import app

    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    applicant = User()
    applicant.id = uuid.uuid4()
    applicant.role = UserRole.APPLICANT
    applicant.is_active = True
    applicant.is_verified = True

    async def override_get_current_user():
        return applicant

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/staff/results/{uuid.uuid4()}/{uuid.uuid4()}/publish"
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 403
