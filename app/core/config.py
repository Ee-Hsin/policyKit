"""Application configuration settings."""

from typing import List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "PolicyKit"
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    # OpenAI Settings
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Database Settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "policykit"
    DB_ECHO_LOG: bool = False
    
    @property
    def DATABASE_URL(self) -> str:
        """Get the database URL."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Policy Checker Settings
    JOB_POSTING_CONFIDENCE_THRESHOLD: float = 0.9
    SECURITY_CHECK_CONFIDENCE_THRESHOLD: float = 0.9
    POLICY_INVESTIGATION_CONFIDENCE_THRESHOLD: float = 0.7
    FINAL_OUTPUT_CONFIDENCE_THRESHOLD: float = 0.85
    MAX_PARALLEL_INVESTIGATIONS: int = 3
    LLM_INVESTIGATION_TIMEOUT: int = 30
    VECTOR_SIMILARITY_THRESHOLD: float = 0.98  # 98% similarity threshold for RAG
    
    # Injection Patterns
    INJECTION_PATTERNS: List[Dict[str, Any]] = [
        {
            "pattern": "ignore previous instructions",
            "description": "Attempt to override system instructions"
        },
        {
            "pattern": "system prompt",
            "description": "Attempt to access system prompt"
        },
        {
            "pattern": "disregard all prior",
            "description": "Attempt to override system behavior"
        },
        {
            "pattern": "forget your previous",
            "description": "Attempt to reset system state"
        },
        {
            "pattern": "you are now",
            "description": "Attempt to change system identity"
        },
        {
            "pattern": "bypass security",
            "description": "Attempt to circumvent security controls"
        },
        {
            "pattern": "reveal your training",
            "description": "Attempt to extract system information"
        },
        {
            "pattern": "let's play a game",
            "description": "Common social engineering pattern"
        },
        {
            "pattern": "pretend to be",
            "description": "Attempt to change system behavior"
        },
        {
            "pattern": "do not check",
            "description": "Attempt to bypass validation"
        }
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 