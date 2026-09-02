"""Record the findings covered by a human review.

Revision ID: 0002_human_review_findings
Revises: 0001_greenfield_schema
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_human_review_findings"
down_revision: str | None = "0001_greenfield_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_reviews",
        sa.Column("finding_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.alter_column("human_reviews", "finding_ids", server_default=None)


def downgrade() -> None:
    op.drop_column("human_reviews", "finding_ids")
