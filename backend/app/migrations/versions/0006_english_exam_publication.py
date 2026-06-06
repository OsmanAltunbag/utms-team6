"""Add exam publication metadata to english_proficiency_reviews.

Supports UC-05-02 (Announce English Proficiency Exam Results):

  exam_date     — date the YDYO proficiency exam was taken
  published_at  — irreversible publication timestamp (SR1)
  published_by  — officer who published the result (SR2)

Pre-publication state (Pending Publication):
    must_take_exam = TRUE  AND  exam_score IS NOT NULL  AND  published_at IS NULL

Published state:
    must_take_exam = TRUE  AND  exam_score IS NOT NULL  AND  published_at IS NOT NULL

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "english_proficiency_reviews",
        sa.Column("exam_date", sa.Date, nullable=True),
    )
    op.add_column(
        "english_proficiency_reviews",
        sa.Column(
            "published_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "english_proficiency_reviews",
        sa.Column(
            "published_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("english_proficiency_reviews", "published_by")
    op.drop_column("english_proficiency_reviews", "published_at")
    op.drop_column("english_proficiency_reviews", "exam_date")
