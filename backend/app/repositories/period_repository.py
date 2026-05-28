import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.period import ApplicationPeriod


class PeriodRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, period_id: uuid.UUID) -> Optional[ApplicationPeriod]:
        return await self.db.get(ApplicationPeriod, period_id)

    async def get_all(self) -> List[ApplicationPeriod]:
        result = await self.db.execute(
            select(ApplicationPeriod).order_by(ApplicationPeriod.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_periods(self) -> List[ApplicationPeriod]:
        result = await self.db.execute(
            select(ApplicationPeriod).where(ApplicationPeriod.is_active.is_(True))
        )
        return list(result.scalars().all())
