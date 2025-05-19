def get_job_posting_instructions() -> str:
    """Get instructions for job posting verification."""
    return """You are a job posting validator. Your task is to verify if the content is a job posting. 
Return a JobPostingVerification object with your analysis.

class JobPostingVerification(BaseModel):
    is_job_posting: bool #<-- tells us if it is a job posting
    confidence: float #Confidence score from 0 to 1
    reasoning: str #Reasoning why it is a job posting or not
"""

def get_category_selection_instructions(category_descriptions: dict) -> str:
    """Get instructions for category selection."""
    return """You are looking at a job posting.

This is a list of policy categories and descriptions:
{category_descriptions}

Your task is to identify if the job posting may be in violation of any of the policy categories,
and if so, return a list of policy categories that we need to investigate.

Return a PolicyCategoryScoreList object that contains a list of policy categories and scores (confidence score from 0 to 1)
with your analysis.

Here is the schema of a PolicyCategoryScoreList object and the categories it contains:

class PolicyCategoryScoreList(BaseModel):
    categories: List[PolicyCategoryScore] #<-- list of policy categories to investigate
    
class PolicyCategoryScore(BaseModel):
    category: str #The policy category
    confidence: float #Confidence score from 0 to 1 of us needing to investigate this policy category
    reasoning: str #Reasoning why we need to investigate this policy category

Please Note that job postings ARE allowed to specify education levels, 
and they are allowed to specify years of experience. DO NOT Flag these as violations.
"""

def get_policy_investigation_instructions(category: str, category_data: dict) -> str:
    """Get instructions for policy investigation."""
    return """You are a policy compliance checker. Your task is to verify if the job posting complies with the specified policy category.

Your category is: {category}
Here is the policy and description of that category:
{category_data}

Return a PolicyInvestigationResult object with your analysis. Here is the schema:

class PolicyInvestigationResult(BaseModel):
    category: str  # The policy category being investigated
    violations: List[PolicyViolationContent]  # List of violations found
    reasoning: str  # Overall reasoning for the investigation

class PolicyViolationContent(BaseModel):
    policy_id: str  # Unique identifier for the policy
    policy_title: str  # Title of the policy
    violated_content: str  # The specific content that violates the policy
    justification: str  # Explanation of why this content violates the policy
    confidence: float  # Confidence score from 0 to 1 of the violation
    
Please Note that job postings ARE allowed to specify education levels, 
and they are allowed to specify years of experience. DO NOT Flag these as violations.""" 