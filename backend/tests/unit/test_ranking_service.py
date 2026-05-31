"""
Unit tests for RankingService (SPEC-010).
All DB and repository calls are mocked — no PostgreSQL needed.

Covers: T1 score formula, T2 tie-break, T3 excluded missing score,
        T4 quota split asil/yedek, T6 performance ≤10s for 1000 applicants.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.domain.enums import AppStatus
from app.domain.ranking import Ranking, RankingEntry
from app.services.ranking_service import RankingService, calculate_transfer_score


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


def _make_program(quota: int = 5, base_score: float = 400.0) -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.quota = quota
    p.base_score = base_score
    return p


def _make_period() -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    return p


def _make_app(
    yks_score=None,
    gpa_100=None,
    submitted_at=None,
) -> MagicMock:
    app = MagicMock()
    app.id = uuid.uuid4()
    app.status = AppStatus.RANKING
    app.submitted_at = submitted_at or datetime.now(timezone.utc)
    record = MagicMock()
    record.yks_score = Decimal(str(yks_score)) if yks_score is not None else None
    record.gpa_100 = Decimal(str(gpa_100)) if gpa_100 is not None else None
    app.academic_record = record
    return app


def _make_service(db, program=None, period=None, applications=None) -> RankingService:
    service = RankingService(db)
    service._program_repo = AsyncMock()
    service._program_repo.get_by_id = AsyncMock(return_value=program)
    service._period_repo = AsyncMock()
    service._period_repo.get_by_id = AsyncMock(return_value=period)
    service._app_repo = AsyncMock()
    service._app_repo.get_by_program_period_status = AsyncMock(
        return_value=applications or []
    )
    return service


def _extract_entries(db) -> list[RankingEntry]:
    return [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], RankingEntry)
    ]


# ---------------------------------------------------------------------------
# T1 — Correct score calculation (pure function)
# ---------------------------------------------------------------------------

def test_calculate_transfer_score_correct():
    # exam = (400/400)*100*0.90 = 90.0, gpa = 80*0.10 = 8.0, total = 98.0
    assert calculate_transfer_score(400.0, 400.0, 80.0) == 98.0


def test_calculate_transfer_score_partial_score():
    # exam = (360/400)*100*0.90 = 81.0, gpa = 75*0.10 = 7.5, total = 88.5
    assert calculate_transfer_score(360.0, 400.0, 75.0) == 88.5


def test_calculate_transfer_score_rounded_to_3dp():
    score = calculate_transfer_score(450.0, 400.0, 75.5)
    # exam = (450/400)*100*0.90 = 101.25, gpa = 75.5*0.10 = 7.55 → 108.8
    assert score == round(101.25 + 7.55, 3)


# ---------------------------------------------------------------------------
# T2 — Tie-break by submitted_at ASC (SR2)
# ---------------------------------------------------------------------------

async def test_generate_ranking_tiebreak_by_submitted_at():
    db = _make_db()
    program = _make_program(quota=5, base_score=400.0)
    period = _make_period()

    t_early = datetime(2024, 3, 1, tzinfo=timezone.utc)
    t_late = datetime(2024, 3, 2, tzinfo=timezone.utc)
    # Identical scores — tie must be broken by submitted_at
    app_early = _make_app(yks_score=400.0, gpa_100=80.0, submitted_at=t_early)
    app_late = _make_app(yks_score=400.0, gpa_100=80.0, submitted_at=t_late)

    # Deliberately pass late first to confirm sorting is applied
    service = _make_service(db, program=program, period=period, applications=[app_late, app_early])
    await service.generate_ranking(program.id, period.id, uuid.uuid4())

    entries = _extract_entries(db)
    assert len(entries) == 2
    pos1 = next(e for e in entries if e.position == 1)
    pos2 = next(e for e in entries if e.position == 2)
    assert pos1.application_id == app_early.id
    assert pos2.application_id == app_late.id


# ---------------------------------------------------------------------------
# T3 — Missing yks_score → excluded (AC-01)
# ---------------------------------------------------------------------------

async def test_generate_ranking_missing_yks_score_excluded():
    db = _make_db()
    program = _make_program(quota=5, base_score=400.0)
    period = _make_period()

    app_ok = _make_app(yks_score=400.0, gpa_100=80.0)
    app_no_yks = _make_app(yks_score=None, gpa_100=80.0)

    service = _make_service(
        db, program=program, period=period, applications=[app_ok, app_no_yks]
    )
    await service.generate_ranking(program.id, period.id, uuid.uuid4())

    entries = _extract_entries(db)
    assert len(entries) == 1
    assert entries[0].application_id == app_ok.id


async def test_generate_ranking_missing_base_score_excludes_all():
    db = _make_db()
    program = _make_program(quota=5, base_score=None)
    # Remove base_score attribute so getattr returns None
    del program.base_score
    period = _make_period()

    apps = [_make_app(yks_score=400.0, gpa_100=80.0) for _ in range(3)]
    service = _make_service(db, program=program, period=period, applications=apps)
    await service.generate_ranking(program.id, period.id, uuid.uuid4())

    entries = _extract_entries(db)
    assert len(entries) == 0


# ---------------------------------------------------------------------------
# T4 — Quota split: positions 1..quota → is_primary=True (asil),
#       rest → is_primary=False (yedek)
# ---------------------------------------------------------------------------

async def test_generate_ranking_quota_split_asil_yedek():
    db = _make_db()
    quota = 2
    program = _make_program(quota=quota, base_score=400.0)
    period = _make_period()

    apps = [
        _make_app(
            yks_score=400.0 - i * 10,
            gpa_100=80.0,
            submitted_at=datetime(2024, 3, i + 1, tzinfo=timezone.utc),
        )
        for i in range(5)
    ]
    service = _make_service(db, program=program, period=period, applications=apps)
    await service.generate_ranking(program.id, period.id, uuid.uuid4())

    entries = _extract_entries(db)
    assert len(entries) == 5

    primary = [e for e in entries if e.is_primary]
    waitlisted = [e for e in entries if not e.is_primary]

    assert len(primary) == quota
    assert len(waitlisted) == 5 - quota
    assert all(e.position <= quota for e in primary)
    assert all(e.position > quota for e in waitlisted)


async def test_generate_ranking_all_primary_when_within_quota():
    db = _make_db()
    program = _make_program(quota=10, base_score=400.0)
    period = _make_period()

    apps = [_make_app(yks_score=400.0 - i, gpa_100=80.0) for i in range(3)]
    service = _make_service(db, program=program, period=period, applications=apps)
    await service.generate_ranking(program.id, period.id, uuid.uuid4())

    entries = _extract_entries(db)
    assert all(e.is_primary for e in entries)


# ---------------------------------------------------------------------------
# T6 — Performance: 1000 applicants completes within 10 seconds
# ---------------------------------------------------------------------------

async def test_generate_ranking_performance_1000_applicants():
    db = _make_db()
    program = _make_program(quota=100, base_score=400.0)
    period = _make_period()

    applications = [
        _make_app(
            yks_score=300.0 + (i % 200),
            gpa_100=60.0 + (i % 40),
            submitted_at=datetime(2024, 3, 1, tzinfo=timezone.utc)
            + timedelta(seconds=i),
        )
        for i in range(1000)
    ]
    service = _make_service(
        db, program=program, period=period, applications=applications
    )

    start = time.perf_counter()
    await service.generate_ranking(program.id, period.id, uuid.uuid4())
    elapsed = time.perf_counter() - start

    assert elapsed < 10.0, f"Ranking took {elapsed:.2f}s — must complete within 10s"

    entries = _extract_entries(db)
    assert len(entries) == 1000
