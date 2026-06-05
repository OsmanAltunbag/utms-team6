"""
SPEC-014: Approve English Proficiency
SPEC-015: Announce English Proficiency Exam Results
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import AppStatus, UserRole
from app.services.english_service import EnglishProficiencyService

router = APIRouter()

_require_ydyo = require_role(UserRole.YDYO)


class ApproveEnglishRequest(BaseModel):
    exam_type: str
    exam_score: float


class RejectEnglishRequest(BaseModel):
    rejection_reason: str
    notes: str = ""


class ExamResult(BaseModel):
    application_id: uuid.UUID
    score: float
    passed: bool
    exam_type: Optional[str] = "IZTECH_EXAM"
    rejection_reason: Optional[str] = "INSUFFICIENT_SCORE"


class PublishExamResultsRequest(BaseModel):
    results: list[ExamResult]


# ---------------------------------------------------------------------------
# SPEC-014 endpoints
# ---------------------------------------------------------------------------

@router.get("/applications")
async def list_english_review_applications(
    current_user=Depends(_require_ydyo),
    db: AsyncSession = Depends(get_db),
):
    from app.domain.application import Application
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Application)
        .options(
            selectinload(Application.applicant),
            selectinload(Application.program),
            selectinload(Application.documents),
        )
        .where(Application.status == AppStatus.ENGLISH_REVIEW)
    )
    apps = list(result.scalars().all())
    return [
        {
            "id": str(a.id),
            "tracking_number": a.tracking_number,
            "status": a.status.value,
            "program": a.program.name if a.program else None,
            "applicant": f"{a.applicant.user.first_name} {a.applicant.user.last_name}" if a.applicant and a.applicant.user else None,
        }
        for a in apps
    ]


@router.get("/applications/{application_id}")
async def get_application_for_english_review(
    application_id: uuid.UUID,
    current_user=Depends(_require_ydyo),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.application_repository import ApplicationRepository
    from fastapi import HTTPException
    repo = ApplicationRepository(db)
    app = await repo.get_by_id(application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return {
        "id": str(app.id),
        "status": app.status.value,
        "english_review": {
            "approved": app.english_proficiency_review.approved if app.english_proficiency_review else None,
            "exam_type": app.english_proficiency_review.exam_type if app.english_proficiency_review else None,
            "exam_score": float(app.english_proficiency_review.exam_score) if app.english_proficiency_review and app.english_proficiency_review.exam_score else None,
        } if app.english_proficiency_review else None,
        "documents": [
            {"id": str(d.id), "doc_type": d.doc_type.value, "status": d.status.value}
            for d in app.documents
        ],
    }


@router.post("/applications/{application_id}/approve-english")
async def approve_english(
    application_id: uuid.UUID,
    body: ApproveEnglishRequest,
    current_user=Depends(_require_ydyo),
    db: AsyncSession = Depends(get_db),
):
    svc = EnglishProficiencyService(db)
    review = await svc.approve(
        application_id, current_user.id, body.exam_type, body.exam_score
    )
    return {
        "application_id": str(review.application_id),
        "approved": review.approved,
        "exam_type": review.exam_type,
        "exam_score": float(review.exam_score) if review.exam_score else None,
    }


@router.post("/applications/{application_id}/reject-english")
async def reject_english(
    application_id: uuid.UUID,
    body: RejectEnglishRequest,
    current_user=Depends(_require_ydyo),
    db: AsyncSession = Depends(get_db),
):
    svc = EnglishProficiencyService(db)
    review = await svc.reject(
        application_id, current_user.id, body.rejection_reason, body.notes
    )
    return {
        "application_id": str(review.application_id),
        "approved": review.approved,
        "notes": review.notes,
    }


# ---------------------------------------------------------------------------
# SPEC-015 endpoints
# ---------------------------------------------------------------------------

@router.get("/exam-results")
async def list_exam_results(
    current_user=Depends(_require_ydyo),
    db: AsyncSession = Depends(get_db),
):
    from app.domain.application import Application
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Application)
        .options(
            selectinload(Application.applicant),
            selectinload(Application.english_proficiency_review),
        )
        .where(Application.status == AppStatus.ENGLISH_REVIEW)
    )
    apps = list(result.scalars().all())
    return [
        {
            "application_id": str(a.id),
            "applicant_name": f"{a.applicant.user.first_name} {a.applicant.user.last_name}" if a.applicant and a.applicant.user else None,
            "score": float(a.english_proficiency_review.exam_score) if a.english_proficiency_review and a.english_proficiency_review.exam_score else None,
            "passed": a.english_proficiency_review.approved if a.english_proficiency_review else None,
        }
        for a in apps
    ]


@router.post("/exam-results/publish")
async def publish_exam_results(
    body: PublishExamResultsRequest,
    current_user=Depends(_require_ydyo),
    db: AsyncSession = Depends(get_db),
):
    svc = EnglishProficiencyService(db)
    result = await svc.publish_exam_results(
        [r.model_dump() for r in body.results],
        current_user.id,
    )
    return result
