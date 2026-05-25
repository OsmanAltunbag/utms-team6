from typing import List
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.user import User

router = APIRouter()


class ProgramOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    faculty: str
    quota: int
    min_gpa: float | None

    model_config = {"from_attributes": True}


class PeriodOut(BaseModel):
    id: uuid.UUID
    label: str
    opens_at: str
    closes_at: str

    model_config = {"from_attributes": True}


@router.get("/programs", response_model=List[ProgramOut])
async def list_programs(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProgramOut]:
    result = await db.execute(select(Program).where(Program.is_active == True))
    programs = result.scalars().all()
    return [
        ProgramOut(
            id=p.id,
            name=p.name,
            code=p.code,
            faculty=p.faculty,
            quota=p.quota,
            min_gpa=float(p.min_gpa) if p.min_gpa is not None else None,
        )
        for p in programs
    ]


@router.get("/periods", response_model=List[PeriodOut])
async def list_open_periods(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PeriodOut]:
    result = await db.execute(
        select(ApplicationPeriod).where(ApplicationPeriod.is_active == True)
    )
    periods = result.scalars().all()
    return [
        PeriodOut(
            id=p.id,
            label=p.label,
            opens_at=p.opens_at.isoformat(),
            closes_at=p.closes_at.isoformat(),
        )
        for p in periods
        if p.is_open
    ]
