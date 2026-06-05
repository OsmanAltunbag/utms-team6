import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import AuditLog
from app.domain.period import ApplicationPeriod
from app.repositories.period_repository import PeriodRepository


class PeriodService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = PeriodRepository(db)

    async def create_period(
        self,
        label: str,
        opens_at: datetime,
        closes_at: datetime,
        created_by: uuid.UUID,
    ) -> ApplicationPeriod:
        if closes_at <= opens_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End date cannot be before start date",
            )

        active_periods = await self._repo.get_active_periods()
        for p in active_periods:
            p_closes = p.closes_at.replace(tzinfo=timezone.utc) if p.closes_at.tzinfo is None else p.closes_at
            p_opens = p.opens_at.replace(tzinfo=timezone.utc) if p.opens_at.tzinfo is None else p.opens_at
            opens_at_aware = opens_at.replace(tzinfo=timezone.utc) if opens_at.tzinfo is None else opens_at
            closes_at_aware = closes_at.replace(tzinfo=timezone.utc) if closes_at.tzinfo is None else closes_at
            if opens_at_aware < p_closes and closes_at_aware > p_opens:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An overlapping active period already exists",
                )

        period = ApplicationPeriod(
            label=label,
            opens_at=opens_at,
            closes_at=closes_at,
            is_active=False,
            created_by=created_by,
        )
        self.db.add(period)
        await self.db.flush()

        log = AuditLog(
            actor_id=created_by,
            action="PERIOD_CREATED",
            entity_type="ApplicationPeriod",
            entity_id=period.id,
            new_value={
                "label": label,
                "opens_at": opens_at.isoformat(),
                "closes_at": closes_at.isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()

        return period

    async def list_periods(self) -> List[ApplicationPeriod]:
        return await self._repo.get_all()

    async def is_open(self, period_id: uuid.UUID) -> bool:
        period = await self._repo.get_by_id(period_id)
        if period is None:
            return False
        now = datetime.now(timezone.utc)
        opens = period.opens_at.replace(tzinfo=timezone.utc) if period.opens_at.tzinfo is None else period.opens_at
        closes = period.closes_at.replace(tzinfo=timezone.utc) if period.closes_at.tzinfo is None else period.closes_at
        return period.is_active and opens <= now <= closes
    async def update_period(
        self,
        period_id: uuid.UUID,
        label: str | None,
        opens_at: datetime | None,
        closes_at: datetime | None,
        by: uuid.UUID,
    ) -> ApplicationPeriod:
        period = await self._get_or_404(period_id)

        new_opens = opens_at if opens_at is not None else period.opens_at
        new_closes = closes_at if closes_at is not None else period.closes_at

        if new_closes <= new_opens:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End date cannot be before start date",
            )

        old = {
            "label": period.label,
            "opens_at": period.opens_at.isoformat(),
            "closes_at": period.closes_at.isoformat(),
        }

        if label is not None:
            period.label = label
        if opens_at is not None:
            period.opens_at = opens_at
        if closes_at is not None:
            period.closes_at = closes_at

        await self.db.flush()

        log = AuditLog(
            actor_id=by,
            action="PERIOD_UPDATED",
            entity_type="ApplicationPeriod",
            entity_id=period_id,
            old_value=old,
            new_value={
                "label": period.label,
                "opens_at": period.opens_at.isoformat(),
                "closes_at": period.closes_at.isoformat(),
            },
        )
        self.db.add(log)
        await self.db.flush()

        return period

    async def extend_deadline(
        self, period_id: uuid.UUID, new_closes_at: datetime, by: uuid.UUID
    ) -> ApplicationPeriod:
        period = await self._get_or_404(period_id)

        if new_closes_at <= period.opens_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New deadline must be after the period start date",
            )

        old_closes_at = period.closes_at
        period.closes_at = new_closes_at
        await self.db.flush()

        log = AuditLog(
            actor_id=by,
            action="PERIOD_EXTENDED",
            entity_type="ApplicationPeriod",
            entity_id=period_id,
            old_value={"closes_at": old_closes_at.isoformat()},
            new_value={"closes_at": new_closes_at.isoformat()},
        )
        self.db.add(log)
        await self.db.flush()

        return period

    async def emergency_close(
        self, period_id: uuid.UUID, by: uuid.UUID
    ) -> ApplicationPeriod:
        period = await self._get_or_404(period_id)

        now = datetime.now(timezone.utc)
        period.closes_at = now
        period.is_active = False
        await self.db.flush()

        log = AuditLog(
            actor_id=by,
            action="PERIOD_EMERGENCY_CLOSED",
            entity_type="ApplicationPeriod",
            entity_id=period_id,
            new_value={"closed_at": now.isoformat()},
        )
        self.db.add(log)
        await self.db.flush()

        return period

    async def activate_period(
        self, period_id: uuid.UUID, by: uuid.UUID
    ) -> ApplicationPeriod:
        period = await self._get_or_404(period_id)
        period.is_active = True
        await self.db.flush()

        log = AuditLog(
            actor_id=by,
            action="PERIOD_ACTIVATED",
            entity_type="ApplicationPeriod",
            entity_id=period_id,
            new_value={"is_active": True},
        )
        self.db.add(log)
        await self.db.flush()

        return period

    async def deactivate_period(
        self, period_id: uuid.UUID, by: uuid.UUID
    ) -> ApplicationPeriod:
        period = await self._get_or_404(period_id)
        period.is_active = False
        await self.db.flush()

        log = AuditLog(
            actor_id=by,
            action="PERIOD_DEACTIVATED",
            entity_type="ApplicationPeriod",
            entity_id=period_id,
            new_value={"is_active": False},
        )
        self.db.add(log)
        await self.db.flush()

        return period

    async def _get_or_404(self, period_id: uuid.UUID) -> ApplicationPeriod:
        period = await self._repo.get_by_id(period_id)
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application period not found",
            )
        return period
