"""Version 1 route registry."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, policies, sessions

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(sessions.router, prefix="/compliance-sessions", tags=["sessions"])
router.include_router(policies.router, prefix="/policies", tags=["policies"])
