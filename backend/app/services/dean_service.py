"""
SPEC-016: Approve Transfer Application (Dean's Final Decision)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.application import Application
from app.domain.audit import AuditLog
from app.domain.enums import AppStatus
from app.repositories.application_repository import ApplicationRepository
from app.services.application_service import ApplicationService
from app.services.notification_service import NotificationService


_VALID_REJECTION_CODES = {
    "INSUFFICIENT_ACADEMIC_STANDING",
    "QUOTA_LIMIT_REACHED",
    "DISCIPLINARY_RECORD",
    "UNSUITABLE_PROGRAM_MATCH",
    "OTHER",
}


class DeanOfficeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._app_svc = ApplicationService(db)

    async def list_applications(
        self,
        program_id: Optional[uuid.UUID] = None,
        period_id: Optional[uuid.UUID] = None,
    ) -> list[Application]:
        q = (
            select(Application)
            .options(
                selectinload(Application.applicant),
                selectinload(Application.program),
                selectinload(Application.period),
                selectinload(Application.ranking_entry),
                selectinload(Application.intibak_table),
                selectinload(Application.academic_record),
            )
            .where(Application.status == AppStatus.RANKING)
        )
        if program_id:
            q = q.where(Application.program_id == program_id)
        if period_id:
            q = q.where(Application.period_id == period_id)

        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_application_detail(self, application_id: uuid.UUID) -> Application:
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.applicant),
                selectinload(Application.program),
                selectinload(Application.period),
                selectinload(Application.academic_record),
                selectinload(Application.documents),
                selectinload(Application.eligibility_checks),
                selectinload(Application.department_evaluations),
                selectinload(Application.english_proficiency_review),
                selectinload(Application.ranking_entry),
                selectinload(Application.intibak_table),
            )
            .where(Application.id == application_id)
        )
        app = result.scalar_one_or_none()
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        return app

    async def approve_final(
        self,
        application_id: uuid.UUID,
        approver_id: uuid.UUID,
        ip_address: str,
    ) -> Application:
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.RANKING:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected RANKING, got {app.status.value}",
            )

        await self._app_svc.change_status(
            application_id, AppStatus.ANNOUNCED, approver_id,
            "Dean's final approval — Transfer Accepted"
        )

        log = AuditLog(
            actor_id=approver_id,
            action="DEAN_FINAL_APPROVED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.RANKING.value},
            new_value={
                "status": AppStatus.ANNOUNCED.value,
                "ip_address": ip_address,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="Onaylandı",
            next_steps="Tebrikler! Transfer başvurunuz Dekanlık tarafından onaylandı. Kayıt tarihlerine dikkat ediniz.",
        )
        return app

    async def reject_final(
        self,
        application_id: uuid.UUID,
        approver_id: uuid.UUID,
        rejection_code: str,
        note: str,
        ip_address: str,
    ) -> Application:
        if rejection_code not in _VALID_REJECTION_CODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid rejection_code. Valid: {sorted(_VALID_REJECTION_CODES)}",
            )
        app = await self._app_repo.get_by_id(application_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if app.status != AppStatus.RANKING:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Expected RANKING, got {app.status.value}",
            )

        await self._app_svc.change_status(
            application_id, AppStatus.REJECTED, approver_id,
            f"Dean's final rejection — {rejection_code}: {note}"
        )

        log = AuditLog(
            actor_id=approver_id,
            action="DEAN_FINAL_REJECTED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.RANKING.value},
            new_value={
                "status": AppStatus.REJECTED.value,
                "rejection_code": rejection_code,
                "note": note,
                "ip_address": ip_address,
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="Reddedildi",
            next_steps=f"Transfer başvurunuz Dekanlık tarafından reddedildi. Sebep: {rejection_code}",
        )
        return app

    async def _notify(
        self, app: Application, decision: str, next_steps: str
    ) -> None:
        notif_svc = NotificationService(self.db)
        await notif_svc.enqueue(
            user_id=app.applicant_id,
            subject="UTMS — Dekanlık Kararı",
            application_id=app.id,
            template="dean_decision",
            template_vars={
                "decision": decision,
                "next_steps": next_steps,
                "title": "Dekanlık Kararı",
            },
        )
