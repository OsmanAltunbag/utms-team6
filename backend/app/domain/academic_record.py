import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .application import Application


class AcademicRecord(Base):
    __tablename__ = "academic_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id"),
        nullable=False,
        unique=True,
    )
    institution: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    gpa_4: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    gpa_100: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    yks_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    credits_completed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 'UBYS', 'YOKSIS', 'OSYM', 'MANUAL'

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application", back_populates="academic_record"
    )
