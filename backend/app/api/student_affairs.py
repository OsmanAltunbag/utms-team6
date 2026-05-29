import uuid

from typing import List, Optional



from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.ext.asyncio import AsyncSession



from app.core.database import get_db

from app.core.dependencies import require_role

from app.core.status_labels import srs_display_status

from app.domain.enums import AppStatus, UserRole

from app.domain.user import User

from app.schemas.application import EligibilityCheckResponse

from app.schemas.document import DocumentSummary, PreviewUrlResponse

from app.schemas.officer import (

    ApplicantProfileResponse,

    ApplicationSummaryWithValidation,

    OfficerActionResponse,

    OfficerApplicationDetailResponse,

    PublishResultsResponse,

    RejectApplicationRequest,

    RequestCorrectionRequest,

    ResultsListResponse,

)

from app.services.document_service import DocumentService

from app.services.officer_service import (

    ApplicationFilters,

    OfficerApplicationService,

    build_auto_validation_results,

)



router = APIRouter()





@router.get("/applications", response_model=List[ApplicationSummaryWithValidation])

async def list_applications(

    status_filter: Optional[AppStatus] = Query(None, alias="status"),

    program_id: Optional[uuid.UUID] = Query(None),

    period_id: Optional[uuid.UUID] = Query(None),

    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),

    db: AsyncSession = Depends(get_db),

) -> List[ApplicationSummaryWithValidation]:

    service = OfficerApplicationService(db)

    filters = ApplicationFilters(

        status=status_filter,

        program_id=program_id,

        period_id=period_id,

    )

    return await service.list_applications(filters)





@router.get("/applications/{application_id}", response_model=OfficerApplicationDetailResponse)

async def get_application(

    application_id: uuid.UUID,

    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),

    db: AsyncSession = Depends(get_db),

) -> OfficerApplicationDetailResponse:

    service = OfficerApplicationService(db)

    application = await service.get_application(application_id)

    applicant_user = application.applicant.user



    return OfficerApplicationDetailResponse(

        id=application.id,

        applicant_id=application.applicant_id,

        program_id=application.program_id,

        period_id=application.period_id,

        status=application.status.value,

        display_status=srs_display_status(application.status),

        tracking_number=application.tracking_number,

        submitted_at=application.submitted_at,

        created_at=application.created_at,

        updated_at=application.updated_at,

        correction_deadline=application.correction_deadline,

        progress=application.get_progress(),

        applicant=ApplicantProfileResponse(

            first_name=applicant_user.first_name,

            last_name=applicant_user.last_name,

            email=applicant_user.email,

            national_id=application.applicant.national_id,

            phone=application.applicant.phone,

        ),

        eligibility_checks=[

            EligibilityCheckResponse(

                rule_key=c.rule_key,

                passed=c.passed,

                detail=c.detail,

            )

            for c in application.eligibility_checks

        ],

        documents=[DocumentSummary.model_validate(d) for d in application.documents],

        auto_validation_results=build_auto_validation_results(application),

    )





@router.get(

    "/applications/{application_id}/documents/{document_id}/preview",

    response_model=PreviewUrlResponse,

)

async def preview_document(

    application_id: uuid.UUID,

    document_id: uuid.UUID,

    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),

    db: AsyncSession = Depends(get_db),

) -> PreviewUrlResponse:

    from app.repositories.document_repository import DocumentRepository

    from app.services.officer_service import CORRUPTED_DOCUMENT_MESSAGE



    doc_repo = DocumentRepository(db)

    doc = await doc_repo.get_by_id(document_id)

    if doc is None or doc.application_id != application_id:

        raise HTTPException(status_code=404, detail="Document not found")



    service = DocumentService(db)

    preview_url, viewable, content_type = await service.generate_preview_url_with_status(

        document_id, current_user.id

    )

    return PreviewUrlResponse(

        preview_url=preview_url,

        viewable=viewable,

        content_type=content_type,

        error_message=None if viewable else CORRUPTED_DOCUMENT_MESSAGE,

    )





@router.post(

    "/applications/{application_id}/approve-verification",

    response_model=OfficerActionResponse,

)

async def approve_verification(

    application_id: uuid.UUID,

    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),

    db: AsyncSession = Depends(get_db),

) -> OfficerActionResponse:

    service = OfficerApplicationService(db)

    application = await service.approve_verification(application_id, current_user.id)

    return OfficerActionResponse(

        application_id=application.id,

        status=application.status.value,

        display_status=srs_display_status(application.status),

    )





@router.post(

    "/applications/{application_id}/request-correction",

    response_model=OfficerActionResponse,

)

async def request_correction(

    application_id: uuid.UUID,

    body: RequestCorrectionRequest,

    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),

    db: AsyncSession = Depends(get_db),

) -> OfficerActionResponse:

    service = OfficerApplicationService(db)

    application = await service.request_correction(

        application_id, current_user.id, body.note

    )

    return OfficerActionResponse(

        application_id=application.id,

        status=application.status.value,

        display_status=srs_display_status(application.status),

    )





@router.post(

    "/applications/{application_id}/reject",

    response_model=OfficerActionResponse,

)

async def reject_application(

    application_id: uuid.UUID,

    body: RejectApplicationRequest,

    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),

    db: AsyncSession = Depends(get_db),

) -> OfficerActionResponse:

    service = OfficerApplicationService(db)

    application = await service.reject_application(

        application_id,

        current_user.id,

        body.reason_code,

        body.note,

    )

    return OfficerActionResponse(

        application_id=application.id,

        status=application.status.value,

        display_status=srs_display_status(application.status),

    )


@router.get(
    "/results/{period_id}/{program_id}",
    response_model=ResultsListResponse,
)
async def get_results(
    period_id: uuid.UUID,
    program_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),
    db: AsyncSession = Depends(get_db),
) -> ResultsListResponse:
    service = OfficerApplicationService(db)
    return await service.get_results(period_id, program_id)


@router.post(
    "/results/{period_id}/{program_id}/publish",
    response_model=PublishResultsResponse,
)
async def publish_results(
    period_id: uuid.UUID,
    program_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.STUDENT_AFFAIRS)),
    db: AsyncSession = Depends(get_db),
) -> PublishResultsResponse:
    service = OfficerApplicationService(db)
    result = await service.publish_results(period_id, program_id, current_user.id)
    return PublishResultsResponse(
        announced_count=result.announced_count,
        notifications_enqueued=result.notifications_enqueued,
        published_at=result.published_at,
    )


