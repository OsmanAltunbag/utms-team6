"""
Unit tests for EligibilityEngine (SPEC-009).
All DB and repository calls are mocked — no PostgreSQL needed.

Covers T1–T7 scenarios:
  T1 — MIN_GPA passes
  T2 — MIN_GPA fails
  T3 — MIN_YKS passes
  T4 — MIN_YKS fails
  T5 — MIN_CREDITS passes / fails
  T6 — REQUIRED_DOC present / missing
  T7 — CORE_COURSE_GRADE passes / fails
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.domain.eligibility import DepartmentRequirement, EligibilityCheck
from app.domain.enums import DocType
from app.services.eligibility_engine import EligibilityEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> EligibilityEngine:
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return EligibilityEngine(db)


def _req(rule_key: str, rule_value: str) -> DepartmentRequirement:
    r = DepartmentRequirement()
    r.id = uuid.uuid4()
    r.program_id = uuid.uuid4()
    r.rule_key = rule_key
    r.rule_value = rule_value
    r.description = None
    r.is_active = True
    return r


def _record(
    gpa_4: Decimal | None = None,
    yks_score: Decimal | None = None,
    credits_completed: int | None = None,
) -> MagicMock:
    rec = MagicMock()
    rec.gpa_4 = gpa_4
    rec.yks_score = yks_score
    rec.credits_completed = credits_completed
    return rec


def _transcript_doc(courses: list | None = None) -> MagicMock:
    doc = MagicMock()
    doc.doc_type = DocType.TRANSCRIPT
    doc.extracted_data = {"courses": courses} if courses is not None else None
    return doc


def _make_application(record=None, docs=None) -> MagicMock:
    app = MagicMock()
    app.id = uuid.uuid4()
    app.applicant_id = uuid.uuid4()
    app.program_id = uuid.uuid4()
    app.academic_record = record
    app.documents = docs or []
    return app


def _make_service(engine: EligibilityEngine, application=None, requirements=None):
    engine._app_repo = AsyncMock()
    engine._app_repo.get_by_id = AsyncMock(return_value=application)
    engine._dept_req_repo = AsyncMock()
    engine._dept_req_repo.get_by_program = AsyncMock(return_value=requirements or [])
    engine._elig_repo = AsyncMock()
    engine._elig_repo.save = AsyncMock()


# ---------------------------------------------------------------------------
# T1 — MIN_GPA passes when GPA meets or exceeds threshold
# ---------------------------------------------------------------------------

def test_t1_min_gpa_passes():
    engine = _engine()
    req = _req("MIN_GPA", "3.00")
    record = _record(gpa_4=Decimal("3.50"))

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is True
    assert "3.50" in detail
    assert ">=" in detail


# ---------------------------------------------------------------------------
# T2 — MIN_GPA fails when GPA is below threshold
# ---------------------------------------------------------------------------

def test_t2_min_gpa_fails():
    engine = _engine()
    req = _req("MIN_GPA", "3.00")
    record = _record(gpa_4=Decimal("2.50"))

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is False
    assert "2.50" in detail
    assert "<" in detail


def test_t2_min_gpa_fails_no_record():
    engine = _engine()
    req = _req("MIN_GPA", "3.00")

    passed, detail = engine._evaluate_rule(req, None, {})

    assert passed is False
    assert "not available" in detail


# ---------------------------------------------------------------------------
# T3 — MIN_YKS passes when score meets or exceeds threshold
# ---------------------------------------------------------------------------

def test_t3_min_yks_passes():
    engine = _engine()
    req = _req("MIN_YKS", "420.000")
    record = _record(yks_score=Decimal("450.500"))

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is True
    assert "450.500" in detail


# ---------------------------------------------------------------------------
# T4 — MIN_YKS fails when score is below threshold
# ---------------------------------------------------------------------------

def test_t4_min_yks_fails():
    engine = _engine()
    req = _req("MIN_YKS", "420.000")
    record = _record(yks_score=Decimal("380.000"))

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is False
    assert "380.000" in detail


def test_t4_min_yks_fails_no_score():
    engine = _engine()
    req = _req("MIN_YKS", "420.000")
    record = _record(yks_score=None)

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is False
    assert "not available" in detail


# ---------------------------------------------------------------------------
# T5 — MIN_CREDITS passes and fails
# ---------------------------------------------------------------------------

def test_t5_min_credits_passes():
    engine = _engine()
    req = _req("MIN_CREDITS", "60")
    record = _record(credits_completed=90)

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is True
    assert "90" in detail


def test_t5_min_credits_fails():
    engine = _engine()
    req = _req("MIN_CREDITS", "60")
    record = _record(credits_completed=45)

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is False
    assert "45" in detail


def test_t5_min_credits_fails_no_data():
    engine = _engine()
    req = _req("MIN_CREDITS", "60")
    record = _record(credits_completed=None)

    passed, detail = engine._evaluate_rule(req, record, {})

    assert passed is False
    assert "not available" in detail


# ---------------------------------------------------------------------------
# T6 — REQUIRED_DOC present and missing
# ---------------------------------------------------------------------------

def test_t6_required_doc_present():
    engine = _engine()
    req = _req("REQUIRED_DOC", "TRANSCRIPT")
    transcript = _transcript_doc()
    docs = {DocType.TRANSCRIPT: transcript}

    passed, detail = engine._evaluate_rule(req, None, docs)

    assert passed is True
    assert "TRANSCRIPT" in detail


def test_t6_required_doc_missing():
    engine = _engine()
    req = _req("REQUIRED_DOC", "YKS_RESULT")

    passed, detail = engine._evaluate_rule(req, None, {})

    assert passed is False
    assert "YKS_RESULT" in detail
    assert "missing" in detail


def test_t6_required_doc_invalid_type():
    engine = _engine()
    req = _req("REQUIRED_DOC", "NONEXISTENT_TYPE")

    passed, detail = engine._evaluate_rule(req, None, {})

    assert passed is False
    assert "Invalid" in detail


# ---------------------------------------------------------------------------
# T7 — CORE_COURSE_GRADE passes and fails
# ---------------------------------------------------------------------------

def test_t7_core_course_grade_passes():
    engine = _engine()
    req = _req("CORE_COURSE_GRADE", "MATH101:2.50")
    transcript = _transcript_doc(courses=[{"code": "MATH101", "grade": 3.0}])
    docs = {DocType.TRANSCRIPT: transcript}

    passed, detail = engine._evaluate_rule(req, None, docs)

    assert passed is True
    assert "MATH101" in detail
    assert "3.0" in detail


def test_t7_core_course_grade_fails_low_grade():
    engine = _engine()
    req = _req("CORE_COURSE_GRADE", "MATH101:2.50")
    transcript = _transcript_doc(courses=[{"code": "MATH101", "grade": 2.0}])
    docs = {DocType.TRANSCRIPT: transcript}

    passed, detail = engine._evaluate_rule(req, None, docs)

    assert passed is False
    assert "MATH101" in detail
    assert "<" in detail


def test_t7_core_course_grade_fails_course_not_found():
    engine = _engine()
    req = _req("CORE_COURSE_GRADE", "MATH101:2.50")
    transcript = _transcript_doc(courses=[{"code": "PHYS101", "grade": 3.5}])
    docs = {DocType.TRANSCRIPT: transcript}

    passed, detail = engine._evaluate_rule(req, None, docs)

    assert passed is False
    assert "not found" in detail


def test_t7_core_course_grade_fails_no_transcript():
    engine = _engine()
    req = _req("CORE_COURSE_GRADE", "MATH101:2.50")

    passed, detail = engine._evaluate_rule(req, None, {})

    assert passed is False
    assert "not available" in detail


def test_t7_core_course_grade_invalid_format():
    engine = _engine()
    req = _req("CORE_COURSE_GRADE", "MATH101")  # missing :GRADE part

    passed, detail = engine._evaluate_rule(req, None, {})

    assert passed is False
    assert "Invalid" in detail


# ---------------------------------------------------------------------------
# evaluate_department_conditions — integration-style unit test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_department_conditions_all_pass():
    engine = _engine()
    record = _record(gpa_4=Decimal("3.50"), yks_score=Decimal("450.0"), credits_completed=90)
    application = _make_application(record=record, docs=[])

    requirements = [
        _req("MIN_GPA", "3.00"),
        _req("MIN_CREDITS", "60"),
    ]
    _make_service(engine, application=application, requirements=requirements)

    checks = await engine.evaluate_department_conditions(
        application_id=application.id,
        evaluator_id=uuid.uuid4(),
    )

    assert len(checks) == 2
    assert all(c.passed for c in checks)


@pytest.mark.asyncio
async def test_evaluate_department_conditions_partial_fail():
    engine = _engine()
    record = _record(gpa_4=Decimal("2.50"), yks_score=None, credits_completed=90)
    application = _make_application(record=record, docs=[])

    requirements = [
        _req("MIN_GPA", "3.00"),
        _req("MIN_CREDITS", "60"),
    ]
    _make_service(engine, application=application, requirements=requirements)

    checks = await engine.evaluate_department_conditions(
        application_id=application.id,
        evaluator_id=uuid.uuid4(),
    )

    assert len(checks) == 2
    gpa_check = next(c for c in checks if c.rule_key == "MIN_GPA")
    credits_check = next(c for c in checks if c.rule_key == "MIN_CREDITS")
    assert gpa_check.passed is False
    assert credits_check.passed is True


@pytest.mark.asyncio
async def test_evaluate_department_conditions_app_not_found():
    engine = _engine()
    _make_service(engine, application=None, requirements=[])

    with pytest.raises(HTTPException) as exc_info:
        await engine.evaluate_department_conditions(
            application_id=uuid.uuid4(),
            evaluator_id=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_department_conditions_skips_inactive_rules():
    engine = _engine()
    record = _record(gpa_4=Decimal("2.00"))
    application = _make_application(record=record, docs=[])

    inactive_req = _req("MIN_GPA", "3.00")
    inactive_req.is_active = False

    _make_service(engine, application=application, requirements=[inactive_req])

    checks = await engine.evaluate_department_conditions(
        application_id=application.id,
        evaluator_id=uuid.uuid4(),
    )

    assert checks == []
