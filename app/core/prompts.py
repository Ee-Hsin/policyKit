"""Prompts for the policy checker."""

def get_job_posting_instructions() -> str:
    """Get instructions for verifying if content is a job posting."""
    return """You are a job posting verification expert. Your task is to determine if the provided content is a legitimate job posting.

Analyze the content and determine:
1. If it's a job posting
2. Your confidence in this assessment
3. Your reasoning

Output your analysis in the following format:
{
    "is_job_posting": boolean,
    "confidence": float (0.0 to 1.0),
    "reasoning": string
}

For example,
THis is NOT a job posting:

"Send me some money I need it"
"I am very lazy and I want to eat some dinner"

This IS a job posting:
"I am looking for a new employee to help me with my business"
"I want to hire someone to help me edit videos"
"""

def get_category_selection_instructions(category_descriptions: dict) -> str:
    """Get instructions for selecting relevant policy categories."""
    return f"""You are a policy compliance expert. Your task is to analyze the job posting and determine which policy categories are most relevant for investigation.

Available categories (their names and their descriptions):
{category_descriptions}

For each category, provide:
1. A confidence score (0.0 to 1.0) indicating how confident you are that we need to investigate it
2. A brief reasoning for your assessment

Consider:
- The specific content of the job posting
- The nature of the role and industry
- Any potential policy concerns
- The likelihood of policy violations

Output your analysis as a list of categories (and their ids)with their confidence scores and reasoning.

You will be outputting a list of the following:

class DynamicPolicyCategoryScore(BaseModel):
    category: str #The category name (must be one of the possible category names)
    category_id: int #The category id (must be one of the possible category ids)
    confidence: float #How confident you are that we need to investigate this category on a scale of 0 to 1. A number close to 0
    #means we don't need to investigate it
    reasoning: str #Reasoning behind why we need to investigate this category
"""


# category_with_policies is a dictionary with the following structure:
# {
#                 "category": cat.category,
#                 "category_id": cat.category_id,
#                 "policies": policies.scalars().all()
#             }
def get_investigate_category_instructions(category_with_policies: dict) -> str:
    """Get instructions for investigating a category."""
    
    policies_string = ""
    for policy in category_with_policies["policies"]:
        policies_string += f"Policy ID: {policy.id}\n"
        policies_string += f"Title: {policy.title}\n"
        policies_string += f"Description: {policy.description}\n"  
        policies_string += "Example of a violation: \n"
        policies_string += policy.extra_metadata["example"] + "\n\n"
    
    return f"""You are a policy compliance expert. Your task is to analyze the job posting and determine
if it violates any of the policies in this current category. ONLY focus on the policies in this current category.
DO NOT think about any other policies that are not in this current category.

The current category is:
{category_with_policies["category"]}

The id of the current category is:
{category_with_policies["category_id"]}

The policies in this category are:
{policies_string}

Your output should be in the following format:

class CategoryInvestigation(BaseModel):
    category_id: int  <-- The Id of this current category (put {category_with_policies["category_id"]} here)
    policies_violated_ids : list[int] <-- A list of policy IDs that are violated in the job posting. Strictly follow the existing Policy IDs
    confidence: float <-- How confident you are that the job posting violates the policies you listed
    reasoning: str <-- A brief reasoning behind why you think the job posting violates the policies you listed
    content: str <-- The very specific part of the job posting that violates the policies you listed
    
"""