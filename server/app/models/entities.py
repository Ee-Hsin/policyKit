"""Durable PolicyKit domain entities."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utc_now


def new_id() -> str:
    return str(uuid.uuid4())


class PolicyStatus(enum.StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    PUBLISHED = "published"
    RETIRED = "retired"


class IndexStatus(enum.StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class ComplianceSessionStatus(enum.StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    INVESTIGATING = "investigating"
    WAITING_FOR_INFORMATION = "waiting_for_information"
    CHANGES_PROPOSED = "changes_proposed"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    READY_TO_PUBLISH = "ready_to_publish"
    NEEDS_REVIEW = "needs_review"
    PUBLISHED = "published"
    FAILED = "failed"


class FindingStatus(enum.StrEnum):
    VIOLATION = "violation"
    NO_VIOLATION = "no_violation"
    UNCERTAIN = "uncertain"


class StepStatus(enum.StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ChangeStatus(enum.StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="PolicyVersion.version"
    )


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version", name="uq_policy_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24), default=PolicyStatus.DRAFT.value, index=True)
    rule_text: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    enforcement_level: Mapped[str] = mapped_column(String(24), default="standard")
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    employment_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    violation_examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    compliant_examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    exceptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_status: Mapped[str] = mapped_column(String(24), default=IndexStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    policy: Mapped[Policy] = relationship(back_populates="versions")


class PolicySnapshot(Base):
    __tablename__ = "policy_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    items: Mapped[list[PolicySnapshotItem]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class PolicySnapshotItem(Base):
    __tablename__ = "policy_snapshot_items"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "policy_version_id", name="uq_snapshot_policy_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("policy_snapshots.id", ondelete="CASCADE"), index=True
    )
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="RESTRICT"), index=True
    )

    snapshot: Mapped[PolicySnapshot] = relationship(back_populates="items")
    policy_version: Mapped[PolicyVersion] = relationship()


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(240))
    organization_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    target_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    employment_type: Mapped[str] = mapped_column(String(60), default="full_time")
    platform: Mapped[str] = mapped_column(String(80), default="policykit")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    versions: Mapped[list[PostingVersion]] = relationship(
        back_populates="posting",
        cascade="all, delete-orphan",
        foreign_keys="PostingVersion.posting_id",
        order_by="PostingVersion.version",
    )


class PostingVersion(Base):
    __tablename__ = "posting_versions"
    __table_args__ = (UniqueConstraint("posting_id", "version", name="uq_posting_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    posting_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="user")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    posting: Mapped[JobPosting] = relationship(back_populates="versions", foreign_keys=[posting_id])


class ComplianceSession(Base):
    __tablename__ = "compliance_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    posting_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    current_posting_version_id: Mapped[str] = mapped_column(
        ForeignKey("posting_versions.id", ondelete="RESTRICT")
    )
    policy_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(40), default=ComplianceSessionStatus.DRAFT.value, index=True
    )
    goal: Mapped[str] = mapped_column(Text)
    current_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_iterations: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    posting: Mapped[JobPosting] = relationship(foreign_keys=[posting_id])
    current_posting_version: Mapped[PostingVersion] = relationship(
        foreign_keys=[current_posting_version_id]
    )
    policy_snapshot: Mapped[PolicySnapshot | None] = relationship()
    steps: Mapped[list[AgentStep]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="AgentStep.sequence"
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("session_id", "sequence", name="uq_agent_step_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("compliance_sessions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default=StepStatus.STARTED.value)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[ComplianceSession] = relationship(back_populates="steps")


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("compliance_sessions.id", ondelete="CASCADE"), index=True
    )
    posting_version_id: Mapped[str] = mapped_column(
        ForeignKey("posting_versions.id", ondelete="CASCADE"), index=True
    )
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), index=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    policy_version: Mapped[PolicyVersion] = relationship()


class ProposedChange(Base):
    __tablename__ = "proposed_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("compliance_sessions.id", ondelete="CASCADE"), index=True
    )
    from_posting_version_id: Mapped[str] = mapped_column(
        ForeignKey("posting_versions.id", ondelete="CASCADE")
    )
    to_posting_version_id: Mapped[str] = mapped_column(
        ForeignKey("posting_versions.id", ondelete="CASCADE")
    )
    original_text: Mapped[str] = mapped_column(Text)
    replacement_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    policy_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default=ChangeStatus.PROPOSED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("compliance_sessions.id", ondelete="CASCADE"), index=True
    )
    reviewer_name: Mapped[str] = mapped_column(String(160))
    decision: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReviewedPrecedent(Base):
    __tablename__ = "reviewed_precedents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    human_review_id: Mapped[str] = mapped_column(
        ForeignKey("human_reviews.id", ondelete="CASCADE"), unique=True
    )
    excerpt: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(40))
    jurisdiction: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="RESTRICT")
    )
    index_status: Mapped[str] = mapped_column(String(24), default=IndexStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240), unique=True)
    posting_text: Mapped[str] = mapped_column(Text)
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    expected_assessments: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(40), default="authored")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ComplianceCacheEntry(Base):
    __tablename__ = "compliance_cache_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    policy_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("policy_snapshots.id", ondelete="CASCADE"), index=True
    )
    model_namespace: Mapped[str] = mapped_column(String(160))
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
