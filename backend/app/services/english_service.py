"""
SPEC-014: Approve English Proficiency
SPEC-015: Announce English Proficiency Exam Results
"""
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import AuditLog
from app.domain.english import EnglishProficiencyReview
from app.domain.enums import AppStatus
from app.repositories.application_repository import ApplicationRepository
from app.services.application_service import ApplicationService


_VALID_REJECTION_REASONS = {
    "EXPIRED_EXAM",
    "INSUFFICIENT_SCORE",
    "UNVERIFIABLE_DOCUMENT",
    "OTHER",
}


class EnglishProficiencyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._app_svc = ApplicationService(db)

    async def approve(
        self,
        application_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        exam_type: str,
        exam_score: float,
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
        review.exam_score = Decimal(str(exam_score))
        review.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()

        await self._app_svc.change_status(
            application_id, AppStatus.DEPT_EVAL, reviewer_id, "English proficiency approved"
        )

        log = AuditLog(
            actor_id=reviewer_id,
            action="ENGLISH_APPROVED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.ENGLISH_REVIEW.value},
            new_value={"status": AppStatus.DEPT_EVAL.value, "exam_type": exam_type, "exam_score": exam_score},
        )
        self.db.add(log)
        await self.db.flush()

        self._notify(app, "İngilizce yeterlilik onaylandı. Bölüm değerlendirmesine geçildi.")
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

        self._notify(app, f"İngilizce yeterlilik reddedildi. Sebep: {rejection_reason}")
        return review

    # ------------------------------------------------------------------
    # SPEC-015: Bulk exam results
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

    def _notify(self, app, message: str) -> None:
        try:
            from app.domain.notification import Notification
            from app.domain.enums import NotifChannel, NotifStatus
            notif = Notification(
                user_id=app.applicant_id,
                application_id=app.id,
                channel=NotifChannel.EMAIL,
                subject="UTMS — İngilizce Yeterlilik Sonucu",
                body=message,
                status=NotifStatus.PENDING,
            )
            self.db.add(notif)
        except Exception:
            pass
