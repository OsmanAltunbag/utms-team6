"""Add template fields to notifications for Jinja2 rendering.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("template_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("template_context", JSONB, nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("error_message", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "error_message")
    op.drop_column("notifications", "template_context")
    op.drop_column("notifications", "template_name")
