from typing import List, Optional
from pydantic import BaseModel
from enum import Enum

class PolicyCategory(str, Enum):
    LEGAL = "legal"
    ETHICS = "ethics"
    TRANSPARENCY = "transparency"
    SECURITY = "security"
    UNDEFINED = "undefined"

class SecurityIssue(BaseModel):
    type: str
    pattern: Optional[str] = None
    description: str

class SecurityCheck(BaseModel):
    is_safe: bool
    confidence: float  # Removed constraints for OpenAI compatibility
    security_issues: Optional[List[SecurityIssue]] = None
    reasoning: str

class JobPostingVerification(BaseModel):
    is_job_posting: bool
    confidence: float  # Removed constraints
    reasoning: str

class PolicyCategoryScore(BaseModel):
    category: PolicyCategory
    confidence: float  # Removed constraints
    reasoning: str

class PolicyCategoryScoreList(BaseModel):
    categories: List[PolicyCategoryScore]

class PolicyViolationContent(BaseModel):
    policy_id: str
    policy_title: str
    violated_content: str
    justification: str
    confidence: float  # Removed constraints but supposed to be 0-1

class PolicyInvestigationResult(BaseModel):
    category: PolicyCategory
    violations: List[PolicyViolationContent]
    reasoning: str

class FinalOutput(BaseModel):
    has_violations: bool
    violations: List[PolicyViolationContent]
    metadata: Optional[dict] = None  # For internal use only, won't be included in JSON output

    class Config:
        json_schema_extra = {
            "example": {
                "has_violations": True,
                "violations": [
                    {
                        "policy_id": "POL001",
                        "policy_title": "No Illegal Activities",
                        "violated_content": "Looking for someone to create fake IDs",
                        "justification": "Content explicitly requests creation of fraudulent documents",
                        "confidence": 0.95
                    }
                ]
            }
        } 