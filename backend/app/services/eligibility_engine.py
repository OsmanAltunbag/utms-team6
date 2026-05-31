import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eligibility import DepartmentEvaluation, DepartmentRequirement, EligibilityCheck
from app.domain.enums import DocType, IntibakStatus
from app.domain.intibak import CourseMapping, IntibakTable
from app.repositories.application_repository import ApplicationRepository
from app.repositories.eligibility_repository import DepartmentRequirementRepository, EligibilityRepository

logger = logging.getLogger(__name__)


class EligibilityEngine:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._dept_req_repo = DepartmentRequirementRepository(db)
        self._elig_repo = EligibilityRepository(db)

    async def evaluate_department_conditions(
        self,
        application_id: uuid.UUID,
        evaluator_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> List[EligibilityCheck]:
        application = await self._app_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        requirements = await self._dept_req_repo.get_by_program(application.program_id)
        record = application.academic_record
        docs = {d.doc_type: d for d in application.documents}

        checks: List[EligibilityCheck] = []
        for req in requirements:
            if not req.is_active:
                continue
            passed, detail = self._evaluate_rule(req, record, docs)
            check = EligibilityCheck(
                application_id=application_id,
                rule_key=req.rule_key,
                passed=passed,
                detail=detail,
            )
            await self._elig_repo.save(check)
            checks.append(check)

        all_passed = all(c.passed for c in checks) if checks else True

        evaluation = DepartmentEvaluation(
            application_id=application_id,
            evaluator_id=evaluator_id,
            passed=all_passed,
            notes=notes,
            evaluated_at=datetime.now(timezone.utc),
        )
        self.db.add(evaluation)
        await self.db.flush()

        return checks

    async def manual_course_mapping(
        self,
        application_id: uuid.UUID,
        prepared_by: uuid.UUID,
        mappings: List[dict],
    ) -> dict:
        application = await self._app_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        result = await self.db.execute(
            select(IntibakTable).where(IntibakTable.application_id == application_id)
        )
        intibak = result.scalar_one_or_none()

        if intibak is None:
            intibak = IntibakTable(
                application_id=application_id,
                prepared_by=prepared_by,
                status=IntibakStatus.DRAFT,
            )
            self.db.add(intibak)
            await self.db.flush()

        if not intibak.is_editable:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Course mapping table is not editable in its current status",
            )

        for m in mappings:
            self.db.add(CourseMapping(
                intibak_table_id=intibak.id,
                source_course=m["source_course"],
                target_course=m["target_course"],
                source_credits=m.get("source_credits"),
                target_credits=m.get("target_credits"),
                equivalence_type=m.get("equivalence_type", "FULL"),
                notes=m.get("notes"),
            ))

        await self.db.flush()

        return {
            "intibak_table_id": str(intibak.id),
            "application_id": str(application_id),
            "mappings_added": len(mappings),
        }

    # ------------------------------------------------------------------
    # Rule evaluators — pure sync, no DB access
    # ------------------------------------------------------------------

    def _evaluate_rule(
        self,
        req: DepartmentRequirement,
        record,
        docs: dict,
    ) -> tuple[bool, str]:
        key = req.rule_key
        val = req.rule_value
        if key == "MIN_GPA":
            return self._check_min_gpa(val, record)
        if key == "MIN_YKS":
            return self._check_min_yks(val, record)
        if key == "MIN_CREDITS":
            return self._check_min_credits(val, record)
        if key == "REQUIRED_DOC":
            return self._check_required_doc(val, docs)
        if key == "CORE_COURSE_GRADE":
            return self._check_core_course_grade(val, docs)
        return False, f"Unknown rule type: {key}"

    def _check_min_gpa(self, rule_value: str, record) -> tuple[bool, str]:
        try:
            threshold = Decimal(rule_value)
        except InvalidOperation:
            return False, f"Invalid MIN_GPA threshold: {rule_value}"
        if record is None or record.gpa_4 is None:
            return False, "GPA data not available"
        gpa = Decimal(str(record.gpa_4))
        if gpa >= threshold:
            return True, f"GPA {gpa:.2f} >= minimum {threshold:.2f}"
        return False, f"GPA {gpa:.2f} < minimum {threshold:.2f}"

    def _check_min_yks(self, rule_value: str, record) -> tuple[bool, str]:
        try:
            threshold = Decimal(rule_value)
        except InvalidOperation:
            return False, f"Invalid MIN_YKS threshold: {rule_value}"
        if record is None or record.yks_score is None:
            return False, "YKS score not available"
        score = Decimal(str(record.yks_score))
        if score >= threshold:
            return True, f"YKS score {score:.3f} >= minimum {threshold:.3f}"
        return False, f"YKS score {score:.3f} < minimum {threshold:.3f}"

    def _check_min_credits(self, rule_value: str, record) -> tuple[bool, str]:
        try:
            threshold = int(rule_value)
        except ValueError:
            return False, f"Invalid MIN_CREDITS threshold: {rule_value}"
        if record is None or record.credits_completed is None:
            return False, "Credit data not available"
        if record.credits_completed >= threshold:
            return True, f"Credits {record.credits_completed} >= minimum {threshold}"
        return False, f"Credits {record.credits_completed} < minimum {threshold}"

    def _check_required_doc(self, rule_value: str, docs: dict) -> tuple[bool, str]:
        try:
            required_type = DocType(rule_value)
        except ValueError:
            return False, f"Invalid document type in rule: {rule_value}"
        if required_type in docs:
            return True, f"Required document {rule_value} is present"
        return False, f"Required document {rule_value} is missing"

    def _check_core_course_grade(self, rule_value: str, docs: dict) -> tuple[bool, str]:
        # rule_value format: "COURSE_CODE:MIN_GRADE"  e.g. "MATH101:2.50"
        try:
            course_code, min_grade_str = rule_value.split(":", 1)
            min_grade = float(min_grade_str)
        except (ValueError, AttributeError):
            return False, f"Invalid CORE_COURSE_GRADE format (expected CODE:GRADE): {rule_value}"
        transcript = docs.get(DocType.TRANSCRIPT)
        if transcript is None or not transcript.extracted_data:
            return False, "Transcript data not available for course grade check"
        for course in transcript.extracted_data.get("courses", []):
            if course.get("code") == course_code:
                grade = course.get("grade")
                if grade is None:
                    return False, f"Grade not found for course {course_code}"
                if float(grade) >= min_grade:
                    return True, f"Course {course_code} grade {grade} >= minimum {min_grade}"
                return False, f"Course {course_code} grade {grade} < minimum {min_grade}"
        return False, f"Course {course_code} not found in transcript"
