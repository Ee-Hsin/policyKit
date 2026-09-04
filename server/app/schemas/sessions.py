"""Compliance-session schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.policies import EmploymentType, PolicyPlatform


class ComplianceSessionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    job_description: str = Field(min_length=30, max_length=100_000)
    organization_name: str | None = Field(default=None, max_length=240)
    target_locations: list[str] = Field(default_factory=list)
    employment_type: EmploymentType = "full_time"
    platform: PolicyPlatform = "policykit"


class PostingVersionCreate(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=36)
    content: str = Field(min_length=30, max_length=100_000)

    @model_validator(mode="after")
    def reject_blank_content(self) -> "PostingVersionCreate":
        if not self.content.strip():
            raise ValueError("Posting content cannot be blank")
        return self


class WritingSuggestionCreate(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=36)
    draft_text: str = Field(min_length=30, max_length=20_000)
    instruction: str = Field(min_length=3, max_length=2_000)
    selection_start: int | None = Field(default=None, ge=0)
    selection_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_selection(self) -> "WritingSuggestionCreate":
        bounds = (self.selection_start, self.selection_end)
        if any(value is not None for value in bounds) and any(value is None for value in bounds):
            raise ValueError("Selection start and end must be supplied together")
        if self.selection_start is not None and self.selection_end is not None:
            if self.selection_end <= self.selection_start:
                raise ValueError("Selection end must be greater than selection start")
            if self.selection_end > len(self.draft_text):
                raise ValueError("Selection cannot extend beyond the draft")
        elif len(self.draft_text) > 12_000:
            raise ValueError("Select a passage when the draft is longer than 12,000 characters")
        return self


class WritingSuggestionRead(BaseModel):
    base_version_id: str
    suggested_text: str
    summary: str


class ComplianceCheckCreate(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=36)


class SessionMessageCreate(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=36)
    message: str = Field(min_length=1, max_length=5_000)


class RevisionApproval(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=36)
    approved: bool
    reviewer_name: str = Field(default="Demo recruiter", min_length=2, max_length=160)
    notes: str | None = Field(default=None, max_length=2_000)


class PublishPostingRequest(BaseModel):
    base_version_id: str = Field(min_length=1, max_length=36)
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
    check_state: Literal["never_run", "running", "current", "stale"]
    last_checked_posting_version_id: str | None
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
    base_version_id: str
    reviewer_name: str = Field(min_length=2, max_length=160)
    decision: str = Field(pattern=r"^(approve|reject|request_changes)$")
    notes: str | None = Field(default=None, max_length=3_000)
    promote_to_precedent: bool = False
    finding_id: str | None = None
