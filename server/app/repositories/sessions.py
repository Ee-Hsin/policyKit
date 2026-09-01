"""Compliance-session persistence."""

from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time import utc_now
from app.models.entities import (
    AgentStep,
    ChangeStatus,
    ComplianceFinding,
    ComplianceSession,
    ComplianceSessionStatus,
    HumanReview,
    JobPosting,
    PolicySnapshot,
    PolicyVersion,
    PostingVersion,
    ProposedChange,
    ReviewedPrecedent,
    StepStatus,
)
from app.schemas.ai import PolicyAssessment, ProposedRevision
from app.schemas.sessions import ComplianceSessionCreate
from app.services.jurisdictions import resolve_jurisdictions


class SessionNotFoundError(LookupError):
    pass


async def create_session(
    db: AsyncSession, data: ComplianceSessionCreate, snapshot: PolicySnapshot
) -> ComplianceSession:
    posting = JobPosting(
        title=data.title,
        organization_name=data.organization_name,
        target_locations=data.target_locations,
        employment_type=data.employment_type,
        platform=data.platform,
    )
    original = PostingVersion(version=1, content=data.job_description, source="user")
    posting.versions.append(original)
    db.add(posting)
    await db.flush()
    session = ComplianceSession(
        posting_id=posting.id,
        current_posting_version_id=original.id,
        policy_snapshot_id=snapshot.id,
        status=ComplianceSessionStatus.QUEUED.value,
        goal=(
            "Prepare this job posting for publication while preserving its meaning and "
            "satisfying every applicable platform policy."
        ),
    )
    db.add(session)
    await db.commit()
    return await get_session(db, session.id)


async def get_session(db: AsyncSession, session_id: str) -> ComplianceSession:
    session = await db.scalar(
        select(ComplianceSession)
        .where(ComplianceSession.id == session_id)
        .options(
            selectinload(ComplianceSession.posting).selectinload(JobPosting.versions),
            selectinload(ComplianceSession.current_posting_version),
            selectinload(ComplianceSession.policy_snapshot),
            selectinload(ComplianceSession.steps),
        )
    )
    if not session:
        raise SessionNotFoundError(session_id)
    return session


async def list_sessions(
    db: AsyncSession, *, statuses: Sequence[str] | None = None
) -> list[ComplianceSession]:
    statement = select(ComplianceSession).options(
        selectinload(ComplianceSession.posting).selectinload(JobPosting.versions),
        selectinload(ComplianceSession.current_posting_version),
        selectinload(ComplianceSession.policy_snapshot),
        selectinload(ComplianceSession.steps),
    )
    if statuses:
        statement = statement.where(ComplianceSession.status.in_(statuses))
    result = await db.scalars(statement.order_by(ComplianceSession.updated_at.desc()))
    return list(result)


async def claim_next_queued_session(db: AsyncSession) -> ComplianceSession | None:
    statement = (
        select(ComplianceSession)
        .where(ComplianceSession.status == ComplianceSessionStatus.QUEUED.value)
        .order_by(ComplianceSession.updated_at)
        .limit(1)
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    session = await db.scalar(statement)
    if not session:
        return None
    session.status = ComplianceSessionStatus.INVESTIGATING.value
    session.started_at = session.started_at or utc_now()
    session.error_message = None
    await db.commit()
    return await get_session(db, session.id)


async def recover_stale_sessions(db: AsyncSession, stale_after_seconds: int) -> int:
    stale_before = utc_now() - timedelta(seconds=stale_after_seconds)
    result = await db.execute(
        update(ComplianceSession)
        .where(
            ComplianceSession.status == ComplianceSessionStatus.INVESTIGATING.value,
            ComplianceSession.updated_at < stale_before,
        )
        .values(
            status=ComplianceSessionStatus.QUEUED.value,
            error_message="Recovered after an interrupted agent run.",
            updated_at=utc_now(),
        )
    )
    await db.commit()
    return result.rowcount or 0


async def add_step(
    db: AsyncSession,
    session_id: str,
    *,
    kind: str,
    name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    status: str = StepStatus.COMPLETED.value,
    duration_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> AgentStep:
    sequence = (
        await db.scalar(
            select(func.max(AgentStep.sequence)).where(AgentStep.session_id == session_id)
        )
        or 0
    ) + 1
    step = AgentStep(
        session_id=session_id,
        sequence=sequence,
        kind=kind,
        name=name,
        input_data=input_data or {},
        output_data=output_data or {},
        status=status,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(step)
    await db.flush()
    return step


async def findings_for_session(
    db: AsyncSession, session_id: str, *, posting_version_id: str | None = None
) -> list[ComplianceFinding]:
    statement = (
        select(ComplianceFinding)
        .where(ComplianceFinding.session_id == session_id)
        .options(selectinload(ComplianceFinding.policy_version).selectinload(PolicyVersion.policy))
        .order_by(ComplianceFinding.created_at)
    )
    if posting_version_id:
        statement = statement.where(ComplianceFinding.posting_version_id == posting_version_id)
    return list(await db.scalars(statement))


async def replace_findings(
    db: AsyncSession,
    session: ComplianceSession,
    assessments: list[PolicyAssessment],
) -> list[ComplianceFinding]:
    await db.execute(
        delete(ComplianceFinding).where(
            ComplianceFinding.session_id == session.id,
            ComplianceFinding.posting_version_id == session.current_posting_version_id,
        )
    )
    findings = [
        ComplianceFinding(
            session_id=session.id,
            posting_version_id=session.current_posting_version_id,
            policy_version_id=assessment.policy_id,
            status=assessment.status.value,
            evidence_text=assessment.evidence_text,
            evidence_start=assessment.evidence_start,
            evidence_end=assessment.evidence_end,
            reason=assessment.reason,
            confidence=assessment.confidence,
            resolved=assessment.status.value == "no_violation",
        )
        for assessment in assessments
    ]
    db.add_all(findings)
    await db.flush()
    return findings


async def proposed_changes_for_session(db: AsyncSession, session_id: str) -> list[ProposedChange]:
    return list(
        await db.scalars(
            select(ProposedChange)
            .where(ProposedChange.session_id == session_id)
            .order_by(ProposedChange.created_at)
        )
    )


async def create_proposed_revision(
    db: AsyncSession, session: ComplianceSession, revision: ProposedRevision
) -> PostingVersion:
    latest_version_number = (
        await db.scalar(
            select(func.max(PostingVersion.version)).where(
                PostingVersion.posting_id == session.posting_id
            )
        )
        or 0
    )
    proposed = PostingVersion(
        posting_id=session.posting_id,
        version=latest_version_number + 1,
        content=revision.revised_text,
        source="agent",
    )
    db.add(proposed)
    await db.flush()
    for change in revision.changes:
        db.add(
            ProposedChange(
                session_id=session.id,
                from_posting_version_id=session.current_posting_version_id,
                to_posting_version_id=proposed.id,
                original_text=change.original_text,
                replacement_text=change.replacement_text,
                reason=change.reason,
                policy_keys=change.policy_keys,
            )
        )
    session.current_posting_version_id = proposed.id
    session.status = ComplianceSessionStatus.WAITING_FOR_APPROVAL.value
    await db.commit()
    return proposed


async def record_revision_decision(
    db: AsyncSession,
    session: ComplianceSession,
    *,
    approved: bool,
    reviewer_name: str,
    notes: str | None,
) -> None:
    proposed_changes = await proposed_changes_for_session(db, session.id)
    pending = [
        change for change in proposed_changes if change.status == ChangeStatus.PROPOSED.value
    ]
    if not pending:
        raise ValueError("This session has no proposed changes awaiting approval")
    status = ChangeStatus.ACCEPTED.value if approved else ChangeStatus.REJECTED.value
    for change in pending:
        change.status = status
    review = HumanReview(
        session_id=session.id,
        reviewer_name=reviewer_name,
        decision="approve" if approved else "reject",
        notes=notes,
    )
    db.add(review)
    if approved:
        session.current_posting_version.approved_at = utc_now()
        session.status = ComplianceSessionStatus.QUEUED.value
    else:
        previous_id = pending[0].from_posting_version_id
        session.current_posting_version_id = previous_id
        session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
        session.current_question = "What should the agent change about the proposed revision?"
    await db.commit()


async def record_user_message(db: AsyncSession, session: ComplianceSession, message: str) -> None:
    await add_step(
        db,
        session.id,
        kind="user_message",
        name="Recruiter answered",
        input_data={"message": message},
    )
    session.current_question = None
    session.status = ComplianceSessionStatus.QUEUED.value
    await db.commit()


async def add_human_review(
    db: AsyncSession,
    session: ComplianceSession,
    *,
    reviewer_name: str,
    decision: str,
    notes: str | None,
    precedent: tuple[ComplianceFinding, str] | None = None,
) -> HumanReview:
    review = HumanReview(
        session_id=session.id,
        reviewer_name=reviewer_name,
        decision=decision,
        notes=notes,
    )
    db.add(review)
    await db.flush()
    if precedent:
        finding, excerpt = precedent
        jurisdictions, _ = resolve_jurisdictions(session.posting.target_locations)
        db.add(
            ReviewedPrecedent(
                human_review_id=review.id,
                excerpt=excerpt,
                decision=decision,
                jurisdiction=(jurisdictions or ["GLOBAL"])[0],
                category=finding.policy_version.category,
                policy_version_id=finding.policy_version_id,
            )
        )
    if decision == "approve":
        session.status = ComplianceSessionStatus.READY_TO_PUBLISH.value
        session.completed_at = utc_now()
    elif decision == "request_changes":
        session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
        session.current_question = notes or "What should change before this posting is approved?"
    else:
        session.status = ComplianceSessionStatus.FAILED.value
        session.error_message = notes or "A reviewer rejected this posting."
    await db.commit()
    return review


async def publish_posting(
    db: AsyncSession, session: ComplianceSession, publisher_name: str
) -> None:
    if session.status != ComplianceSessionStatus.READY_TO_PUBLISH.value:
        raise ValueError("Only a ready posting can be published")
    await add_step(
        db,
        session.id,
        kind="publication",
        name="Posting published",
        output_data={"publisher_name": publisher_name},
    )
    session.status = ComplianceSessionStatus.PUBLISHED.value
    session.completed_at = utc_now()
    await db.commit()
