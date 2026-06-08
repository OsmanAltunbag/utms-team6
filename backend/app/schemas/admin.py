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


class StaffCreateResponse(StaffResponse):
    temp_password: Optional[str] = None


# --- SPEC-018: Application Period schemas ---

class PeriodCreateRequest(BaseModel):
    label: str
    opens_at: datetime
    closes_at: datetime


class PeriodExtendRequest(BaseModel):
    new_closes_at: datetime


class PeriodUpdateRequest(BaseModel):
    label: Optional[str] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None


class PeriodResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    label: str
    opens_at: datetime
    closes_at: datetime
    is_active: bool
    created_by: Optional[uuid.UUID]
    created_at: datetime


# --- SPEC-019: Department Condition schemas ---

class ConditionCreateRequest(BaseModel):
    rule_key: str
    rule_value: str
    description: Optional[str] = None


class ConditionUpdateRequest(BaseModel):
    rule_value: Optional[str] = None
    is_active: Optional[bool] = None


class ConditionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    program_id: uuid.UUID
    rule_key: str
    rule_value: str
    description: Optional[str]
    is_active: bool
