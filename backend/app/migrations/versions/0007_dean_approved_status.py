"""Add DEAN_APPROVED application status for SA announcement queue.

After the Dean signs off, applications land in DEAN_APPROVED until
Student Affairs publishes the final result (DEAN_APPROVED → ANNOUNCED).

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE app_status ADD VALUE IF NOT EXISTS 'DEAN_APPROVED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
