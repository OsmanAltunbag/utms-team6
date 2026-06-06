import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.application import ApplicationDetailResponse, ApplicationSummary
from app.schemas.document import DocumentSummary


class AutoValidationResult(BaseModel):
    doc_type: str
    check: str
    passed: bool
    detail: Optional[str] = None


class StaffApplicationSummary(ApplicationSummary):
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    auto_validation_results: List[AutoValidationResult] = []


class StaffApplicationDetail(ApplicationDetailResponse):
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    documents: List[DocumentSummary] = []
