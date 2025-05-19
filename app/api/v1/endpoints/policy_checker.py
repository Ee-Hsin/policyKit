from fastapi import APIRouter, HTTPException
from app.schemas.policy import JobPostingRequest
from app.services.policy_checker import PolicyChecker
from app.core.config import settings

router = APIRouter()

# Initialize the policy checker
policy_checker = PolicyChecker(api_key=settings.OPENAI_API_KEY)

@router.post("/check-posting")
async def check_job_posting(request: JobPostingRequest):
    """
    Check a job posting for policy violations.
    
    Args:
        request: JobPostingRequest containing the job description and optional image path
        
    Returns:
        Policy check results including any violations found
    """
    try:
        result = await policy_checker.check_job_posting(
            job_description=request.job_description,
            image_path=request.image_path
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 