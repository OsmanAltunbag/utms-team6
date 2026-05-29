"""Add correction deadline fields to applications.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("correction_requested_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("correction_deadline", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "correction_deadline")
    op.drop_column("applications", "correction_requested_at")
