import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.domain.enums import AppStatus, UserRole
from app.domain.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.application import (
    ApplicationCreatedResponse,
    ApplicationDetailResponse,
    ApplicationSummary,
    CreateApplicationRequest,
    EligibilityCheckResponse,
    StatusChangeRequest,
    SubmitApplicationResponse,
)
from app.schemas.document import (
    ConfirmUploadRequest,
    DocumentSummary,
    GenerateUploadUrlRequest,
    PresignedUploadResponse,
)
from app.core.storage import MinIOClient, get_minio_client
from app.domain.enums import DocType
from app.services.application_service import ApplicationService
from app.services.document_service import DocumentService

router = APIRouter()


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationCreatedResponse,
)
async def create_application(
    body: CreateApplicationRequest,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> ApplicationCreatedResponse:
    service = ApplicationService(db)
    application = await service.create_application(
        applicant_id=current_user.id,
        program_id=body.program_id,
        period_id=body.period_id,
    )
    return ApplicationCreatedResponse(
        application_id=application.id,
        status=application.status.value,
    )


@router.get("", response_model=List[ApplicationSummary])
async def list_applications(
    status_filter: Optional[AppStatus] = Query(None, alias="status"),
    program_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ApplicationSummary]:
    repo = ApplicationRepository(db)
    if current_user.role == UserRole.APPLICANT:
        apps = await repo.get_by_applicant(current_user.id)
    else:
        apps = await repo.get_all_filtered(status=status_filter, program_id=program_id)
    return [ApplicationSummary.model_validate(a) for a in apps]


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationDetailResponse:
    repo = ApplicationRepository(db)
    application = await repo.get_by_id(application_id)
    if application is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Application not found")

    if (
        current_user.role == UserRole.APPLICANT
        and application.applicant_id != current_user.applicant_profile.id
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return ApplicationDetailResponse(
        id=application.id,
        applicant_id=application.applicant_id,
        program_id=application.program_id,
        period_id=application.period_id,
        status=application.status.value,
        tracking_number=application.tracking_number,
        submitted_at=application.submitted_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
        progress=application.get_progress(),
        eligibility_checks=[
            EligibilityCheckResponse(
                rule_key=c.rule_key,
                passed=c.passed,
                detail=c.detail,
            )
            for c in application.eligibility_checks
        ],
    )


@router.post("/{application_id}/fetch-academic-data")
async def fetch_academic_data(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ApplicationService(db)
    return await service.fetch_academic_data(application_id)


@router.post("/{application_id}/submit", response_model=SubmitApplicationResponse)
async def submit_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> SubmitApplicationResponse:
    service = ApplicationService(db)
    application = await service.submit_application(application_id)
    return SubmitApplicationResponse(
        tracking_number=application.tracking_number,
        status=application.status.value,
    )


@router.post("/{application_id}/status")
async def change_status(
    application_id: uuid.UUID,
    body: StatusChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if current_user.role == UserRole.APPLICANT:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service = ApplicationService(db)
    application = await service.change_status(
        application_id=application_id,
        new_status=body.new_status,
        actor_id=current_user.id,
        note=body.note,
    )
    return {"application_id": str(application.id), "status": application.status.value}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/{application_id}/documents", response_model=List[DocumentSummary])
async def list_documents(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentSummary]:
    repo = DocumentRepository(db)
    docs = await repo.get_by_application(application_id)
    return [DocumentSummary.model_validate(d) for d in docs]


@router.post(
    "/{application_id}/documents/upload-url",
    response_model=PresignedUploadResponse,
)
async def generate_upload_url(
    application_id: uuid.UUID,
    body: GenerateUploadUrlRequest,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> PresignedUploadResponse:
    service = DocumentService(db)
    result = await service.generate_upload_url(application_id, body.doc_type)
    return PresignedUploadResponse(upload_url=result.upload_url, object_key=result.object_key)


@router.post(
    "/{application_id}/documents/confirm",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentSummary,
)
async def confirm_upload(
    application_id: uuid.UUID,
    body: ConfirmUploadRequest,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> DocumentSummary:
    service = DocumentService(db)
    document = await service.confirm_upload(
        application_id=application_id,
        doc_type=body.doc_type,
        object_key=body.object_key,
        file_name=body.file_name,
        file_size_bytes=body.file_size_bytes,
    )
    return DocumentSummary.model_validate(document)


@router.post(
    "/{application_id}/documents/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentSummary,
)
async def upload_document(
    application_id: uuid.UUID,
    doc_type: DocType = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
    storage: MinIOClient = Depends(get_minio_client),
) -> DocumentSummary:
    _MAX_SIZE = 5_242_880
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")
    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(status_code=422, detail="File exceeds 5 MB limit.")

    object_key = f"applications/{application_id}/{doc_type.value}/{uuid.uuid4()}.pdf"
    storage.put_object(object_key, content, "application/pdf")

    service = DocumentService(db)
    document = await service.confirm_upload(
        application_id=application_id,
        doc_type=doc_type,
        object_key=object_key,
        file_name=file.filename or f"{doc_type.value}.pdf",
        file_size_bytes=len(content),
    )
    return DocumentSummary.model_validate(document)

