from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.policy import JobPostingRequest
from app.services.policy_checker import PolicyChecker
from app.core.config import settings
from typing import Optional

router = APIRouter()

@router.post("/check-posting")
async def check_job_posting(
    request: JobPostingRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Check a job posting for policy violations.
    Args:
        job_description: The job description text
    Returns:
        Policy check results including any violations found
    """
    try:
        if not request.job_description:
            raise HTTPException(status_code=422, detail="Job description is required")
        
        policy_checker = PolicyChecker(db=db, api_key=settings.OPENAI_API_KEY)
        result = await policy_checker.check_job_posting(
            job_description=request.job_description
        )
        return result
    except Exception as e:
        # raise the specific error if there is one
        if hasattr(e, "detail"):
            raise HTTPException(status_code=422, detail=e.detail)
        else:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-image")
async def check_image(
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Check an image for policy violations.
    Args:
        image: The image file to check
    Returns:
        Policy check results including any violations found
    """
    try:
        if not image:
            raise HTTPException(status_code=422, detail="Image is required")
        
        # Validate file type
        if not image.content_type.startswith('image/'):
            raise HTTPException(status_code=422, detail="File must be an image")
        
        policy_checker = PolicyChecker(db=db, api_key=settings.OPENAI_API_KEY)
        result = await policy_checker.check_image(image)
        return result
    except Exception as e:
        if hasattr(e, "detail"):
            raise HTTPException(status_code=422, detail=e.detail)
        else:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 