import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import RankStatus, rank_status_type

if TYPE_CHECKING:
    from .application import Application
    from .period import ApplicationPeriod
    from .program import Program
    from .user import User


class Ranking(Base):
    __tablename__ = "rankings"
    __table_args__ = (
        UniqueConstraint("program_id", "period_id", name="uq_ranking_program_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_periods.id"), nullable=False
    )
    status: Mapped[RankStatus] = mapped_column(
        rank_status_type,
        nullable=False,
        default=RankStatus.DRAFT,
        server_default=text("'DRAFT'"),
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    program: Mapped["Program"] = relationship("Program", back_populates="rankings")
    period: Mapped["ApplicationPeriod"] = relationship(
        "ApplicationPeriod", back_populates="rankings"
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by]
    )
    entries: Mapped[List["RankingEntry"]] = relationship(
        "RankingEntry", back_populates="ranking", order_by="RankingEntry.position"
    )


class RankingEntry(Base):
    __tablename__ = "ranking_entries"
    __table_args__ = (
        UniqueConstraint("ranking_id", "application_id", name="uq_entry_ranking_app"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ranking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rankings.id"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False
    )
    composite_score: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )  # TRUE = asil, FALSE = yedek

    # Relationships
    ranking: Mapped["Ranking"] = relationship("Ranking", back_populates="entries")
    application: Mapped["Application"] = relationship(
        "Application", back_populates="ranking_entry"
    )
