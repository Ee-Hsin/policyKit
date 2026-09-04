"""Recruiter-facing writing assistance that does not save model output."""

import logging

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.integrations.openai_gateway import MissingAIConfigurationError, OpenAIGateway
from app.schemas.writing import InitialPostingDraftCreate, InitialPostingDraftRead

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drafts", response_model=InitialPostingDraftRead)
async def draft_posting(request: InitialPostingDraftCreate) -> InitialPostingDraftRead:
    try:
        output = await OpenAIGateway(get_settings()).draft_posting(
            details=request.model_dump(mode="json")
        )
    except MissingAIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Initial job-posting draft failed")
        raise HTTPException(
            status_code=502, detail="Writing assistance could not complete"
        ) from error
    return InitialPostingDraftRead(suggested_content=output.suggested_content)
