import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notification import Notification
from app.domain.enums import NotifStatus


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        return await self.db.get(Notification, notification_id)

    async def get_by_application(self, application_id: uuid.UUID) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.application_id == application_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def save(self, notification: Notification) -> None:
        self.db.add(notification)
        await self.db.flush()
