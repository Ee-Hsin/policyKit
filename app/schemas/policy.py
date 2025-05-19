from typing import List, Optional
from pydantic import BaseModel

class JobPostingRequest(BaseModel):
    job_description: str
    image_path: Optional[str] = None

class SecurityIssue(BaseModel):
    type: str
    pattern: Optional[str] = None
    description: str

class SecurityCheck(BaseModel):
    is_safe: bool
    confidence: float
    security_issues: Optional[List[SecurityIssue]] = None
    reasoning: str

class JobPostingVerification(BaseModel):
    is_job_posting: bool
    confidence: float
    reasoning: str

class PolicyCategoryScore(BaseModel):
    category: str
    confidence: float
    reasoning: str

class PolicyCategoryScoreList(BaseModel):
    categories: List[PolicyCategoryScore]

class PolicyViolationContent(BaseModel):
    policy_id: str #need to find a way to make this an enum of options from the policy data
    policy_title: str #need to find a way to make this an enum of options from the policy data
    violated_content: str
    justification: str
    confidence: float

class PolicyInvestigationResult(BaseModel):
    category: str
    violations: List[PolicyViolationContent]
    reasoning: str

class FinalOutput(BaseModel):
    has_violations: bool
    violations: List[PolicyViolationContent]
    metadata: Optional[dict] = None 