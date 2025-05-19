from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.policy import JobPostingRequest
from app.services.policy_checker import PolicyChecker
from app.core.config import settings

router = APIRouter()

@router.post("/check-posting")
async def check_job_posting(
    request: JobPostingRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Check a job posting for policy violations.
    Args:
        request: JobPostingRequest containing the job description and optional image path
    Returns:
        Policy check results including any violations found
    """
    try:
        if not request.job_description:
            raise HTTPException(status_code=422, detail="Job description is required")
        
        policy_checker = PolicyChecker(db=db, api_key=settings.OPENAI_API_KEY)
        result = await policy_checker.check_job_posting(
            job_description=request.job_description,
            image_path=request.image_path
        )
        return result
    except Exception as e:
        # raise the specific error if there is one
        if hasattr(e, "detail"):
            raise HTTPException(status_code=422, detail=e.detail)
        else:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 