import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    application_id: Optional[uuid.UUID] = None


class ReplyCreate(BaseModel):
    body: str = Field(min_length=1)


class ReplyOut(BaseModel):
    id: uuid.UUID
    body: str
    staff_name: str
    created_at: datetime


class QuestionOut(BaseModel):
    id: uuid.UUID
    subject: str
    body: str
    application_id: Optional[uuid.UUID]
    applicant_name: Optional[str] = None
    is_resolved: bool
    created_at: datetime
    replies: List[ReplyOut] = []
