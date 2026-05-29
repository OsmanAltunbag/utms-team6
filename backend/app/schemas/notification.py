import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class NotificationLogEntry(BaseModel):
    id: uuid.UUID
    channel: str
    subject: Optional[str]
    status: str
    retry_count: int
    sent_at: Optional[datetime]
    created_at: datetime
    template_name: Optional[str]
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class NotificationLogResponse(BaseModel):
    application_id: uuid.UUID
    notifications: list[NotificationLogEntry]
