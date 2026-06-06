import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.audit import AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # Actions that appear in the applicant "Status History" / workflow log.
    _WORKFLOW_ACTIONS = (
        "STATUS_CHANGED",
        "DEAN_FINAL_APPROVED",
        "DEAN_FINAL_REJECTED",
        "ENGLISH_APPROVED",
        "ENGLISH_REJECTED",
        "ENGLISH_ROUTED_TO_EXAM",
        "RESULT_ANNOUNCED",
        "DOCUMENT_VERIFIED",
        "APPLICATION_REJECTED",
    )

    async def get_status_history(self, application_id: uuid.UUID) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog)
            .options(joinedload(AuditLog.actor))
            .where(
                AuditLog.entity_type == "Application",
                AuditLog.entity_id == application_id,
                AuditLog.action.in_(self._WORKFLOW_ACTIONS),
            )
            .order_by(AuditLog.created_at.desc())
        )
        return list(result.scalars().all())
