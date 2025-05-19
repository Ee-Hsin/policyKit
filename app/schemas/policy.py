from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, create_model, validator
from enum import Enum
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.policy import PolicyCategory

def create_policy_category_score_list_model(categories: Set[str]) -> type[BaseModel]:
    """Create a dynamic PolicyCategoryScoreList model with validation."""
    # Create the score model with a custom validator
    class DynamicPolicyCategoryScore(BaseModel):
        category: str
        confidence: float
        reasoning: str
        
        @validator('category')
        def validate_category(cls, v, values, **kwargs):
            if v not in categories:
                raise ValueError(f"Category must be one of: {', '.join(categories)}")
            return v
    
    # Create the list model
    return create_model(
        'DynamicPolicyCategoryScoreList',
        categories=(List[DynamicPolicyCategoryScore], ...),
        __base__=BaseModel
    )

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

# These will be replaced with dynamic models at runtime
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