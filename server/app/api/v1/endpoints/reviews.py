"""Human-review queue endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.sessions import session_response
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.chroma import ChromaIndex
from app.integrations.openai_gateway import OpenAIGateway
from app.models.entities import (
    ComplianceFinding,
    ComplianceSessionStatus,
    IndexStatus,
    PolicyVersion,
)
from app.repositories import sessions as repository
from app.schemas.sessions import ComplianceSessionRead, HumanReviewCreate

router = APIRouter()


@router.get("", response_model=list[ComplianceSessionRead])
async def review_queue(db: AsyncSession = Depends(get_db)) -> list[ComplianceSessionRead]:
    sessions = await repository.list_sessions(
        db, statuses=[ComplianceSessionStatus.NEEDS_REVIEW.value]
    )
    return [await session_response(db, session) for session in sessions]


@router.post("/{session_id}", response_model=ComplianceSessionRead)
async def resolve_review(
    session_id: str,
    request: HumanReviewCreate,
    db: AsyncSession = Depends(get_db),
) -> ComplianceSessionRead:
    try:
        session = await repository.get_session(db, session_id)
    except repository.SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Compliance session not found") from error
    if session.status != ComplianceSessionStatus.NEEDS_REVIEW.value:
        raise HTTPException(status_code=409, detail="Session does not require human review")

    precedent = None
    finding = None
    if request.promote_to_precedent:
        if not request.finding_id:
            raise HTTPException(status_code=422, detail="A finding is required for a precedent")
        finding = await db.scalar(
            select(ComplianceFinding)
            .where(
                ComplianceFinding.id == request.finding_id,
                ComplianceFinding.session_id == session_id,
            )
            .options(
                selectinload(ComplianceFinding.policy_version).selectinload(PolicyVersion.policy)
            )
        )
        if not finding or not finding.evidence_text:
            raise HTTPException(status_code=422, detail="Finding does not contain evidence")
        precedent = (finding, finding.evidence_text)

    review = await repository.add_human_review(
        db,
        session,
        reviewer_name=request.reviewer_name,
        decision=request.decision,
        notes=request.notes,
        precedent=precedent,
    )
    if request.promote_to_precedent:
        from app.models.entities import ReviewedPrecedent

        saved = await db.scalar(
            select(ReviewedPrecedent).where(ReviewedPrecedent.human_review_id == review.id)
        )
        if saved:
            try:
                ai = OpenAIGateway(get_settings())
                await ChromaIndex(get_settings(), ai).index_precedent(saved)
                saved.index_status = IndexStatus.INDEXED.value
            except Exception:
                saved.index_status = IndexStatus.FAILED.value
            await db.commit()
    return await session_response(db, await repository.get_session(db, session_id))
