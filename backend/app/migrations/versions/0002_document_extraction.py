"""Add extracted_data and extraction_confirmed to documents table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("extracted_data", JSONB, nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "extraction_confirmed",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "extraction_confirmed")
    op.drop_column("documents", "extracted_data")
