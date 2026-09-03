"""Policy administration schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.jurisdictions import US_STATE_CODE_SET, normalize_location

EmploymentType = Literal["full_time", "part_time", "contract", "temporary", "internship"]
PolicyPlatform = Literal["policykit"]


def canonical_policy_jurisdictions(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        canonical_value = value.strip().upper()
        if canonical_value in {"GLOBAL", "US", "GB", "CA"}:
            jurisdiction = canonical_value
        elif canonical_value.startswith("US-") and canonical_value[3:] in US_STATE_CODE_SET:
            jurisdiction = canonical_value
        elif canonical_value.startswith("US-"):
            raise ValueError(f"Unsupported jurisdiction: {value}")
        else:
            jurisdiction = normalize_location(value)
        if jurisdiction.startswith("UNRESOLVED:"):
            raise ValueError(f"Unsupported jurisdiction: {value}")
        if jurisdiction not in normalized:
            normalized.append(jurisdiction)
    if "GLOBAL" in normalized and len(normalized) > 1:
        raise ValueError("GLOBAL cannot be combined with another jurisdiction")
    return normalized


class PolicyVersionFields(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    category: str = Field(min_length=2, max_length=80)
    rule_text: str = Field(min_length=10)
    rationale: str | None = None
    remediation: str | None = None
    enforcement_level: str = "standard"
    jurisdictions: list[str] = Field(default_factory=lambda: ["GLOBAL"])
    employment_types: list[EmploymentType] = Field(default_factory=list)
    platforms: list[PolicyPlatform] = Field(default_factory=list)
    violation_examples: list[str] = Field(default_factory=list)
    compliant_examples: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    effective_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("jurisdictions")
    @classmethod
    def normalize_jurisdictions(cls, values: list[str]) -> list[str]:
        return canonical_policy_jurisdictions(values)


class PolicyCreate(PolicyVersionFields):
    key: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,79}$")


class PolicyDraftUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    rule_text: str | None = Field(default=None, min_length=10)
    rationale: str | None = None
    remediation: str | None = None
    enforcement_level: str | None = None
    jurisdictions: list[str] | None = None
    employment_types: list[EmploymentType] | None = None
    platforms: list[PolicyPlatform] | None = None
    violation_examples: list[str] | None = None
    compliant_examples: list[str] | None = None
    exceptions: list[str] | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("jurisdictions")
    @classmethod
    def normalize_jurisdictions(cls, values: list[str] | None) -> list[str] | None:
        return canonical_policy_jurisdictions(values) if values is not None else None

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> "PolicyDraftUpdate":
        required_fields = {
            "title",
            "category",
            "rule_text",
            "enforcement_level",
            "jurisdictions",
            "employment_types",
            "platforms",
            "violation_examples",
            "compliant_examples",
            "exceptions",
        }
        invalid_fields = sorted(
            field
            for field in self.model_fields_set & required_fields
            if getattr(self, field) is None
        )
        if invalid_fields:
            raise ValueError(f"Fields cannot be null: {', '.join(invalid_fields)}")
        return self


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
    model_config = ConfigDict(extra="forbid")

    posting_text: str = Field(min_length=20)


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
