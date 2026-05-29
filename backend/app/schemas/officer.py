import uuid

from datetime import datetime

from typing import List, Optional



from pydantic import BaseModel, Field



from app.schemas.application import ApplicationDetailResponse, EligibilityCheckResponse

from app.schemas.document import DocumentSummary





class AutoValidationResult(BaseModel):

    rule_key: str

    passed: bool

    detail: Optional[str] = None





class ApplicantProfileResponse(BaseModel):

    first_name: str

    last_name: str

    email: str

    national_id: str

    phone: Optional[str] = None





class ApplicationSummaryWithValidation(BaseModel):

    id: uuid.UUID

    program_id: uuid.UUID

    period_id: uuid.UUID

    status: str

    display_status: str

    tracking_number: Optional[str]

    submitted_at: Optional[datetime]

    created_at: datetime

    auto_validation_results: List[AutoValidationResult]



    model_config = {"from_attributes": True}





class OfficerApplicationDetailResponse(ApplicationDetailResponse):

    display_status: str

    correction_deadline: Optional[datetime] = None

    applicant: ApplicantProfileResponse

    documents: List[DocumentSummary]

    auto_validation_results: List[AutoValidationResult]





class RequestCorrectionRequest(BaseModel):

    note: str = Field(..., min_length=1)





class RejectApplicationRequest(BaseModel):

    reason_code: str

    note: str = ""





class OfficerActionResponse(BaseModel):

    application_id: uuid.UUID

    status: str

    display_status: str





class ResubmitCorrectionResponse(BaseModel):

    application_id: uuid.UUID

    status: str

    display_status: str


class ApplicantResultEntry(BaseModel):

    application_id: uuid.UUID

    tracking_number: Optional[str]

    first_name: str

    last_name: str

    email: str

    position: int

    composite_score: float

    result_label: str


class ResultsListResponse(BaseModel):

    period_id: uuid.UUID

    program_id: uuid.UUID

    program_name: str

    period_label: str

    ranking_status: str

    published_at: Optional[datetime] = None

    is_read_only: bool = True

    can_publish: bool

    primary: List[ApplicantResultEntry]

    waitlisted: List[ApplicantResultEntry]


class PublishResultsResponse(BaseModel):

    announced_count: int

    notifications_enqueued: int

    published_at: datetime

