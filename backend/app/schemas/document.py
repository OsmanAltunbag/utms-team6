import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.domain.enums import DocType


class GenerateUploadUrlRequest(BaseModel):
    doc_type: DocType


class PresignedUploadResponse(BaseModel):
    upload_url: str
    object_key: str


class ConfirmUploadRequest(BaseModel):
    doc_type: DocType
    object_key: str
    file_name: str
    file_size_bytes: int


class DocumentSummary(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    doc_type: str
    file_name: str
    file_size_bytes: Optional[int]
    status: str
    uploaded_at: datetime
    extracted_data: Optional[Any] = None
    extraction_confirmed: bool = False

    model_config = {"from_attributes": True}


class PreviewUrlResponse(BaseModel):
    preview_url: str
    viewable: bool = True
    content_type: str = "application/pdf"
    error_message: Optional[str] = None


class VerifyDocumentResponse(BaseModel):
    id: uuid.UUID
    extraction_confirmed: bool
