"""Add VERIFIED value to app_status enum.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06 00:00:00.000000

UC-03-01: approving document verification moves an application to VERIFIED
(between SUBMITTED and UNDER_REVIEW), so the PostgreSQL app_status enum needs
the new value.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Insert VERIFIED right after SUBMITTED to mirror the lifecycle ordering.
    op.execute("ALTER TYPE app_status ADD VALUE IF NOT EXISTS 'VERIFIED' AFTER 'SUBMITTED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a value from an enum type. Rebuild the type
    # without VERIFIED, remapping any rows that still use it to UNDER_REVIEW.
    op.execute("ALTER TYPE app_status RENAME TO app_status_old")
    op.execute(
        """
        CREATE TYPE app_status AS ENUM (
            'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'ENGLISH_REVIEW',
            'DEPT_EVAL', 'RANKING', 'ANNOUNCED', 'REJECTED', 'CORRECTION_REQUESTED'
        )
        """
    )
    op.execute("ALTER TABLE applications ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE applications
        ALTER COLUMN status TYPE app_status
        USING (
            CASE status::text
                WHEN 'VERIFIED' THEN 'UNDER_REVIEW'
                ELSE status::text
            END
        )::app_status
        """
    )
    op.execute("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'DRAFT'")
    op.execute("DROP TYPE app_status_old")
