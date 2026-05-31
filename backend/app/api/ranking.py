import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import UserRole
from app.domain.user import User
from app.schemas.ranking import GenerateRankingRequest, RankingOut
from app.services.ranking_service import RankingService

router = APIRouter()


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    response_model=RankingOut,
)
async def generate_ranking(
    body: GenerateRankingRequest,
    current_user: User = Depends(require_role(UserRole.TRANSFER_COMMISSION)),
    db: AsyncSession = Depends(get_db),
) -> RankingOut:
    service = RankingService(db)
    ranking = await service.generate_ranking(
        program_id=body.program_id,
        period_id=body.period_id,
        generated_by=current_user.id,
    )
    return RankingOut.model_validate(ranking)


@router.get("/{ranking_id}", response_model=RankingOut)
async def get_ranking(
    ranking_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TRANSFER_COMMISSION)),
    db: AsyncSession = Depends(get_db),
) -> RankingOut:
    service = RankingService(db)
    ranking = await service.get_ranking(ranking_id)
    return RankingOut.model_validate(ranking)
