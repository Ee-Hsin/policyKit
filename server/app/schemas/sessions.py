"""Compliance-session schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ComplianceSessionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    job_description: str = Field(min_length=30, max_length=100_000)
    organization_name: str | None = Field(default=None, max_length=240)
    target_locations: list[str] = Field(default_factory=list)
    employment_type: str = "full_time"
    platform: str = "policykit"


class SessionMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=5_000)


class RevisionApproval(BaseModel):
    approved: bool
    reviewer_name: str = Field(default="Demo recruiter", min_length=2, max_length=160)
    notes: str | None = Field(default=None, max_length=2_000)


class PublishPostingRequest(BaseModel):
    publisher_name: str = Field(default="Demo recruiter", min_length=2, max_length=160)


class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    kind: str
    name: str
    status: str
    input_data: dict
    output_data: dict
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime


class FindingRead(BaseModel):
    id: str
    policy_key: str
    policy_title: str
    category: str
    status: str
    evidence_text: str | None
    evidence_start: int | None
    evidence_end: int | None
    reason: str
    confidence: float | None
    resolved: bool


class ProposedChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_text: str
    replacement_text: str
    reason: str
    policy_keys: list[str]
    status: str
    created_at: datetime


class PostingVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    content: str
    source: str
    approved_at: datetime | None
    created_at: datetime


class ComplianceSessionRead(BaseModel):
    id: str
    status: str
    goal: str
    title: str
    organization_name: str | None
    target_locations: list[str]
    employment_type: str
    platform: str
    current_question: str | None
    error_message: str | None
    policy_snapshot_version: int | None
    current_posting_version: PostingVersionRead
    posting_versions: list[PostingVersionRead]
    findings: list[FindingRead]
    proposed_changes: list[ProposedChangeRead]
    steps: list[AgentStepRead]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class SessionListItem(BaseModel):
    id: str
    title: str
    status: str
    target_locations: list[str]
    finding_count: int
    updated_at: datetime


class HumanReviewCreate(BaseModel):
    reviewer_name: str = Field(min_length=2, max_length=160)
    decision: str = Field(pattern=r"^(approve|reject|request_changes)$")
    notes: str | None = Field(default=None, max_length=3_000)
    promote_to_precedent: bool = False
    finding_id: str | None = None
