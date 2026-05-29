import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save(self, notification: Notification) -> Notification:
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def get_by_application(self, application_id: uuid.UUID) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.application_id == application_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())
