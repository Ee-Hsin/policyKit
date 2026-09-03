"""Create the greenfield PolicyKit schema.

Revision ID: 0001_greenfield_schema
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_greenfield_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policies_key", "policies", ["key"], unique=True)

    op.create_table(
        "policy_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )

    op.create_table(
        "job_postings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("organization_name", sa.String(length=240), nullable=True),
        sa.Column("target_locations", sa.JSON(), nullable=False),
        sa.Column("employment_type", sa.String(length=60), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "compliance_cache_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("policy_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("model_namespace", sa.String(length=160), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_snapshot_id"], ["policy_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_cache_entries_cache_key",
        "compliance_cache_entries",
        ["cache_key"],
        unique=True,
    )
    op.create_index(
        "ix_compliance_cache_entries_policy_snapshot_id",
        "compliance_cache_entries",
        ["policy_snapshot_id"],
    )

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("posting_text", sa.Text(), nullable=False),
        sa.Column("jurisdictions", sa.JSON(), nullable=False),
        sa.Column("expected_assessments", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("enforcement_level", sa.String(length=24), nullable=False),
        sa.Column("jurisdictions", sa.JSON(), nullable=False),
        sa.Column("employment_types", sa.JSON(), nullable=False),
        sa.Column("platforms", sa.JSON(), nullable=False),
        sa.Column("violation_examples", sa.JSON(), nullable=False),
        sa.Column("compliant_examples", sa.JSON(), nullable=False),
        sa.Column("exceptions", sa.JSON(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", "version", name="uq_policy_version"),
    )
    op.create_index("ix_policy_versions_category", "policy_versions", ["category"])
    op.create_index("ix_policy_versions_policy_id", "policy_versions", ["policy_id"])
    op.create_index("ix_policy_versions_status", "policy_versions", ["status"])

    op.create_table(
        "policy_snapshot_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["policy_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "policy_version_id", name="uq_snapshot_policy_version"),
    )
    op.create_index(
        "ix_policy_snapshot_items_policy_version_id",
        "policy_snapshot_items",
        ["policy_version_id"],
    )
    op.create_index(
        "ix_policy_snapshot_items_snapshot_id", "policy_snapshot_items", ["snapshot_id"]
    )

    op.create_table(
        "posting_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("posting_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("posting_id", "version", name="uq_posting_version"),
    )

    op.create_table(
        "compliance_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("posting_id", sa.String(length=36), nullable=False),
        sa.Column("current_posting_version_id", sa.String(length=36), nullable=False),
        sa.Column("policy_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("current_question", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("agent_iterations", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["current_posting_version_id"], ["posting_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["policy_snapshot_id"], ["policy_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_sessions_status", "compliance_sessions", ["status"])

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["compliance_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_agent_step_sequence"),
    )
    op.create_index("ix_agent_steps_session_id", "agent_steps", ["session_id"])

    op.create_table(
        "compliance_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("posting_version_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("evidence_start", sa.Integer(), nullable=True),
        sa.Column("evidence_end", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["posting_version_id"], ["posting_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["compliance_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_findings_policy_version_id",
        "compliance_findings",
        ["policy_version_id"],
    )
    op.create_index(
        "ix_compliance_findings_posting_version_id",
        "compliance_findings",
        ["posting_version_id"],
    )
    op.create_index("ix_compliance_findings_session_id", "compliance_findings", ["session_id"])
    op.create_index("ix_compliance_findings_status", "compliance_findings", ["status"])

    op.create_table(
        "proposed_changes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("from_posting_version_id", sa.String(length=36), nullable=False),
        sa.Column("to_posting_version_id", sa.String(length=36), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("replacement_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("policy_keys", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_posting_version_id"], ["posting_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["compliance_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["to_posting_version_id"], ["posting_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_proposed_changes_session_id", "proposed_changes", ["session_id"])

    op.create_table(
        "human_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_name", sa.String(length=160), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["compliance_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_reviews_session_id", "human_reviews", ["session_id"])

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


def downgrade() -> None:
    op.drop_index("ix_reviewed_precedents_jurisdiction", table_name="reviewed_precedents")
    op.drop_index("ix_reviewed_precedents_category", table_name="reviewed_precedents")
    op.drop_table("reviewed_precedents")
    op.drop_index("ix_human_reviews_session_id", table_name="human_reviews")
    op.drop_table("human_reviews")
    op.drop_index("ix_proposed_changes_session_id", table_name="proposed_changes")
    op.drop_table("proposed_changes")
    op.drop_index("ix_compliance_findings_status", table_name="compliance_findings")
    op.drop_index("ix_compliance_findings_session_id", table_name="compliance_findings")
    op.drop_index("ix_compliance_findings_posting_version_id", table_name="compliance_findings")
    op.drop_index("ix_compliance_findings_policy_version_id", table_name="compliance_findings")
    op.drop_table("compliance_findings")
    op.drop_index("ix_agent_steps_session_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_compliance_sessions_status", table_name="compliance_sessions")
    op.drop_table("compliance_sessions")
    op.drop_table("posting_versions")
    op.drop_index("ix_policy_snapshot_items_snapshot_id", table_name="policy_snapshot_items")
    op.drop_index("ix_policy_snapshot_items_policy_version_id", table_name="policy_snapshot_items")
    op.drop_table("policy_snapshot_items")
    op.drop_index("ix_policy_versions_status", table_name="policy_versions")
    op.drop_index("ix_policy_versions_policy_id", table_name="policy_versions")
    op.drop_index("ix_policy_versions_category", table_name="policy_versions")
    op.drop_table("policy_versions")
    op.drop_table("eval_cases")
    op.drop_index(
        "ix_compliance_cache_entries_policy_snapshot_id",
        table_name="compliance_cache_entries",
    )
    op.drop_index("ix_compliance_cache_entries_cache_key", table_name="compliance_cache_entries")
    op.drop_table("compliance_cache_entries")
    op.drop_table("job_postings")
    op.drop_table("policy_snapshots")
    op.drop_index("ix_policies_key", table_name="policies")
    op.drop_table("policies")
