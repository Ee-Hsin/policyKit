"""Remove reviewer and semantic-search persistence.

Revision ID: 0003_remove_reviewer_and_search
Revises: 0002_human_review_findings
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_remove_reviewer_and_search"
down_revision: str | None = "0002_human_review_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revision_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("recruiter_name", sa.String(length=160), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["compliance_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revision_decisions_session_id", "revision_decisions", ["session_id"])

    bind = op.get_bind()
    old_reviews = sa.table(
        "human_reviews",
        sa.column("id", sa.String()),
        sa.column("session_id", sa.String()),
        sa.column("reviewer_name", sa.String()),
        sa.column("decision", sa.String()),
        sa.column("notes", sa.Text()),
        sa.column("finding_ids", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    revision_decisions = sa.table(
        "revision_decisions",
        sa.column("id", sa.String()),
        sa.column("session_id", sa.String()),
        sa.column("recruiter_name", sa.String()),
        sa.column("decision", sa.String()),
        sa.column("notes", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for review in bind.execute(sa.select(old_reviews)).mappings():
        if review["finding_ids"]:
            continue
        bind.execute(
            revision_decisions.insert().values(
                id=review["id"],
                session_id=review["session_id"],
                recruiter_name=review["reviewer_name"],
                decision=review["decision"],
                notes=review["notes"],
                created_at=review["created_at"],
            )
        )

    op.drop_index("ix_reviewed_precedents_jurisdiction", table_name="reviewed_precedents")
    op.drop_index("ix_reviewed_precedents_category", table_name="reviewed_precedents")
    op.drop_table("reviewed_precedents")
    op.drop_index("ix_human_reviews_session_id", table_name="human_reviews")
    op.drop_table("human_reviews")
    op.drop_column("policy_versions", "index_status")
    op.drop_column("compliance_findings", "resolved")
    sessions = sa.table("compliance_sessions", sa.column("status", sa.String()))
    op.execute(
        sessions.update()
        .where(sessions.c.status == "needs_review")
        .values(status="review_complete")
    )


def downgrade() -> None:
    op.add_column(
        "compliance_findings",
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("compliance_findings", "resolved", server_default=None)
    op.add_column(
        "policy_versions",
        sa.Column("index_status", sa.String(length=24), nullable=False, server_default="pending"),
    )
    op.alter_column("policy_versions", "index_status", server_default=None)
    op.create_table(
        "human_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_name", sa.String(length=160), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["compliance_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_reviews_session_id", "human_reviews", ["session_id"])

    bind = op.get_bind()
    decisions = sa.table(
        "revision_decisions",
        sa.column("id", sa.String()),
        sa.column("session_id", sa.String()),
        sa.column("recruiter_name", sa.String()),
        sa.column("decision", sa.String()),
        sa.column("notes", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    reviews = sa.table(
        "human_reviews",
        sa.column("id", sa.String()),
        sa.column("session_id", sa.String()),
        sa.column("reviewer_name", sa.String()),
        sa.column("decision", sa.String()),
        sa.column("notes", sa.Text()),
        sa.column("finding_ids", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for decision in bind.execute(sa.select(decisions)).mappings():
        bind.execute(
            reviews.insert().values(
                id=decision["id"],
                session_id=decision["session_id"],
                reviewer_name=decision["recruiter_name"],
                decision=decision["decision"],
                notes=decision["notes"],
                finding_ids=[],
                created_at=decision["created_at"],
            )
        )

    op.create_table(
        "reviewed_precedents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("human_review_id", sa.String(length=36), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("jurisdiction", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("policy_version_id", sa.String(length=36), nullable=False),
        sa.Column("index_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["human_review_id"], ["human_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("human_review_id"),
    )
    op.create_index("ix_reviewed_precedents_category", "reviewed_precedents", ["category"])
    op.create_index("ix_reviewed_precedents_jurisdiction", "reviewed_precedents", ["jurisdiction"])
    op.drop_index("ix_revision_decisions_session_id", table_name="revision_decisions")
    op.drop_table("revision_decisions")
    sessions = sa.table("compliance_sessions", sa.column("status", sa.String()))
    op.execute(
        sessions.update()
        .where(sessions.c.status == "review_complete")
        .values(status="needs_review")
    )
