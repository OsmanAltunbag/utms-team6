import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .application import Application
    from .eligibility import DepartmentRequirement
    from .ranking import Ranking


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    faculty: Mapped[str] = mapped_column(String(150), nullable=False)
    quota: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    min_gpa: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )

    # Relationships
    applications: Mapped[List["Application"]] = relationship(
        "Application", back_populates="program"
    )
    department_requirements: Mapped[List["DepartmentRequirement"]] = relationship(
        "DepartmentRequirement", back_populates="program"
    )
    rankings: Mapped[List["Ranking"]] = relationship(
        "Ranking", back_populates="program"
    )
