"""
SPEC-014: Approve English Proficiency
SPEC-015: Announce English Proficiency Exam Results
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import AuditLog
from app.domain.english import EnglishProficiencyReview
from app.domain.enums import AppStatus
from app.repositories.application_repository import ApplicationRepository
from app.services.application_service import ApplicationService
from app.services.notification_service import NotificationService


_VALID_REJECTION_REASONS = {
    "EXPIRED_EXAM",
    "INSUFFICIENT_SCORE",
    "UNVERIFIABLE_DOCUMENT",
    "OTHER",
}

# Required score thresholds per English proficiency exam, used by
# record_exam_result() to compute the Pass/Fail flag shown on the
# publication preview screen.
_REQUIRED_SCORE: dict[str, float] = {
    "TOEFL_IBT": 80,
    "TOEFL": 80,
    "IELTS": 6.5,
    "YDS": 65,
    "YOKDIL": 65,
    "IZTECH_EXAM": 70,
}


def required_score_for(exam_type: str | None) -> float | None:
    if exam_type is None:
        return None
    return _REQUIRED_SCORE.get(exam_type)


class EnglishProficiencyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._app_svc = ApplicationService(db)

    async def approve(
        self,
        application_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        exam_type: Optional[str] = None,
        exam_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> EnglishProficiencyReview:
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.ENGLISH_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected ENGLISH_REVIEW, got {app.status.value}",
            )

        from datetime import datetime, timezone
        review = app.english_proficiency_review
        if review is None:
            review = EnglishProficiencyReview(application_id=application_id)
            self.db.add(review)

        review.reviewer_id = reviewer_id
        review.approved = True
        review.exam_type = exam_type
        review.exam_score = Decimal(str(exam_score)) if exam_score is not None else None
        review.notes = notes
        review.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Route the approved applicant straight to the Dean's pending queue.
        # The intermediate DEPT_EVAL and ranking stages are auto-skipped in
        # this demo (no Faculty Commission UI yet); the dean is the next
        # decision-maker per UC-06-01.
        await self._app_svc.change_status(
            application_id, AppStatus.RANKING, reviewer_id, "English proficiency approved — sent to Dean's Office"
        )

        log = AuditLog(
            actor_id=reviewer_id,
            action="ENGLISH_APPROVED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.ENGLISH_REVIEW.value},
            new_value={"status": AppStatus.RANKING.value, "exam_type": exam_type, "exam_score": exam_score},
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="Onaylandı",
            reason="İngilizce yeterlilik onaylandı. Başvurunuz Dekanlık onayı bekliyor.",
        )
        return review

    async def route_to_exam(
        self,
        application_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        notes: str,
    ) -> EnglishProficiencyReview:
        """Soft-reject the certificate and route the applicant to the YDYO
        proficiency exam. The application stays in ENGLISH_REVIEW so that
        the officer can later publish an exam result via
        EnglishProficiencyService.publish_exam_results().
        """
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.ENGLISH_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected ENGLISH_REVIEW, got {app.status.value}",
            )

        from datetime import datetime, timezone
        review = app.english_proficiency_review
        if review is None:
            review = EnglishProficiencyReview(application_id=application_id)
            self.db.add(review)

        review.reviewer_id = reviewer_id
        review.approved = None  # decision is pending exam result
        review.must_take_exam = True
        review.notes = notes or "Certificate insufficient — routed to YDYO proficiency exam."
        review.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()

        log = AuditLog(
            actor_id=reviewer_id,
            action="ENGLISH_ROUTED_TO_EXAM",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.ENGLISH_REVIEW.value},
            new_value={"must_take_exam": True, "notes": review.notes},
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="YDYO Sınavına Yönlendirildi",
            reason=(
                "İngilizce sertifikanız yeterli görülmedi. Yeterlilik için "
                "YDYO proficiency sınavına girmeniz gerekmektedir."
            ),
        )
        return review

    async def reject(
        self,
        application_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        rejection_reason: str,
        notes: str,
    ) -> EnglishProficiencyReview:
        if rejection_reason not in _VALID_REJECTION_REASONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid rejection_reason. Valid: {sorted(_VALID_REJECTION_REASONS)}",
            )
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.ENGLISH_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected ENGLISH_REVIEW, got {app.status.value}",
            )

        from datetime import datetime, timezone
        review = app.english_proficiency_review
        if review is None:
            review = EnglishProficiencyReview(application_id=application_id)
            self.db.add(review)

        review.reviewer_id = reviewer_id
        review.approved = False
        review.notes = f"{rejection_reason}: {notes}"
        review.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()

        await self._app_svc.change_status(
            application_id, AppStatus.REJECTED, reviewer_id, f"English rejected: {rejection_reason}"
        )

        log = AuditLog(
            actor_id=reviewer_id,
            action="ENGLISH_REJECTED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.ENGLISH_REVIEW.value},
            new_value={"status": AppStatus.REJECTED.value, "reason": rejection_reason},
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="Reddedildi",
            reason=f"İngilizce yeterlilik reddedildi. Sebep: {rejection_reason}",
        )
        return review

    # ------------------------------------------------------------------
    # UC-05-02: Record + publish English proficiency exam results
    # ------------------------------------------------------------------

    async def record_exam_result(
        self,
        application_id: uuid.UUID,
        officer_id: uuid.UUID,
        score: float,
        exam_date_value: Optional[date] = None,
        exam_type: str = "IZTECH_EXAM",
    ) -> EnglishProficiencyReview:
        """Record an exam score for an applicant who was routed to the
        YDYO proficiency exam. Does NOT change application status — the
        score waits in 'Pending Publication' state until publish_pending()
        is called. Re-running on the same applicant replaces the score
        (so officers can correct a typo before publishing).
        """
        from datetime import datetime, timezone

        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.ENGLISH_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected ENGLISH_REVIEW, got {app.status.value}",
            )
        review = app.english_proficiency_review
        if review is None or not review.must_take_exam:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Applicant was not routed to the YDYO proficiency exam.",
            )
        if review.published_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Exam result is already published and cannot be modified.",
            )

        review.reviewer_id = officer_id
        review.exam_type = exam_type
        review.exam_score = Decimal(str(score))
        review.exam_date = exam_date_value or date.today()
        review.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()

        log = AuditLog(
            actor_id=officer_id,
            action="ENGLISH_EXAM_RECORDED",
            entity_type="Application",
            entity_id=application_id,
            old_value={},
            new_value={"exam_type": exam_type, "exam_score": score, "exam_date": review.exam_date.isoformat()},
        )
        self.db.add(log)
        await self.db.flush()
        return review

    async def publish_pending_exam_results(self, officer_id: uuid.UUID) -> dict:
        """Bulk-publish every applicant who currently has a scored but
        unpublished YDYO exam result. Publication is irreversible (SR1):
        passed → approve() → DEPT_EVAL; failed → reject() → REJECTED.
        Publication metadata (timestamp + officer) is stamped on each
        review row (SR2)."""
        from datetime import datetime, timezone
        from sqlalchemy import select

        result = await self.db.execute(
            select(EnglishProficiencyReview).where(
                EnglishProficiencyReview.must_take_exam.is_(True),
                EnglishProficiencyReview.exam_score.isnot(None),
                EnglishProficiencyReview.published_at.is_(None),
            )
        )
        pending = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        passed_count = 0
        failed_count = 0

        for review in pending:
            score_float = float(review.exam_score) if review.exam_score is not None else 0.0
            threshold = required_score_for(review.exam_type) or 0.0
            did_pass = score_float >= threshold

            try:
                if did_pass:
                    await self.approve(
                        review.application_id,
                        officer_id,
                        exam_type=review.exam_type or "IZTECH_EXAM",
                        exam_score=score_float,
                    )
                    passed_count += 1
                else:
                    await self.reject(
                        review.application_id,
                        officer_id,
                        rejection_reason="INSUFFICIENT_SCORE",
                        notes=f"YDYO proficiency exam failed (score {score_float} < {threshold}).",
                    )
                    failed_count += 1
            except HTTPException:
                # Already-decided rows or status conflicts: skip silently —
                # publication is best-effort per row.
                continue

            # Re-read review (approve/reject mutated approved + notes); stamp
            # publication metadata last so it survives.
            await self.db.refresh(review)
            review.published_at = now
            review.published_by = officer_id
            review.must_take_exam = True  # preserve audit trail
            await self.db.flush()

        log = AuditLog(
            actor_id=officer_id,
            action="EXAM_RESULTS_PUBLISHED",
            entity_type="EnglishExam",
            entity_id=officer_id,
            old_value={},
            new_value={
                "processed": passed_count + failed_count,
                "passed": passed_count,
                "failed": failed_count,
                "published_at": now.isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()
        return {
            "processed": passed_count + failed_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "published_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # SPEC-015: Bulk exam results (legacy, still used by per-row UI)
    # ------------------------------------------------------------------

    async def publish_exam_results(
        self,
        results: list[dict],
        officer_id: uuid.UUID,
    ) -> dict:
        """
        results: [{ "application_id": UUID, "score": float, "passed": bool }]
        """
        processed = 0
        passed_count = 0
        failed_count = 0

        for item in results:
            app_id = uuid.UUID(str(item["application_id"])) if isinstance(item["application_id"], str) else item["application_id"]
            score = float(item["score"])
            passed = bool(item["passed"])

            try:
                if passed:
                    await self.approve(
                        app_id, officer_id,
                        exam_type=item.get("exam_type", "IZTECH_EXAM"),
                        exam_score=score,
                    )
                    passed_count += 1
                else:
                    await self.reject(
                        app_id, officer_id,
                        rejection_reason=item.get("rejection_reason", "INSUFFICIENT_SCORE"),
                        notes=f"Score: {score}",
                    )
                    failed_count += 1
                processed += 1
            except Exception:
                pass

        log = AuditLog(
            actor_id=officer_id,
            action="EXAM_RESULTS_PUBLISHED",
            entity_type="EnglishExam",
            entity_id=officer_id,
            old_value={},
            new_value={"processed": processed, "passed": passed_count, "failed": failed_count},
        )
        self.db.add(log)
        await self.db.flush()

        return {"processed": processed, "passed_count": passed_count, "failed_count": failed_count}

    async def _notify(self, app, decision: str, reason: str) -> None:
        notif_svc = NotificationService(self.db)
        await notif_svc.enqueue(
            user_id=app.applicant_id,
            subject="UTMS — İngilizce Yeterlilik Kararı",
            application_id=app.id,
            template="english_decision",
            template_vars={
                "decision": decision,
                "reason": reason,
                "title": "İngilizce Yeterlilik Kararı",
            },
        )
