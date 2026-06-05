import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotifChannel, NotifStatus
from app.domain.notification import Notification
from app.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = NotificationRepository(db)

    async def enqueue(
        self,
        user_id: uuid.UUID,
        subject: str,
        body: str,
        application_id: Optional[uuid.UUID] = None,
        channel: NotifChannel = NotifChannel.EMAIL,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            application_id=application_id,
            channel=channel,
            subject=subject,
            body=body,
            status=NotifStatus.PENDING,
        )
        await self._repo.save(notification)

        try:
            from app.workers.notification_tasks import send_notification
            send_notification.delay(str(notification.id))
        except Exception:
            pass

        return notification

    async def get_delivery_log(
        self, application_id: uuid.UUID
    ) -> list[Notification]:
        return await self._repo.get_by_application(application_id)
