from typing import List, Optional, Any, Set, Type, Union
from pydantic import BaseModel, create_model, validator

def create_policy_category_score_list_model(category_names: Set[str], category_ids: Set[int]) -> Type[BaseModel]:
    """Create dynamic PolicyCategoryScoreList model with validation."""
    # Create the score model with a custom validator
    class DynamicPolicyCategoryScore(BaseModel):
        category: str
        category_id: int
        confidence: float
        reasoning: str
        
        @validator('category')
        def validate_category(cls, v, values, **kwargs):
            if v not in category_names:
                raise ValueError(f"Category must be one of: {', '.join(category_names)}")
            return v
        
        @validator('category_id')
        def validate_category_id(cls, v, values, **kwargs):
            if v not in category_ids:
                raise ValueError(f"Category ID must be one of: {', '.join(str(id) for id in category_ids)}")
            return v
    
    # Create the list model
    DynamicPolicyCategoryScoreList = create_model(
        'DynamicPolicyCategoryScoreList',
        categories=(List[DynamicPolicyCategoryScore], ...),
        __base__=BaseModel
    )
    
    return DynamicPolicyCategoryScoreList

class JobPostingRequest(BaseModel):
    """Request body for job posting verification, this is what is passed into check_job_posting"""
    job_description: str
    image_path: Optional[str] = None
    
class SafetyKitViolation(BaseModel):
    """A violation model specifically for safetykit (for prompt injections and not job postings)
    This is used in the violations list in the FinalOutput model."""
    category: str
    confidence: float
    reasoning: str
    
class StandardViolation(BaseModel):
    """Standard violation model. This is used in the violations list in the FinalOutput model."""
    category: str
    policy: list[str]
    reasoning: str
    content: str
class FinalOutput(BaseModel):
    """The final Output of the API, returned by check_job_posting"""
    has_violations: bool
    violations: List[Union[StandardViolation, SafetyKitViolation]]
    metadata: Optional[dict] = None 

class SecurityCheck(BaseModel):
    """Security check model. This is returned from the _check_security method."""
    is_safe: bool
    confidence: float
    reasoning: str

class JobPostingVerification(BaseModel):
    """Job posting verification model. This is returned from the _verify_job_posting method."""
    is_job_posting: bool
    confidence: float
    reasoning: str
    
class CategoryInvestigation(BaseModel):
    """Category investigation model. This is returned from the _investigate_individual_category method.
    We identify a list of policies from that category that are violated in the job posting."""
    category_id: int
    policies_violated_ids : list[int]
    confidence: float
    reasoning: str
    content: str
