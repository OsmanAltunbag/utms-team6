import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.period import ApplicationPeriod


class PeriodRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, period_id: uuid.UUID) -> Optional[ApplicationPeriod]:
        return await self.db.get(ApplicationPeriod, period_id)
