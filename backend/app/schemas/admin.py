import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.domain.enums import UserRole


class StaffCreateRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    department: Optional[str] = None
    title: Optional[str] = None


class RoleUpdateRequest(BaseModel):
    role: UserRole


class StaffResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    department: Optional[str]
    title: Optional[str]
    is_active: bool
    created_at: datetime
