from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import policy_checker
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for checking job postings against policy violations",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    policy_checker.router,
    prefix=settings.API_V1_STR,
    tags=["policy-checker"]
) 