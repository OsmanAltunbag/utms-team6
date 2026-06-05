import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .application import Application
    from .ranking import Ranking
    from .user import User


class ApplicationPeriod(Base):
    __tablename__ = "application_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    opens_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    applications: Mapped[List["Application"]] = relationship(
        "Application", back_populates="period"
    )
    rankings: Mapped[List["Ranking"]] = relationship(
        "Ranking", back_populates="period"
    )

    @property
    def is_open(self) -> bool:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        opens = self.opens_at.replace(tzinfo=timezone.utc) if self.opens_at.tzinfo is None else self.opens_at
        closes = self.closes_at.replace(tzinfo=timezone.utc) if self.closes_at.tzinfo is None else self.closes_at
        return self.is_active and opens <= now <= closes