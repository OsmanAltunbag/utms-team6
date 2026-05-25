import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from app.domain.enums import AppStatus


class CreateApplicationRequest(BaseModel):
    program_id: uuid.UUID
    period_id: uuid.UUID


class ApplicationCreatedResponse(BaseModel):
    application_id: uuid.UUID
    status: str


class ApplicationSummary(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    period_id: uuid.UUID
    status: str
    tracking_number: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AcademicRecordResponse(BaseModel):
    institution: Optional[str]
    gpa_4: Optional[Decimal]
    gpa_100: Optional[Decimal]
    yks_score: Optional[Decimal]
    credits_completed: Optional[int]
    fetched_at: Optional[datetime]
    source: Optional[str]
    errors: Optional[List[str]] = None

    model_config = {"from_attributes": True}


class EligibilityCheckResponse(BaseModel):
    rule_key: str
    passed: bool
    detail: Optional[str]

    model_config = {"from_attributes": True}


class ApplicationDetailResponse(BaseModel):
    id: uuid.UUID
    applicant_id: uuid.UUID
    program_id: uuid.UUID
    period_id: uuid.UUID
    status: str
    tracking_number: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    progress: dict
    eligibility_checks: List[EligibilityCheckResponse]

    model_config = {"from_attributes": True}


class SubmitApplicationResponse(BaseModel):
    tracking_number: str
    status: str


class StatusChangeRequest(BaseModel):
    new_status: AppStatus
    note: Optional[str] = None
