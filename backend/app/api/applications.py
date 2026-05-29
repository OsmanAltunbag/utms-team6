import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.storage import MinIOClient, get_minio_client
from app.domain.enums import AppStatus, DocType, UserRole
from app.domain.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.application import (
    ApplicationCreatedResponse,
    ApplicationDetailResponse,
    ApplicationStatusResponse,
    ApplicationSummary,
    CreateApplicationRequest,
    EligibilityCheckResponse,
    HistoryEntry,
    ProgressOut,
    ResultOut,
    StageOut,
    StatusChangeRequest,
    SubmitApplicationResponse,
)
from app.schemas.officer import ResubmitCorrectionResponse
from app.schemas.notification import NotificationLogEntry, NotificationLogResponse
from app.schemas.document import (
    ConfirmUploadRequest,
    DocumentSummary,
    GenerateUploadUrlRequest,
    PresignedUploadResponse,
    VerifyDocumentResponse,
)
from app.services.application_service import ApplicationService
from app.services.document_service import DocumentService, is_allowed_upload, resolve_content_type
from app.services.notification_service import NotificationService
from app.core.status_labels import srs_display_status

_PIPELINE_STAGES = [
    {"name": "SUBMITTED",      "label_tr": "Başvuru Alındı",        "label_en": "Submitted"},
    {"name": "UNDER_REVIEW",   "label_tr": "Belge Doğrulama",       "label_en": "Document Verification"},
    {"name": "ENGLISH_REVIEW", "label_tr": "İngilizce Yeterliliği", "label_en": "English Proficiency"},
    {"name": "DEPT_EVAL",      "label_tr": "Bölüm Değerlendirmesi", "label_en": "Department Evaluation"},
    {"name": "RANKING",        "label_tr": "Sıralama",              "label_en": "Ranking"},
    {"name": "ANNOUNCED",      "label_tr": "Sonuç Açıklandı",       "label_en": "Result Announced"},
]
_STAGE_NAMES = [s["name"] for s in _PIPELINE_STAGES]

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


@router.get("/{application_id}/status", response_model=ApplicationStatusResponse)
async def get_application_status(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationStatusResponse:
    try:
        repo = ApplicationRepository(db)
        application = await repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        if (
            current_user.role == UserRole.APPLICANT
            and application.applicant_id != current_user.id
        ):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Build pipeline progress
        current_name = application.status.value
        # CORRECTION_REQUESTED is treated as active at UNDER_REVIEW stage
        effective = "UNDER_REVIEW" if current_name == "CORRECTION_REQUESTED" else current_name
        try:
            idx = _STAGE_NAMES.index(effective)
        except ValueError:
            idx = -1  # DRAFT or unknown: nothing completed yet

        stages = [
            StageOut(
                name=s["name"],
                label_tr=s["label_tr"],
                label_en=s["label_en"],
                completed=i < idx,
                active=i == idx,
            )
            for i, s in enumerate(_PIPELINE_STAGES)
        ]

        # Fetch audit history
        audit_repo = AuditLogRepository(db)
        logs = await audit_repo.get_status_history(application_id)
        history = [
            HistoryEntry(
                status=log.new_value.get("status", "") if log.new_value else "",
                changed_at=log.created_at,
                changed_by_role=log.actor.role.value if log.actor else None,
                note=log.new_value.get("note") if log.new_value else None,
            )
            for log in logs
        ]

        # Build result for terminal states
        result: Optional[ResultOut] = None
        if application.status == AppStatus.REJECTED:
            reason = history[0].note if history else None
            result = ResultOut(outcome="REJECTED", reason=reason)
        elif application.status == AppStatus.ANNOUNCED:
            if application.ranking_entry is not None:
                outcome = (
                    "ACCEPTED"
                    if application.ranking_entry.is_primary
                    else "WAITLISTED"
                )
            else:
                outcome = "REJECTED"
            result = ResultOut(outcome=outcome, reason=None)

        return ApplicationStatusResponse(
            tracking_number=application.tracking_number,
            status=current_name,
            progress=ProgressOut(stages=stages, current_stage=current_name),
            history=history,
            result=result,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve application information. Please try again later.",
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


@router.post(
    "/{application_id}/resubmit-correction",
    response_model=ResubmitCorrectionResponse,
)
async def resubmit_after_correction(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> ResubmitCorrectionResponse:
    service = ApplicationService(db)
    application = await service.resubmit_after_correction(
        application_id=application_id,
        applicant_id=current_user.id,
    )
    return ResubmitCorrectionResponse(
        application_id=application.id,
        status=application.status.value,
        display_status=srs_display_status(application.status),
    )


@router.get(
    "/{application_id}/notifications",
    response_model=NotificationLogResponse,
)
async def get_notification_log(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationLogResponse:
    """Communication / delivery log for an application (SPEC-020)."""
    app_repo = ApplicationRepository(db)
    application = await app_repo.get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if current_user.role == UserRole.APPLICANT:
        if application.applicant_id != current_user.id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    elif current_user.role not in {
        UserRole.STUDENT_AFFAIRS,
        UserRole.SYSTEM_ADMIN,
        UserRole.TRANSFER_COMMISSION,
        UserRole.YDYO,
        UserRole.DEAN_OFFICE,
    }:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    service = NotificationService(db)
    notifications = await service.get_delivery_log(application_id)
    return NotificationLogResponse(
        application_id=application_id,
        notifications=[NotificationLogEntry.model_validate(n) for n in notifications],
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
    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(status_code=422, detail="File exceeds 5 MB limit.")
    if not is_allowed_upload(file.filename or "", file.content_type):
        raise HTTPException(
            status_code=422,
            detail="Invalid file format. Please upload a PDF or image file (JPG/PNG).",
        )

    ext = ".pdf"
    if file.content_type in {"image/jpeg", "image/jpg"} or (file.filename or "").lower().endswith((".jpg", ".jpeg")):
        ext = ".jpg"
    elif file.content_type == "image/png" or (file.filename or "").lower().endswith(".png"):
        ext = ".png"

    upload_mime = resolve_content_type(file.filename or f"{doc_type.value}{ext}", file.content_type)
    object_key = f"applications/{application_id}/{doc_type.value}/{uuid.uuid4()}{ext}"
    storage.put_object(object_key, content, upload_mime)

    # Run extraction before persisting so we can store results immediately.
    # For doc types that support extraction, always store a dict (even empty)
    # so the frontend knows extraction was attempted and can prompt the user.
    _EXTRACTABLE = {
        DocType.TRANSCRIPT, DocType.YKS_RESULT,
        DocType.LANGUAGE_CERT, DocType.ID_COPY,
        DocType.MILITARY_STATUS, DocType.DISCIPLINE_RECORD,
    }
    extracted_data: dict | None = None
    if doc_type in _EXTRACTABLE:
        from app.external.document_extractor import DocumentExtractor
        try:
            extracted_data = await DocumentExtractor().extract(doc_type, content)
        except Exception:
            extracted_data = {}

    # Replace any previous upload of the same type so the frontend always
    # gets fresh extraction data when the user clicks "Replace".
    doc_repo = DocumentRepository(db)
    await doc_repo.delete_by_type(application_id, doc_type)

    service = DocumentService(db)
    document = await service.confirm_upload(
        application_id=application_id,
        doc_type=doc_type,
        object_key=object_key,
        file_name=file.filename or f"{doc_type.value}.pdf",
        file_size_bytes=len(content),
        extracted_data=extracted_data,
    )
    return DocumentSummary.model_validate(document)


@router.post(
    "/{application_id}/documents/{document_id}/verify",
    response_model=VerifyDocumentResponse,
)
async def verify_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.APPLICANT)),
    db: AsyncSession = Depends(get_db),
) -> VerifyDocumentResponse:
    repo = DocumentRepository(db)
    doc = await repo.get_by_id(document_id)
    if doc is None or doc.application_id != application_id:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.extraction_confirmed = True
    await db.commit()
    await db.refresh(doc)
    return VerifyDocumentResponse(id=doc.id, extraction_confirmed=doc.extraction_confirmed)

