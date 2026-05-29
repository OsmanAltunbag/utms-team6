import logging
import uuid
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotifChannel, NotifStatus
from app.domain.notification import Notification
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = NotificationRepository(db)

    async def enqueue(
        self,
        user_id: uuid.UUID,
        subject: str,
        body: str,
        application_id: uuid.UUID | None = None,
        channel: NotifChannel = NotifChannel.EMAIL,
        template_name: str | None = None,
        template_context: dict[str, Any] | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            application_id=application_id,
            channel=channel,
            subject=subject,
            body=body,
            template_name=template_name,
            template_context=template_context,
            status=NotifStatus.PENDING,
        )
        await self._repo.save(notification)
        self._dispatch(notification.id)
        return notification

    async def enqueue_bulk(
        self,
        items: list[dict[str, Any]],
    ) -> int:
        """
        Create many notifications and dispatch Celery tasks.
        Used for bulk result publication (SRS: 1000 within 5 minutes).
        Each item dict must include: user_id, subject, body,
        and optionally application_id, template_name, template_context.
        """
        notifications: list[Notification] = []
        for item in items:
            notification = Notification(
                user_id=item["user_id"],
                application_id=item.get("application_id"),
                channel=item.get("channel", NotifChannel.EMAIL),
                subject=item["subject"],
                body=item["body"],
                template_name=item.get("template_name"),
                template_context=item.get("template_context"),
                status=NotifStatus.PENDING,
            )
            notifications.append(notification)
            self.db.add(notification)

        await self.db.flush()

        for notification in notifications:
            self._dispatch(notification.id)

        return len(notifications)

    async def get_delivery_log(self, application_id: uuid.UUID) -> List[Notification]:
        return await self._repo.get_by_application(application_id)

    def _dispatch(self, notification_id: uuid.UUID) -> None:
        try:
            from app.workers.notification_tasks import send_notification

            send_notification.delay(str(notification_id))
        except Exception:
            logger.warning(
                "Failed to enqueue notification task for %s",
                notification_id,
            )
