"""Add is_locked column to academic_records.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "academic_records",
        sa.Column(
            "is_locked",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("academic_records", "is_locked")
