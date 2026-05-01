import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import IntibakStatus, intibak_status_type

if TYPE_CHECKING:
    from .application import Application
    from .user import User


class IntibakTable(Base):
    __tablename__ = "intibak_tables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id"),
        nullable=False,
        unique=True,
    )
    prepared_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[IntibakStatus] = mapped_column(
        intibak_status_type,
        nullable=False,
        default=IntibakStatus.DRAFT,
        server_default=text("'DRAFT'"),
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application", back_populates="intibak_table"
    )
    preparer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[prepared_by]
    )
    course_mappings: Mapped[List["CourseMapping"]] = relationship(
        "CourseMapping", back_populates="intibak_table"
    )

    @property
    def is_editable(self) -> bool:
        return self.status == IntibakStatus.DRAFT


class CourseMapping(Base):
    __tablename__ = "course_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intibak_table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intibak_tables.id"), nullable=False
    )
    source_course: Mapped[str] = mapped_column(String(200), nullable=False)
    source_credits: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1), nullable=True)
    target_course: Mapped[str] = mapped_column(String(200), nullable=False)
    target_credits: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1), nullable=True)
    equivalence_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'FULL', 'PARTIAL', 'NONE'
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    intibak_table: Mapped["IntibakTable"] = relationship(
        "IntibakTable", back_populates="course_mappings"
    )
