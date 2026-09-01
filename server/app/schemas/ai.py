"""Strict contracts for OpenAI model calls and agent tools."""

from pydantic import BaseModel, Field, model_validator

from app.models.entities import FindingStatus


class PolicyAssessment(BaseModel):
    policy_id: str
    status: FindingStatus
    evidence_text: str | None = None
    evidence_start: int | None = Field(default=None, ge=0)
    evidence_end: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_evidence_shape(self) -> "PolicyAssessment":
        values = (self.evidence_text, self.evidence_start, self.evidence_end)
        if any(value is not None for value in values) and any(value is None for value in values):
            raise ValueError("Evidence text and offsets must be supplied together")
        if self.evidence_start is not None and self.evidence_end is not None:
            if self.evidence_end <= self.evidence_start:
                raise ValueError("Evidence end must be greater than evidence start")
        return self


class ComplianceCheckOutput(BaseModel):
    input_type: str = Field(pattern=r"^(job_posting|not_job_posting)$")
    assessments: list[PolicyAssessment]
    summary: str


class ToolCall(BaseModel):
    call_id: str
    name: str
    arguments: dict


class AgentTurn(BaseModel):
    response_id: str | None = None
    tool_calls: list[ToolCall]
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProposedEdit(BaseModel):
    original_text: str = Field(min_length=1)
    replacement_text: str
    reason: str = Field(min_length=1)
    policy_keys: list[str] = Field(min_length=1)


class ProposedRevision(BaseModel):
    revised_text: str = Field(min_length=30)
    changes: list[ProposedEdit] = Field(min_length=1)
