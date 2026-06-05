"""
SPEC-010: Generate Ranking Automatically
SPEC-011: Approve System-Generated Ranking
SPEC-013: Process Waitlisted Applicants
"""
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import UserRole
from app.services.ranking_service import RankingService

router = APIRouter()

_require_ygk = require_role(UserRole.TRANSFER_COMMISSION)


class GenerateRankingRequest(BaseModel):
    program_id: uuid.UUID
    period_id: uuid.UUID


class ReturnForCorrectionRequest(BaseModel):
    note: str


class PromoteWaitlistedRequest(BaseModel):
    withdrawn_application_id: uuid.UUID


# ---------------------------------------------------------------------------
# SPEC-010
# ---------------------------------------------------------------------------

@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_ranking(
    body: GenerateRankingRequest,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
):
    svc = RankingService(db)
    ranking = await svc.generate_ranking(body.program_id, body.period_id, current_user.id)
    excluded = getattr(ranking, "_excluded", [])
    return {
        "id": str(ranking.id),
        "program_id": str(ranking.program_id),
        "period_id": str(ranking.period_id),
        "status": ranking.status.value,
        "excluded_candidates": excluded,
    }


@router.get("/{ranking_id}")
async def get_ranking(
    ranking_id: uuid.UUID,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
):
    svc = RankingService(db)
    ranking = await svc.get_ranking(ranking_id)
    return {
        "id": str(ranking.id),
        "program": ranking.program.name if ranking.program else None,
        "period": ranking.period.label if ranking.period else None,
        "status": ranking.status.value,
        "approved_at": ranking.approved_at,
        "published_at": ranking.published_at,
        "entries": [
            {
                "application_id": str(e.application_id),
                "position": e.position,
                "composite_score": float(e.composite_score),
                "is_primary": e.is_primary,
            }
            for e in sorted(ranking.entries, key=lambda x: x.position)
        ],
    }


# ---------------------------------------------------------------------------
# SPEC-011
# ---------------------------------------------------------------------------

@router.post("/{ranking_id}/approve")
async def approve_ranking(
    ranking_id: uuid.UUID,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
):
    svc = RankingService(db)
    ranking = await svc.approve_ranking(ranking_id, current_user.id)
    return {
        "id": str(ranking.id),
        "status": ranking.status.value,
        "approved_at": ranking.approved_at,
    }


@router.post("/{ranking_id}/return")
async def return_for_correction(
    ranking_id: uuid.UUID,
    body: ReturnForCorrectionRequest,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
):
    svc = RankingService(db)
    ranking = await svc.return_for_correction(ranking_id, current_user.id, body.note)
    return {"id": str(ranking.id), "status": ranking.status.value, "note": body.note}


# ---------------------------------------------------------------------------
# SPEC-013
# ---------------------------------------------------------------------------

@router.get("/{ranking_id}/waitlist")
async def get_waitlist(
    ranking_id: uuid.UUID,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
):
    svc = RankingService(db)
    data = await svc.get_waitlist(ranking_id)
    return {
        "vacant_slots": data["vacant_slots"],
        "waitlisted": [
            {
                "application_id": str(e.application_id),
                "position": e.position,
                "composite_score": float(e.composite_score),
            }
            for e in data["waitlisted"]
        ],
    }


@router.post("/{ranking_id}/promote-waitlisted")
async def promote_waitlisted(
    ranking_id: uuid.UUID,
    body: PromoteWaitlistedRequest,
    current_user=Depends(_require_ygk),
    db: AsyncSession = Depends(get_db),
):
    svc = RankingService(db)
    entry = await svc.promote_next_waitlisted(
        ranking_id, body.withdrawn_application_id, current_user.id
    )
    if entry is None:
        return {"promoted": None, "message": "No candidates remain on waitlist"}
    return {
        "promoted": {
            "application_id": str(entry.application_id),
            "position": entry.position,
            "composite_score": float(entry.composite_score),
        },
        "message": "Candidate promoted from waitlist to primary",
    }
