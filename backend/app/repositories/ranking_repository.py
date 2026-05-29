import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.application import Application
from app.domain.ranking import Ranking, RankingEntry
from app.domain.user import Applicant


class RankingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_program_and_period(
        self, program_id: uuid.UUID, period_id: uuid.UUID
    ) -> Optional[Ranking]:
        result = await self.db.execute(
            select(Ranking)
            .options(
                selectinload(Ranking.program),
                selectinload(Ranking.period),
                selectinload(Ranking.entries)
                .selectinload(RankingEntry.application)
                .selectinload(Application.applicant)
                .selectinload(Applicant.user),
            )
            .where(
                Ranking.program_id == program_id,
                Ranking.period_id == period_id,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, ranking: Ranking) -> None:
        self.db.add(ranking)
        await self.db.flush()
