"""
SPEC-016: Approve Transfer Application (Dean's Final Decision)
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import UserRole
from app.services.dean_service import DeanOfficeService

router = APIRouter()

_require_dean = require_role(UserRole.DEAN_OFFICE)


class ApproveRequest(BaseModel):
    pass


class RejectRequest(BaseModel):
    rejection_code: str
    note: str = ""


@router.get("/applications")
async def list_applications_for_dean(
    program_id: Optional[uuid.UUID] = None,
    period_id: Optional[uuid.UUID] = None,
    current_user=Depends(_require_dean),
    db: AsyncSession = Depends(get_db),
):
    svc = DeanOfficeService(db)
    apps = await svc.list_applications(program_id, period_id)
    return [
        {
            "id": str(a.id),
            "tracking_number": a.tracking_number,
            "status": a.status.value,
            "program": a.program.name if a.program else None,
            "applicant": f"{a.applicant.user.first_name} {a.applicant.user.last_name}" if a.applicant and a.applicant.user else None,
            "ranking_position": a.ranking_entry.position if a.ranking_entry else None,
            "composite_score": float(a.ranking_entry.composite_score) if a.ranking_entry else None,
            "intibak_status": a.intibak_table.status.value if a.intibak_table else None,
        }
        for a in apps
    ]


@router.get("/applications/{application_id}")
async def get_application_detail(
    application_id: uuid.UUID,
    current_user=Depends(_require_dean),
    db: AsyncSession = Depends(get_db),
):
    svc = DeanOfficeService(db)
    app = await svc.get_application_detail(application_id)
    record = app.academic_record
    return {
        "id": str(app.id),
        "tracking_number": app.tracking_number,
        "status": app.status.value,
        "program": app.program.name if app.program else None,
        "applicant": {
            "name": f"{app.applicant.user.first_name} {app.applicant.user.last_name}" if app.applicant and app.applicant.user else None,
            "email": app.applicant.user.email if app.applicant and app.applicant.user else None,
        } if app.applicant else None,
        "academic_record": {
            "gpa_4": float(record.gpa_4) if record and record.gpa_4 else None,
            "gpa_100": float(record.gpa_100) if record and record.gpa_100 else None,
            "yks_score": float(record.yks_score) if record and record.yks_score else None,
        } if record else None,
        "ranking_entry": {
            "position": app.ranking_entry.position,
            "composite_score": float(app.ranking_entry.composite_score),
            "is_primary": app.ranking_entry.is_primary,
        } if app.ranking_entry else None,
        "intibak_table": {
            "id": str(app.intibak_table.id),
            "status": app.intibak_table.status.value,
        } if app.intibak_table else None,
        "english_review": {
            "approved": app.english_proficiency_review.approved,
            "exam_type": app.english_proficiency_review.exam_type,
            "exam_score": float(app.english_proficiency_review.exam_score) if app.english_proficiency_review.exam_score else None,
        } if app.english_proficiency_review else None,
        "documents": [
            {"id": str(d.id), "doc_type": d.doc_type.value, "status": d.status.value}
            for d in app.documents
        ],
    }


@router.post("/applications/{application_id}/approve")
async def approve_final(
    application_id: uuid.UUID,
    request: Request,
    current_user=Depends(_require_dean),
    db: AsyncSession = Depends(get_db),
):
    ip_address = request.client.host if request.client else "unknown"
    svc = DeanOfficeService(db)
    app = await svc.approve_final(application_id, current_user.id, ip_address)
    return {"status": app.status.value, "message": "Transfer Accepted"}


@router.post("/applications/{application_id}/reject")
async def reject_final(
    application_id: uuid.UUID,
    body: RejectRequest,
    request: Request,
    current_user=Depends(_require_dean),
    db: AsyncSession = Depends(get_db),
):
    ip_address = request.client.host if request.client else "unknown"
    svc = DeanOfficeService(db)
    app = await svc.reject_final(
        application_id, current_user.id, body.rejection_code, body.note, ip_address
    )
    return {"status": app.status.value}
