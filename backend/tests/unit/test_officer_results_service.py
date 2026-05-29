"""
Unit tests for results publication (SPEC-007).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.domain.enums import AppStatus, RankStatus
from app.services.officer_service import OfficerApplicationService


@pytest.fixture
def db():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _make_ranking(status: RankStatus = RankStatus.APPROVED):
    ranking = MagicMock()
    ranking.id = uuid.uuid4()
    ranking.status = status
    ranking.published_at = None
    ranking.program = MagicMock(name="Computer Engineering")
    ranking.period = MagicMock(label="2025-2026 Spring")

    entry = MagicMock()
    entry.application_id = uuid.uuid4()
    entry.position = 1
    entry.composite_score = Decimal("85.500")
    entry.is_primary = True

    app = MagicMock()
    app.id = entry.application_id
    app.tracking_number = "APP-MOCK-00001"
    app.applicant = MagicMock()
    app.applicant.user = MagicMock(
        first_name="Ayşe", last_name="Yılmaz", email="applicant@iyte.edu.tr"
    )
    entry.application = app
    ranking.entries = [entry]
    return ranking


def _make_ranking_app():
    app = MagicMock()
    app.id = uuid.uuid4()
    app.applicant_id = uuid.uuid4()
    app.tracking_number = "APP-MOCK-00001"
    app.applicant = MagicMock()
    app.applicant.user = MagicMock(email="applicant@iyte.edu.tr")
    app.ranking_entry = MagicMock(is_primary=True)
    return app


def _make_service(db):
    service = OfficerApplicationService(db)
    service._app_repo = AsyncMock()
    service._ranking_repo = AsyncMock()
    service._notif_service = AsyncMock()
    service._notif_service.enqueue_bulk = AsyncMock(return_value=1)
    return service


async def test_get_results_returns_primary_and_waitlisted(db):
    service = _make_service(db)
    ranking = _make_ranking(RankStatus.APPROVED)

    waitlisted_entry = MagicMock()
    waitlisted_entry.application_id = uuid.uuid4()
    waitlisted_entry.position = 2
    waitlisted_entry.composite_score = Decimal("80.000")
    waitlisted_entry.is_primary = False
    waitlisted_app = MagicMock()
    waitlisted_app.id = waitlisted_entry.application_id
    waitlisted_app.tracking_number = "APP-MOCK-00002"
    waitlisted_app.applicant = MagicMock()
    waitlisted_app.applicant.user = MagicMock(
        first_name="Mehmet", last_name="Demir", email="waitlist@iyte.edu.tr"
    )
    waitlisted_entry.application = waitlisted_app
    ranking.entries.append(waitlisted_entry)

    service._ranking_repo.get_by_program_and_period = AsyncMock(return_value=ranking)

    period_id = uuid.uuid4()
    program_id = uuid.uuid4()
    result = await service.get_results(period_id, program_id)

    assert result.can_publish is True
    assert len(result.primary) == 1
    assert len(result.waitlisted) == 1
    assert result.primary[0].result_label == "Asil"
    assert result.waitlisted[0].result_label == "Yedek"


async def test_get_results_422_when_ranking_not_approved(db):
    service = _make_service(db)
    service._ranking_repo.get_by_program_and_period = AsyncMock(
        return_value=_make_ranking(RankStatus.DRAFT)
    )

    with pytest.raises(HTTPException) as exc:
        await service.get_results(uuid.uuid4(), uuid.uuid4())
    assert exc.value.status_code == 422


async def test_publish_results_409_when_already_published(db):
    service = _make_service(db)
    service._ranking_repo.get_by_program_and_period = AsyncMock(
        return_value=_make_ranking(RankStatus.PUBLISHED)
    )

    with pytest.raises(HTTPException) as exc:
        await service.publish_results(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    assert exc.value.status_code == 409


async def test_publish_results_announces_and_enqueues_notifications(db):
    service = _make_service(db)
    ranking = _make_ranking(RankStatus.APPROVED)
    ranking_app = _make_ranking_app()
    ranking_app.id = ranking.entries[0].application_id

    service._ranking_repo.get_by_program_and_period = AsyncMock(return_value=ranking)
    service._app_repo.get_by_program_period_and_status = AsyncMock(
        return_value=[ranking_app]
    )
    service._app_repo.bulk_update_status = AsyncMock(return_value=1)

    officer_id = uuid.uuid4()
    result = await service.publish_results(
        uuid.uuid4(), uuid.uuid4(), officer_id
    )

    assert result.announced_count == 1
    assert result.notifications_enqueued == 1
    assert ranking.status == RankStatus.PUBLISHED
    assert ranking.published_at is not None
    service._notif_service.enqueue_bulk.assert_awaited_once()
    db.add.assert_called()
