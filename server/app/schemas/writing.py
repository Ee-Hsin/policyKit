"""Writing-assistance request and response schemas."""

from pydantic import BaseModel, Field

from app.schemas.policies import EmploymentType


class InitialPostingDraftCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    role_ideas: str = Field(min_length=10, max_length=5_000)
    organization_name: str | None = Field(default=None, max_length=240)
    target_locations: list[str] = Field(default_factory=list)
    employment_type: EmploymentType = "full_time"


class InitialPostingDraftRead(BaseModel):
    suggested_content: str
