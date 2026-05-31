import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.audit import AuditLog
from app.domain.enums import AppStatus, RankStatus
from app.domain.ranking import Ranking, RankingEntry
from app.repositories.application_repository import ApplicationRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.program_repository import ProgramRepository

logger = logging.getLogger(__name__)

_EPOCH_MAX = datetime(9999, 12, 31, tzinfo=timezone.utc)


def calculate_transfer_score(
    yks_score: float,
    program_base_score: float,
    gpa_100: float,
) -> float:
    """
    SRS UC-04-03 formula (SR1 — deterministic pure function):
      Exam Component = (yks_score / program_base_score) × 100 × 0.90
      GPA Component  = gpa_100 × 0.10
      Transfer Score = Exam + GPA, rounded to 3 decimal places
    """
    exam_component = (yks_score / program_base_score) * 100 * 0.90
    gpa_component = gpa_100 * 0.10
    return round(exam_component + gpa_component, 3)


class RankingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._program_repo = ProgramRepository(db)
        self._period_repo = PeriodRepository(db)

    async def generate_ranking(
        self,
        program_id: uuid.UUID,
        period_id: uuid.UUID,
        generated_by: uuid.UUID,
    ) -> Ranking:
        program = await self._program_repo.get_by_id(program_id)
        if program is None:
            raise HTTPException(status_code=404, detail="Program not found")

        period = await self._period_repo.get_by_id(period_id)
        if period is None:
            raise HTTPException(status_code=404, detail="Period not found")

        applications = await self._app_repo.get_by_program_period_status(
            program_id=program_id,
            period_id=period_id,
            app_status=AppStatus.RANKING,
        )

        base_score = getattr(program, "base_score", None)

        eligible: List[tuple] = []
        excluded_count = 0

        for app in applications:
            record = app.academic_record
            yks_score = (
                float(record.yks_score)
                if (record and record.yks_score is not None)
                else None
            )

            if yks_score is None or base_score is None:
                excluded_count += 1
                logger.info(
                    "Excluded application %s: missing score data (AC-01)", app.id
                )
                continue

            gpa_100 = (
                float(record.gpa_100)
                if (record and record.gpa_100 is not None)
                else 0.0
            )
            score = calculate_transfer_score(yks_score, float(base_score), gpa_100)
            eligible.append((app, score))

        # Sort DESC by composite score; tie-break by submitted_at ASC (SR2)
        eligible.sort(key=lambda x: (-x[1], x[0].submitted_at or _EPOCH_MAX))

        ranking = Ranking(
            program_id=program_id,
            period_id=period_id,
            status=RankStatus.DRAFT,
        )
        self.db.add(ranking)
        await self.db.flush()

        quota = program.quota or 0
        for pos, (app, score) in enumerate(eligible, start=1):
            entry = RankingEntry(
                ranking_id=ranking.id,
                application_id=app.id,
                composite_score=Decimal(str(score)),
                position=pos,
                is_primary=(pos <= quota),
            )
            self.db.add(entry)

        await self.db.flush()

        audit = AuditLog(
            actor_id=generated_by,
            action="RANKING_GENERATED",
            entity_type="Ranking",
            entity_id=ranking.id,
            new_value={
                "program_id": str(program_id),
                "period_id": str(period_id),
                "total_eligible": len(eligible),
                "total_excluded": excluded_count,
                "quota": quota,
            },
        )
        self.db.add(audit)
        await self.db.flush()

        return ranking

    async def get_ranking(self, ranking_id: uuid.UUID) -> Ranking:
        result = await self.db.execute(
            select(Ranking)
            .options(selectinload(Ranking.entries))
            .where(Ranking.id == ranking_id)
        )
        ranking = result.scalar_one_or_none()
        if ranking is None:
            raise HTTPException(status_code=404, detail="Ranking not found")
        return ranking
