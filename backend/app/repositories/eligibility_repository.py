import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eligibility import DepartmentRequirement, EligibilityCheck


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


class DepartmentRequirementRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_program(self, program_id: uuid.UUID) -> List[DepartmentRequirement]:
        result = await self.db.execute(
            select(DepartmentRequirement)
            .where(DepartmentRequirement.program_id == program_id)
            .order_by(DepartmentRequirement.rule_key)
        )
        return list(result.scalars().all())

    async def get_by_id(self, condition_id: uuid.UUID) -> Optional[DepartmentRequirement]:
        return await self.db.get(DepartmentRequirement, condition_id)

    async def get_by_program_and_rule_key(
        self, program_id: uuid.UUID, rule_key: str
    ) -> Optional[DepartmentRequirement]:
        result = await self.db.execute(
            select(DepartmentRequirement).where(
                DepartmentRequirement.program_id == program_id,
                DepartmentRequirement.rule_key == rule_key,
            )
        )
        return result.scalars().first()

    async def delete(self, condition: DepartmentRequirement) -> None:
        await self.db.delete(condition)
        await self.db.flush()
