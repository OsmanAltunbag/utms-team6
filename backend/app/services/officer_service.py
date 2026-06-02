"""
SPEC-006: Student Affairs — Oversee Application Documents
SPEC-007: Student Affairs — Notify Transfer Results
"""
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.application import Application
from app.domain.audit import AuditLog
from app.domain.enums import AppStatus, RankStatus
from app.domain.ranking import Ranking
from app.repositories.application_repository import ApplicationRepository
from app.services.application_service import ApplicationService


_VALID_REJECTION_CODES = {
    "INVALID_DOCUMENT",
    "FRAUDULENT_DOCUMENT",
    "DUPLICATE_APPLICATION",
    "MISSED_DEADLINE",
    "OTHER",
}


class OfficerApplicationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._app_svc = ApplicationService(db)

    async def list_applications(
        self,
        status_filter: Optional[AppStatus] = None,
        program_id: Optional[uuid.UUID] = None,
        period_id: Optional[uuid.UUID] = None,
    ) -> list[Application]:
        from app.domain.application import Application as App
        q = (
            select(App)
            .options(
                selectinload(App.applicant),
                selectinload(App.program),
                selectinload(App.period),
                selectinload(App.documents),
                selectinload(App.eligibility_checks),
            )
        )
        if status_filter is not None:
            q = q.where(App.status == status_filter)
        if program_id is not None:
            q = q.where(App.program_id == program_id)
        if period_id is not None:
            q = q.where(App.period_id == period_id)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def approve_verification(
        self,
        application_id: uuid.UUID,
        officer_id: uuid.UUID,
    ) -> Application:
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected SUBMITTED, got {app.status.value}",
            )

        await self._app_svc.change_status(
            application_id, AppStatus.UNDER_REVIEW, officer_id, "Documents verified"
        )

        log = AuditLog(
            actor_id=officer_id,
            action="DOCUMENT_VERIFIED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.SUBMITTED.value},
            new_value={"status": AppStatus.UNDER_REVIEW.value},
        )
        self.db.add(log)
        await self.db.flush()

        self._enqueue_status_notification(app, officer_id, "Belgeleriniz doğrulandı.")
        return app

    async def request_correction(
        self,
        application_id: uuid.UUID,
        officer_id: uuid.UUID,
        note: str,
    ) -> Application:
        if not note or not note.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Correction note is required",
            )
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected SUBMITTED, got {app.status.value}",
            )

        await self._app_svc.change_status(
            application_id, AppStatus.CORRECTION_REQUESTED, officer_id, note
        )

        log = AuditLog(
            actor_id=officer_id,
            action="CORRECTION_REQUESTED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.SUBMITTED.value},
            new_value={"status": AppStatus.CORRECTION_REQUESTED.value, "note": note},
        )
        self.db.add(log)
        await self.db.flush()

        self._enqueue_status_notification(
            app, officer_id, f"Başvurunuzda düzeltme istendi: {note}"
        )
        return app

    async def reject_application(
        self,
        application_id: uuid.UUID,
        officer_id: uuid.UUID,
        reason_code: str,
        note: str,
    ) -> Application:
        if reason_code not in _VALID_REJECTION_CODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid reason_code. Valid: {sorted(_VALID_REJECTION_CODES)}",
            )
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status not in (AppStatus.SUBMITTED, AppStatus.UNDER_REVIEW, AppStatus.CORRECTION_REQUESTED):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot reject application in status {app.status.value}",
            )

        await self._app_svc.change_status(
            application_id, AppStatus.REJECTED, officer_id, f"{reason_code}: {note}"
        )

        log = AuditLog(
            actor_id=officer_id,
            action="APPLICATION_REJECTED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": app.status.value},
            new_value={"status": AppStatus.REJECTED.value, "reason_code": reason_code, "note": note},
        )
        self.db.add(log)
        await self.db.flush()

        self._enqueue_status_notification(
            app, officer_id, f"Başvurunuz reddedildi. Sebep: {reason_code}"
        )
        return app

    # ------------------------------------------------------------------
    # SPEC-007: Publish transfer results
    # ------------------------------------------------------------------

    async def publish_results(
        self,
        period_id: uuid.UUID,
        program_id: uuid.UUID,
        officer_id: uuid.UUID,
    ) -> dict:
        from app.domain.ranking import Ranking

        ranking_result = await self.db.execute(
            select(Ranking).where(
                Ranking.program_id == program_id,
                Ranking.period_id == period_id,
            )
        )
        ranking = ranking_result.scalar_one_or_none()

        if ranking is None or ranking.status != RankStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ranking must be APPROVED before publishing results",
            )
        if ranking.published_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Results already published",
            )

        apps_result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.applicant))
            .where(
                Application.program_id == program_id,
                Application.period_id == period_id,
                Application.status == AppStatus.RANKING,
            )
        )
        apps = list(apps_result.scalars().all())

        from datetime import datetime, timezone
        for app in apps:
            app.status = AppStatus.ANNOUNCED
            self._enqueue_status_notification(app, officer_id, "Transfer sonuçlarınız açıklandı.")

        ranking.published_at = datetime.now(timezone.utc)
        await self.db.flush()

        log = AuditLog(
            actor_id=officer_id,
            action="RESULTS_PUBLISHED",
            entity_type="Ranking",
            entity_id=ranking.id,
            old_value={"published_at": None},
            new_value={"announced_count": len(apps)},
        )
        self.db.add(log)
        await self.db.flush()

        return {"announced_count": len(apps)}

    async def get_results(
        self,
        period_id: uuid.UUID,
        program_id: uuid.UUID,
    ) -> dict:
        from app.domain.ranking import Ranking, RankingEntry

        ranking_result = await self.db.execute(
            select(Ranking)
            .options(selectinload(Ranking.entries))
            .where(
                Ranking.program_id == program_id,
                Ranking.period_id == period_id,
            )
        )
        ranking = ranking_result.scalar_one_or_none()
        if ranking is None:
            raise HTTPException(status_code=404, detail="Ranking not found")

        primary = [e for e in ranking.entries if e.is_primary]
        waitlisted = [e for e in ranking.entries if not e.is_primary]
        return {"primary": primary, "waitlisted": waitlisted, "ranking": ranking}

    # ------------------------------------------------------------------

    def _enqueue_status_notification(
        self, app: Application, actor_id: uuid.UUID, message: str
    ) -> None:
        try:
            from app.workers.notification_tasks import send_notification
            from app.domain.notification import Notification
            from app.domain.enums import NotifChannel, NotifStatus

            notif = Notification(
                user_id=app.applicant_id,
                application_id=app.id,
                channel=NotifChannel.EMAIL,
                subject="UTMS — Başvuru Durumu Güncellendi",
                body=message,
                status=NotifStatus.PENDING,
            )
            self.db.add(notif)
            # Task will be sent after commit via send_notification.delay
        except Exception:
            pass
