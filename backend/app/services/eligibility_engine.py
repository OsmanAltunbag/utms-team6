"""
SPEC-009: Evaluate Department Specific Conditions
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.audit import AuditLog
from app.domain.eligibility import DepartmentEvaluation, DepartmentRequirement, EligibilityCheck
from app.domain.enums import AppStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.eligibility_repository import EligibilityRepository
from app.services.application_service import ApplicationService


class EligibilityEngine:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._elig_repo = EligibilityRepository(db)
        self._app_svc = ApplicationService(db)

    async def get_conditions_with_status(self, application_id: uuid.UUID) -> dict:
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")

        reqs_result = await self.db.execute(
            select(DepartmentRequirement).where(
                DepartmentRequirement.program_id == app.program_id,
                DepartmentRequirement.is_active == True,
            )
        )
        requirements = list(reqs_result.scalars().all())

        checks_by_key = {c.rule_key: c for c in app.eligibility_checks}

        return {
            "requirements": [
                {
                    "rule_key": r.rule_key,
                    "required_value": r.rule_value,
                    "description": r.description,
                    "result": "Met" if checks_by_key.get(r.rule_key) and checks_by_key[r.rule_key].passed
                              else "Not Met" if r.rule_key in checks_by_key
                              else "Pending",
                    "detail": checks_by_key[r.rule_key].detail if r.rule_key in checks_by_key else None,
                }
                for r in requirements
            ]
        }

    async def evaluate_department_conditions(
        self,
        application_id: uuid.UUID,
        evaluator_id: uuid.UUID,
        notes: Optional[str] = None,
        rejection_override: bool = False,
        portfolio_result: Optional[str] = None,
        rejection_justification: Optional[str] = None,
    ) -> dict:
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.UNDER_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected UNDER_REVIEW, got {app.status.value}",
            )

        reqs_result = await self.db.execute(
            select(DepartmentRequirement).where(
                DepartmentRequirement.program_id == app.program_id,
                DepartmentRequirement.is_active == True,
            )
        )
        requirements = list(reqs_result.scalars().all())

        record = app.academic_record

        # Index existing manual course mappings so they are honoured here.
        existing_manual = {
            c.rule_key: c
            for c in app.eligibility_checks
            if c.detail and c.detail.startswith("Manual course mapping:")
        }

        checks = []
        automated_passed = True

        for req in requirements:
            if req.rule_key == "PORTFOLIO_REQUIRED" and portfolio_result is not None:
                # Evaluator provided an explicit portfolio decision — use it.
                passed = portfolio_result == "Passed"
                detail = f"Portfolio manually reviewed by YGK: {portfolio_result}"
            elif req.rule_key in existing_manual:
                # A previous manual-course-mapping call already resolved this rule.
                passed = existing_manual[req.rule_key].passed
                detail = existing_manual[req.rule_key].detail
            else:
                passed, detail = self._evaluate_rule(req, record, app)

            if not passed:
                automated_passed = False

            check = EligibilityCheck(
                application_id=application_id,
                rule_key=req.rule_key,
                passed=passed,
                detail=detail,
            )
            self.db.add(check)
            checks.append(check)

        await self.db.flush()

        # ── Final outcome decision ──────────────────────────────────────
        # The YGK evaluator is the authoritative decision-maker.
        # Rejection requires an explicit signal:
        #   • rejection_override=True  (UI detected any "Not Met" condition)
        #   • portfolio_result == "Failed"  (evaluator failed portfolio review)
        #   • rejection_justification has actual text  (evaluator wrote a reason)
        # Anything else is an approval — automated checks are informational only
        # (CORE_COURSE rules always fail automated eval and require human review).
        evaluator_rejects = (
            rejection_override
            or portfolio_result == "Failed"
            or bool(rejection_justification and rejection_justification.strip())
        )
        all_passed = not evaluator_rejects

        evaluation = DepartmentEvaluation(
            application_id=application_id,
            evaluator_id=evaluator_id,
            passed=all_passed,
            notes=rejection_justification or notes,
            evaluated_at=datetime.now(timezone.utc),
        )
        self.db.add(evaluation)
        await self.db.flush()

        log = AuditLog(
            actor_id=evaluator_id,
            action="DEPT_CONDITIONS_EVALUATED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": app.status.value},
            new_value={
                "passed": all_passed,
                "portfolio_result": portfolio_result,
                "rejection_justification": rejection_justification,
                "rejection_override": rejection_override,
                "checks": len(checks),
            },
        )
        self.db.add(log)
        await self.db.flush()

        if all_passed:
            await self._app_svc.change_status(
                application_id, AppStatus.ENGLISH_REVIEW, evaluator_id,
                "Department conditions confirmed by YGK — forwarded to YDYO for English review",
            )
        else:
            rejection_note = (
                rejection_justification.strip()
                if rejection_justification and rejection_justification.strip()
                else (notes or "Department conditions not met")
            )
            await self._app_svc.change_status(
                application_id, AppStatus.REJECTED, evaluator_id,
                rejection_note,
            )

        return {
            "evaluation": {
                "passed": all_passed,
                "notes": notes,
                "evaluated_at": evaluation.evaluated_at.isoformat(),
            },
            "checks": [
                {"rule_key": c.rule_key, "passed": c.passed, "detail": c.detail}
                for c in checks
            ],
        }

    async def manual_course_mapping(
        self,
        application_id: uuid.UUID,
        external_course: str,
        rule_key: str,
        evaluator_id: uuid.UUID,
    ) -> EligibilityCheck:
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")

        existing = next(
            (c for c in app.eligibility_checks if c.rule_key == rule_key), None
        )

        detail = f"Manual course mapping: {external_course} → rule {rule_key} satisfied"
        if existing:
            existing.passed = True
            existing.detail = detail
            await self.db.flush()
            check = existing
        else:
            check = EligibilityCheck(
                application_id=application_id,
                rule_key=rule_key,
                passed=True,
                detail=detail,
            )
            self.db.add(check)
            await self.db.flush()

        log = AuditLog(
            actor_id=evaluator_id,
            action="MANUAL_COURSE_MAPPING",
            entity_type="EligibilityCheck",
            entity_id=check.id,
            old_value={},
            new_value={"external_course": external_course, "rule_key": rule_key},
        )
        self.db.add(log)
        await self.db.flush()

        return check

    # ------------------------------------------------------------------

    def _evaluate_rule(
        self,
        req: DepartmentRequirement,
        record,
        app,
    ) -> tuple[bool, str]:
        key = req.rule_key
        val = req.rule_value

        try:
            if key == "MIN_GPA":
                min_val = float(val)
                if record is None or record.gpa_4 is None:
                    return False, "GPA data not available"
                gpa = float(record.gpa_4)
                if gpa >= min_val:
                    return True, f"GPA {gpa:.2f} >= minimum {min_val:.2f}"
                return False, f"GPA {gpa:.2f} < minimum {min_val:.2f}"

            elif key == "MIN_YKS":
                min_val = float(val)
                if record is None or record.yks_score is None:
                    return False, "YKS score data not available"
                score = float(record.yks_score)
                if score >= min_val:
                    return True, f"YKS {score:.3f} >= minimum {min_val:.3f}"
                return False, f"YKS {score:.3f} < minimum {min_val:.3f}"

            elif key == "MIN_CREDITS":
                min_val = int(val)
                if record is None or record.credits_completed is None:
                    return False, "Credit data not available"
                if record.credits_completed >= min_val:
                    return True, f"Credits {record.credits_completed} >= minimum {min_val}"
                return False, f"Credits {record.credits_completed} < minimum {min_val}"

            elif key == "REQUIRED_DOC":
                from app.domain.enums import DocStatus, DocType
                try:
                    doc_type = DocType(val)
                except ValueError:
                    return False, f"Unknown document type: {val}"
                matching = [
                    d for d in app.documents
                    if d.doc_type == doc_type and d.status == DocStatus.ACCEPTED
                ]
                if matching:
                    return True, f"Required document {val} present and accepted"
                return False, f"Required document {val} missing or not accepted"

            elif key == "PORTFOLIO_REQUIRED":
                required = val.upper() == "TRUE"
                if not required:
                    return True, "Portfolio not required"
                from app.domain.enums import DocType
                has_portfolio = any(
                    d.doc_type == DocType.OTHER for d in app.documents
                )
                if has_portfolio:
                    return True, "Portfolio document submitted"
                return False, "Portfolio document required but not submitted"

            elif key == "CORE_COURSE_GRADE":
                return False, "Requires manual evaluation — CORE_COURSE_GRADE rule"

            else:
                return True, f"Rule {key} evaluated (no specific check)"

        except Exception as e:
            return False, f"Evaluation error: {str(e)}"
