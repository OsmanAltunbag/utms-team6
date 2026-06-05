"""
SPEC-006: Student Affairs — Oversee Application Documents
SPEC-007: Student Affairs — Notify Transfer Results
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import AppStatus, UserRole
from app.schemas.application import ApplicationDetailResponse, ApplicationSummary
from app.services.officer_service import OfficerApplicationService
from pydantic import BaseModel

router = APIRouter()

_require_sa = require_role(UserRole.STUDENT_AFFAIRS)


class CorrectionRequest(BaseModel):
    note: str


class RejectionRequest(BaseModel):
    reason_code: str
    note: str = ""


class PublishResultsResponse(BaseModel):
    announced_count: int


# ---------------------------------------------------------------------------
# SPEC-006 endpoints
# ---------------------------------------------------------------------------

@router.get("/applications", response_model=list[ApplicationSummary])
async def list_applications(
    status: Optional[AppStatus] = None,
    program_id: Optional[uuid.UUID] = None,
    period_id: Optional[uuid.UUID] = None,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    svc = OfficerApplicationService(db)
    apps = await svc.list_applications(status, program_id, period_id)
    return [ApplicationSummary.model_validate(a) for a in apps]


@router.get("/applications/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: uuid.UUID,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.application_repository import ApplicationRepository
    repo = ApplicationRepository(db)
    app = await repo.get_by_id(application_id)
    if app is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationDetailResponse.model_validate(app)


@router.post("/applications/{application_id}/approve-verification")
async def approve_verification(
    application_id: uuid.UUID,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    svc = OfficerApplicationService(db)
    app = await svc.approve_verification(application_id, current_user.id)
    return {"id": str(app.id), "status": app.status.value}


@router.post("/applications/{application_id}/request-correction")
async def request_correction(
    application_id: uuid.UUID,
    body: CorrectionRequest,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    svc = OfficerApplicationService(db)
    app = await svc.request_correction(application_id, current_user.id, body.note)
    return {"id": str(app.id), "status": app.status.value}


@router.post("/applications/{application_id}/reject")
async def reject_application(
    application_id: uuid.UUID,
    body: RejectionRequest,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    svc = OfficerApplicationService(db)
    app = await svc.reject_application(
        application_id, current_user.id, body.reason_code, body.note
    )
    return {"id": str(app.id), "status": app.status.value}


# ---------------------------------------------------------------------------
# SPEC-007 endpoints
# ---------------------------------------------------------------------------

@router.get("/results/{period_id}/{program_id}")
async def get_results(
    period_id: uuid.UUID,
    program_id: uuid.UUID,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    svc = OfficerApplicationService(db)
    data = await svc.get_results(period_id, program_id)
    ranking = data["ranking"]
    return {
        "ranking_id": str(ranking.id),
        "status": ranking.status.value,
        "published_at": ranking.published_at,
        "primary": [
            {
                "application_id": str(e.application_id),
                "position": e.position,
                "composite_score": float(e.composite_score),
                "first_name": e.application.applicant.user.first_name,
                "last_name": e.application.applicant.user.last_name,
                "email": e.application.applicant.user.email,
            }
            for e in data["primary"]
        ],
        "waitlisted": [
            {
                "application_id": str(e.application_id),
                "position": e.position,
                "composite_score": float(e.composite_score),
                "first_name": e.application.applicant.user.first_name,
                "last_name": e.application.applicant.user.last_name,
                "email": e.application.applicant.user.email,
            }
            for e in data["waitlisted"]
        ],
    }


@router.post(
    "/results/{period_id}/{program_id}/publish",
    response_model=PublishResultsResponse,
)
async def publish_results(
    period_id: uuid.UUID,
    program_id: uuid.UUID,
    current_user=Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
):
    svc = OfficerApplicationService(db)
    result = await svc.publish_results(period_id, program_id, current_user.id)
    return PublishResultsResponse(**result)
