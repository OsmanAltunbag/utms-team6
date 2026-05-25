import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.application import Application
from app.domain.enums import AppStatus


class ApplicationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, app_id: uuid.UUID) -> Optional[Application]:
        result = await self.db.execute(
            select(Application)
            .options(
                selectinload(Application.applicant),
                selectinload(Application.program),
                selectinload(Application.period),
                selectinload(Application.academic_record),
                selectinload(Application.documents),
                selectinload(Application.eligibility_checks),
            )
            .where(Application.id == app_id)
        )
        return result.scalar_one_or_none()

    async def get_by_applicant(self, applicant_id: uuid.UUID) -> List[Application]:
        result = await self.db.execute(
            select(Application).where(Application.applicant_id == applicant_id)
        )
        return list(result.scalars().all())

    async def get_by_program_and_period(
        self,
        applicant_id: uuid.UUID,
        program_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> Optional[Application]:
        result = await self.db.execute(
            select(Application).where(
                Application.applicant_id == applicant_id,
                Application.program_id == program_id,
                Application.period_id == period_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_filtered(
        self,
        status: Optional[AppStatus] = None,
        program_id: Optional[uuid.UUID] = None,
    ) -> List[Application]:
        q = select(Application)
        if status is not None:
            q = q.where(Application.status == status)
        if program_id is not None:
            q = q.where(Application.program_id == program_id)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def count_submitted_this_year(self, year: int) -> int:
        result = await self.db.execute(
            select(func.count(Application.id)).where(
                Application.tracking_number.isnot(None),
                func.extract("year", Application.submitted_at) == year,
            )
        )
        return result.scalar_one() or 0

    async def save(self, application: Application) -> None:
        self.db.add(application)
        await self.db.flush()
