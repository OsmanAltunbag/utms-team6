"""
SPEC-016: Approve Transfer Application (Dean's Final Decision)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.application import Application
from app.domain.audit import AuditLog
from app.domain.enums import AppStatus
from app.domain.user import Applicant
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

DEAN_REJECTION_LABELS: dict[str, str] = {
    "INSUFFICIENT_ACADEMIC_STANDING": (
        "Failure to meet the grade point average requirement."
    ),
    "QUOTA_LIMIT_REACHED": "Program quota limit has been reached.",
    "DISCIPLINARY_RECORD": "Disciplinary record on file.",
    "UNSUITABLE_PROGRAM_MATCH": "Unsuitable program match.",
    "OTHER": "Other reason (see note).",
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
        """Returns every application that has entered the dean's review cycle:

          - RANKING                                        → pending dean decision
          - DEAN_APPROVED / ANNOUNCED                      → dean-approved (final)
          - REJECTED **with a DEAN_FINAL_REJECTED audit log** → dean-rejected (final)

        REJECTED apps that were rejected earlier in the pipeline (e.g. UC-05-02
        failed English exam) are intentionally excluded so they don't pollute
        the dean's screen.
        """
        dean_rejected_subq = (
            select(AuditLog.entity_id)
            .where(AuditLog.action == "DEAN_FINAL_REJECTED")
            .scalar_subquery()
        )

        q = (
            select(Application)
            .options(
                selectinload(Application.applicant).selectinload(Applicant.user),
                selectinload(Application.program),
                selectinload(Application.period),
                selectinload(Application.ranking_entry),
                selectinload(Application.intibak_table),
                selectinload(Application.academic_record),
            )
            .where(
                or_(
                    Application.status == AppStatus.RANKING,
                    Application.status == AppStatus.DEAN_APPROVED,
                    Application.status == AppStatus.ANNOUNCED,
                    and_(
                        Application.status == AppStatus.REJECTED,
                        Application.id.in_(dean_rejected_subq),
                    ),
                )
            )
            .order_by(Application.submitted_at.desc().nulls_last())
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
                selectinload(Application.applicant).selectinload(Applicant.user),
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
            application_id,
            AppStatus.DEAN_APPROVED,
            approver_id,
            "Dean's final approval — routed to Student Affairs for announcement",
        )

        log = AuditLog(
            actor_id=approver_id,
            action="DEAN_FINAL_APPROVED",
            entity_type="Application",
            entity_id=application_id,
            old_value={"status": AppStatus.RANKING.value},
            new_value={
                "status": AppStatus.DEAN_APPROVED.value,
                "routed_to": "STUDENT_AFFAIRS",
                "ip_address": ip_address,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="Dekanlık Onayı",
            next_steps=(
                "Transfer başvurunuz Dekanlık tarafından onaylandı. "
                "Sonuç Öğrenci İşleri tarafından ilan edilecektir."
            ),
        )
        return app

    async def reject_final(
        self,
        application_id: uuid.UUID,
        approver_id: uuid.UUID,
        rejection_code: str,
        note: str,
        ip_address: str,
    ) -> tuple[Application, AuditLog, str]:
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

        rejection_reason = DEAN_REJECTION_LABELS[rejection_code]
        status_note = f"Dean's final rejection — {rejection_reason}"
        if note.strip():
            status_note = f"{status_note} ({note.strip()})"

        await self._app_svc.change_status(
            application_id,
            AppStatus.REJECTED,
            approver_id,
            status_note,
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
                "rejection_reason": rejection_reason,
                "note": note,
                "ip_address": ip_address,
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()

        await self._notify(
            app,
            decision="Transfer Rejected",
            next_steps=(
                f"Transfer başvurunuz Dekanlık tarafından reddedildi. "
                f"Sebep: {rejection_reason}"
            ),
        )
        return app, log, rejection_reason

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
