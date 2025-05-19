from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from policy_checker import PolicyChecker
import os
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Policy Checker API",
    description="API for checking job postings against policy violations",
    version="1.0.0"
)

# Initialize the policy checker
policy_checker = PolicyChecker(api_key=os.getenv("OPENAI_API_KEY"))

class JobPostingRequest(BaseModel):
    job_description: str
    image_path: Optional[str] = None

@app.post("/check-posting")
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

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    # Ensure OPENAI_API_KEY is set
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    # Run the FastAPI server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Enable auto-reload during development
    ) 