import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotifChannel, NotifStatus
from app.domain.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.workers.template_renderer import build_templated_body, parse_notification_body

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = NotificationRepository(db)

    async def enqueue(
        self,
        user_id: uuid.UUID,
        subject: str,
        body: str = "",
        application_id: Optional[uuid.UUID] = None,
        channel: NotifChannel = NotifChannel.EMAIL,
        template: Optional[str] = None,
        template_vars: Optional[dict[str, Any]] = None,
    ) -> Notification:
        stored_body = (
            build_templated_body(template, **(template_vars or {}))
            if template
            else body
        )
        notification = Notification(
            user_id=user_id,
            application_id=application_id,
            channel=channel,
            subject=subject,
            body=stored_body,
            status=NotifStatus.PENDING,
        )
        await self._repo.save(notification)
        self._dispatch(notification.id)
        return notification

    async def get_delivery_log(
        self, application_id: uuid.UUID
    ) -> list[Notification]:
        return await self._repo.get_by_application(application_id)

    @staticmethod
    def display_message(body: str) -> str:
        """Human-readable message for API responses (strips template JSON)."""
        template_name, variables, plain = parse_notification_body(body)
        if plain:
            return plain
        if template_name == "dean_decision":
            decision = variables.get("decision", "Decision")
            next_steps = variables.get("next_steps", "")
            return f"{decision}. {next_steps}".strip()
        if variables.get("correction_note"):
            return str(variables["correction_note"])
        if variables.get("note"):
            return str(variables["note"])
        if variables.get("result"):
            return f"Result: {variables['result']}"
        if variables.get("decision"):
            return str(variables["decision"])
        try:
            import json
            data = json.loads(body)
            if isinstance(data, dict):
                if "correction_note" in data:
                    return str(data["correction_note"])
                if "note" in data:
                    return str(data["note"])
                if "result" in data:
                    return f"Result: {data['result']}"
        except (json.JSONDecodeError, TypeError):
            pass
        return "Notification"

    @staticmethod
    def _dispatch(notification_id: uuid.UUID) -> None:
        try:
            from app.workers.notification_tasks import send_notification
            send_notification.delay(str(notification_id))
        except Exception:
            logger.warning(
                "Failed to enqueue notification task for %s", notification_id, exc_info=True
            )
