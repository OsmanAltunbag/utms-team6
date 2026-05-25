import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.audit import AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_status_history(self, application_id: uuid.UUID) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog)
            .options(joinedload(AuditLog.actor))
            .where(
                AuditLog.entity_type == "Application",
                AuditLog.entity_id == application_id,
                AuditLog.action == "STATUS_CHANGED",
            )
            .order_by(AuditLog.created_at.desc())
        )
        return list(result.scalars().all())
