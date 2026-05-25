import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eligibility import EligibilityCheck


class EligibilityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_application(self, application_id: uuid.UUID) -> List[EligibilityCheck]:
        result = await self.db.execute(
            select(EligibilityCheck).where(EligibilityCheck.application_id == application_id)
        )
        return list(result.scalars().all())

    async def save(self, check: EligibilityCheck) -> None:
        self.db.add(check)
        await self.db.flush()
