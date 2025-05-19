from typing import List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    PROJECT_NAME: str = "Policy Checker API"
    API_V1_STR: str = "/api/v1"
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    # OpenAI Configuration
    OPENAI_API_KEY: str
    
    # Policy Checker Configuration
    JOB_POSTING_CONFIDENCE_THRESHOLD: float = 0.7
    POLICY_INVESTIGATION_THRESHOLD: float = 0.5
    MAX_PARALLEL_INVESTIGATIONS: int = 3
    LLM_INVESTIGATION_TIMEOUT: int = 30
    
    # Injection Patterns
    INJECTION_PATTERNS: List[dict] = [
        {
            "pattern": "ignore previous instructions",
            "description": "Attempt to ignore previous instructions"
        },
        {
            "pattern": "you are now",
            "description": "Attempt to change AI behavior"
        }
    ]
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 