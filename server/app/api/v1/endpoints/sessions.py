"""Recruiter-facing compliance-session endpoints."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionFactory, get_db
from app.models.entities import ComplianceSession, ComplianceSessionStatus
from app.repositories import policies as policy_repository
from app.repositories import sessions as repository
from app.schemas.sessions import (
    AgentStepRead,
    ComplianceSessionCreate,
    ComplianceSessionRead,
    FindingRead,
    PostingVersionRead,
    ProposedChangeRead,
    PublishPostingRequest,
    RevisionApproval,
    SessionListItem,
    SessionMessageCreate,
)

router = APIRouter()


async def session_response(db: AsyncSession, session: ComplianceSession) -> ComplianceSessionRead:
    findings = await repository.findings_for_session(
        db, session.id, posting_version_id=session.current_posting_version_id
    )
    changes = await repository.proposed_changes_for_session(db, session.id)
    return ComplianceSessionRead(
        id=session.id,
        status=session.status,
        goal=session.goal,
        title=session.posting.title,
        organization_name=session.posting.organization_name,
        target_locations=session.posting.target_locations,
        employment_type=session.posting.employment_type,
        platform=session.posting.platform,
        current_question=session.current_question,
        error_message=session.error_message,
        policy_snapshot_version=(
            session.policy_snapshot.version if session.policy_snapshot else None
        ),
        current_posting_version=PostingVersionRead.model_validate(session.current_posting_version),
        posting_versions=[
            PostingVersionRead.model_validate(version) for version in session.posting.versions
        ],
        findings=[
            FindingRead(
                id=finding.id,
                policy_key=finding.policy_version.policy.key,
                policy_title=finding.policy_version.title,
                category=finding.policy_version.category,
                status=finding.status,
                evidence_text=finding.evidence_text,
                evidence_start=finding.evidence_start,
                evidence_end=finding.evidence_end,
                reason=finding.reason,
                confidence=finding.confidence,
                resolved=finding.resolved,
            )
            for finding in findings
        ],
        proposed_changes=[ProposedChangeRead.model_validate(change) for change in changes],
        steps=[AgentStepRead.model_validate(step) for step in session.steps],
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


def session_error(error: Exception) -> HTTPException:
    if isinstance(error, repository.SessionNotFoundError):
        return HTTPException(status_code=404, detail="Compliance session not found")
    return HTTPException(status_code=409, detail=str(error))


@router.post("", response_model=ComplianceSessionRead, status_code=status.HTTP_202_ACCEPTED)
async def create_session(
    request: ComplianceSessionCreate, db: AsyncSession = Depends(get_db)
) -> ComplianceSessionRead:
    snapshot = await policy_repository.get_latest_snapshot(db)
    if not snapshot:
        raise HTTPException(
            status_code=409,
            detail="Publish at least one policy before starting a compliance session",
        )
    session = await repository.create_session(db, request, snapshot)
    return await session_response(db, session)


@router.get("", response_model=list[SessionListItem])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionListItem]:
    sessions = await repository.list_sessions(db)
    response = []
    for session in sessions:
        findings = await repository.findings_for_session(
            db, session.id, posting_version_id=session.current_posting_version_id
        )
        response.append(
            SessionListItem(
                id=session.id,
                title=session.posting.title,
                status=session.status,
                target_locations=session.posting.target_locations,
                finding_count=sum(finding.status != "no_violation" for finding in findings),
                updated_at=session.updated_at,
            )
        )
    return response


@router.get("/{session_id}", response_model=ComplianceSessionRead)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> ComplianceSessionRead:
    try:
        return await session_response(db, await repository.get_session(db, session_id))
    except repository.SessionNotFoundError as error:
        raise session_error(error) from error


@router.post("/{session_id}/messages", response_model=ComplianceSessionRead)
async def answer_agent(
    session_id: str,
    request: SessionMessageCreate,
    db: AsyncSession = Depends(get_db),
) -> ComplianceSessionRead:
    try:
        session = await repository.get_session(db, session_id)
        if session.status != ComplianceSessionStatus.WAITING_FOR_INFORMATION.value:
            raise ValueError("The agent is not waiting for recruiter information")
        await repository.record_user_message(db, session, request.message)
        return await session_response(db, await repository.get_session(db, session_id))
    except (repository.SessionNotFoundError, ValueError) as error:
        raise session_error(error) from error


@router.post("/{session_id}/approve", response_model=ComplianceSessionRead)
async def approve_revision(
    session_id: str,
    request: RevisionApproval,
    db: AsyncSession = Depends(get_db),
) -> ComplianceSessionRead:
    try:
        session = await repository.get_session(db, session_id)
        if session.status != ComplianceSessionStatus.WAITING_FOR_APPROVAL.value:
            raise ValueError("The session is not waiting for revision approval")
        await repository.record_revision_decision(
            db,
            session,
            approved=request.approved,
            reviewer_name=request.reviewer_name,
            notes=request.notes,
        )
        return await session_response(db, await repository.get_session(db, session_id))
    except (repository.SessionNotFoundError, ValueError) as error:
        raise session_error(error) from error


@router.post("/{session_id}/publish", response_model=ComplianceSessionRead)
async def publish_posting(
    session_id: str,
    request: PublishPostingRequest,
    db: AsyncSession = Depends(get_db),
) -> ComplianceSessionRead:
    try:
        session = await repository.get_session(db, session_id)
        await repository.publish_posting(db, session, request.publisher_name)
        return await session_response(db, await repository.get_session(db, session_id))
    except (repository.SessionNotFoundError, ValueError) as error:
        raise session_error(error) from error


@router.get("/{session_id}/events")
async def stream_session_events(session_id: str, request: Request) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        last_signature = ""
        while not await request.is_disconnected():
            async with SessionFactory() as db:
                try:
                    session = await repository.get_session(db, session_id)
                    payload = await session_response(db, session)
                except repository.SessionNotFoundError:
                    yield 'event: error\ndata: {"detail": "Session not found"}\n\n'
                    return
            serialized = payload.model_dump_json()
            signature = f"{payload.status}:{len(payload.steps)}:{payload.updated_at}"
            if signature != last_signature:
                yield f"event: session\ndata: {serialized}\n\n"
                last_signature = signature
            else:
                yield ": keepalive\n\n"
            if payload.status in {
                ComplianceSessionStatus.PUBLISHED.value,
                ComplianceSessionStatus.FAILED.value,
            }:
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
