"""Policy administration schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyVersionFields(BaseModel):
    rule_text: str = Field(min_length=10)
    rationale: str | None = None
    remediation: str | None = None
    enforcement_level: str = "standard"
    jurisdictions: list[str] = Field(default_factory=lambda: ["GLOBAL"])
    employment_types: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    violation_examples: list[str] = Field(default_factory=list)
    compliant_examples: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    effective_at: datetime | None = None
    expires_at: datetime | None = None


class PolicyCreate(PolicyVersionFields):
    key: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,79}$")
    title: str = Field(min_length=3, max_length=240)
    category: str = Field(min_length=2, max_length=80)


class PolicyDraftUpdate(PolicyVersionFields):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    category: str | None = Field(default=None, min_length=2, max_length=80)


class PolicyVersionRead(PolicyVersionFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    status: str
    index_status: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PolicySummary(BaseModel):
    id: str
    key: str
    title: str
    category: str
    current_version: int
    status: str
    index_status: str
    jurisdictions: list[str]
    updated_at: datetime


class PolicyDetail(BaseModel):
    id: str
    key: str
    title: str
    category: str
    versions: list[PolicyVersionRead]


class PolicyTestRequest(BaseModel):
    posting_text: str = Field(min_length=20)
    jurisdictions: list[str] = Field(default_factory=list)


class PolicyTestResponse(BaseModel):
    policy_key: str
    status: str
    evidence_text: str | None
    reason: str
    confidence: float | None


class PublishPolicyResponse(BaseModel):
    policy: PolicyDetail
    snapshot_version: int
    index_status: str
