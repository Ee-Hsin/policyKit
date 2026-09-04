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


EDITABLE_SESSION_STATUSES = {
    ComplianceSessionStatus.DRAFT.value,
    ComplianceSessionStatus.WAITING_FOR_INFORMATION.value,
    ComplianceSessionStatus.CHANGES_PROPOSED.value,
    ComplianceSessionStatus.WAITING_FOR_APPROVAL.value,
    ComplianceSessionStatus.READY_TO_PUBLISH.value,
    ComplianceSessionStatus.NEEDS_REVIEW.value,
    ComplianceSessionStatus.FAILED.value,
}


async def create_session(db: AsyncSession, data: ComplianceSessionCreate) -> ComplianceSession:
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
        status=ComplianceSessionStatus.DRAFT.value,
        goal=(
            "Prepare this job posting for publication while preserving its meaning and "
            "satisfying every applicable platform policy."
        ),
    )
    db.add(session)
    await db.commit()
    return await get_session(db, session.id)


async def _lock_session(db: AsyncSession, session_id: str) -> ComplianceSession:
    statement = (
        select(ComplianceSession)
        .where(ComplianceSession.id == session_id)
        .options(
            selectinload(ComplianceSession.posting).selectinload(JobPosting.versions),
            selectinload(ComplianceSession.current_posting_version),
            selectinload(ComplianceSession.policy_snapshot),
            selectinload(ComplianceSession.steps),
        )
        .execution_options(populate_existing=True)
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update()
    session = await db.scalar(statement)
    if not session:
        raise SessionNotFoundError(session_id)
    return session


def _validate_current_base(session: ComplianceSession, base_version_id: str) -> None:
    if session.current_posting_version_id != base_version_id:
        raise ValueError("The posting changed after this draft was loaded")


def last_checked_posting_version_id(
    session: ComplianceSession, steps: Sequence[AgentStep]
) -> str | None:
    versions_by_number = {version.version: version.id for version in session.posting.versions}
    for step in reversed(steps):
        if step.kind != "compliance_check":
            continue
        version_id = step.input_data.get("posting_version_id")
        if isinstance(version_id, str):
            return version_id
        version_number = step.input_data.get("posting_version")
        if isinstance(version_number, int):
            return versions_by_number.get(version_number)
    return None


async def validate_writing_base(db: AsyncSession, session_id: str, base_version_id: str) -> None:
    row = (
        await db.execute(
            select(
                ComplianceSession.status,
                ComplianceSession.current_posting_version_id,
            ).where(ComplianceSession.id == session_id)
        )
    ).one_or_none()
    if not row:
        raise SessionNotFoundError(session_id)
    if row.status not in EDITABLE_SESSION_STATUSES:
        raise ValueError("Writing assistance is not available in the current state")
    if row.current_posting_version_id != base_version_id:
        raise ValueError("The posting changed after this draft was loaded")


async def create_user_posting_version(
    db: AsyncSession,
    session_id: str,
    *,
    base_version_id: str,
    content: str,
) -> ComplianceSession:
    session = await _lock_session(db, session_id)
    if session.status not in EDITABLE_SESSION_STATUSES:
        raise ValueError("The posting cannot be edited in its current state")
    _validate_current_base(session, base_version_id)
    current = await db.scalar(
        select(PostingVersion)
        .where(PostingVersion.id == session.current_posting_version_id)
        .execution_options(populate_existing=True)
    )
    if not current:
        raise ValueError("The current posting version does not exist")
    if current.content == content:
        raise ValueError("The saved draft is unchanged")
    latest_version_number = (
        await db.scalar(
            select(func.max(PostingVersion.version)).where(
                PostingVersion.posting_id == session.posting_id
            )
        )
        or 0
    )
    saved = PostingVersion(
        posting_id=session.posting_id,
        version=latest_version_number + 1,
        content=content,
        source="recruiter",
    )
    db.add(saved)
    session.posting.versions.append(saved)
    await db.flush()
    await db.execute(
        update(ProposedChange)
        .where(
            ProposedChange.session_id == session.id,
            ProposedChange.status == ChangeStatus.PROPOSED.value,
        )
        .values(status=ChangeStatus.REJECTED.value)
    )
    session.current_posting_version_id = saved.id
    session.current_posting_version = saved
    session.status = ComplianceSessionStatus.DRAFT.value
    session.current_question = None
    session.error_message = None
    session.completed_at = None
    await add_step(
        db,
        session.id,
        kind="user_edit",
        name="Recruiter saved a new posting version",
        input_data={"from_posting_version": current.version},
        output_data={"posting_version": saved.version},
    )
    await db.commit()
    return await get_session(db, session.id)


async def start_compliance_check(
    db: AsyncSession, session_id: str, *, base_version_id: str
) -> ComplianceSession:
    from app.repositories import policies as policy_repository

    session = await _lock_session(db, session_id)
    if session.status not in {
        ComplianceSessionStatus.DRAFT.value,
        ComplianceSessionStatus.FAILED.value,
    }:
        raise ValueError("Only a saved draft or failed check can start a compliance check")
    _validate_current_base(session, base_version_id)
    if session.policy_snapshot_id:
        snapshot = await policy_repository.get_snapshot(db, session.policy_snapshot_id)
    else:
        snapshot = await policy_repository.get_latest_snapshot(db)
        if not snapshot:
            raise ValueError("Publish at least one policy before starting a compliance check")
        session.policy_snapshot_id = snapshot.id
        session.policy_snapshot = snapshot
    session.status = ComplianceSessionStatus.QUEUED.value
    session.started_at = session.started_at or utc_now()
    session.completed_at = None
    session.current_question = None
    session.error_message = None
    session.agent_iterations = 0
    await add_step(
        db,
        session.id,
        kind="user_action",
        name="Recruiter requested a compliance check",
        input_data={"posting_version_id": session.current_posting_version_id},
        output_data={"policy_snapshot_version": snapshot.version},
    )
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


async def steps_for_session(db: AsyncSession, session_id: str) -> list[AgentStep]:
    return list(
        await db.scalars(
            select(AgentStep).where(AgentStep.session_id == session_id).order_by(AgentStep.sequence)
        )
    )


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
    session_id: str,
    *,
    base_version_id: str,
    approved: bool,
    reviewer_name: str,
    notes: str | None,
) -> None:
    session = await _lock_session(db, session_id)
    if session.status != ComplianceSessionStatus.WAITING_FOR_APPROVAL.value:
        raise ValueError("The session is not waiting for revision approval")
    _validate_current_base(session, base_version_id)
    proposed_changes = await proposed_changes_for_session(db, session.id)
    pending = [
        change
        for change in proposed_changes
        if change.status == ChangeStatus.PROPOSED.value
        and change.to_posting_version_id == session.current_posting_version_id
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
        session.current_posting_version = next(
            version for version in session.posting.versions if version.id == previous_id
        )
        if notes and notes.strip():
            await add_step(
                db,
                session.id,
                kind="user_message",
                name="Recruiter requested a different revision",
                input_data={"message": notes.strip()},
            )
            session.status = ComplianceSessionStatus.QUEUED.value
            session.current_question = None
        else:
            session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
            session.current_question = "What should the agent change about the proposed revision?"
    await db.commit()


async def record_user_message(
    db: AsyncSession,
    session_id: str,
    *,
    base_version_id: str,
    message: str,
) -> None:
    session = await _lock_session(db, session_id)
    if session.status != ComplianceSessionStatus.WAITING_FOR_INFORMATION.value:
        raise ValueError("The agent is not waiting for recruiter information")
    _validate_current_base(session, base_version_id)
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
    status_statement = select(ComplianceSession.status).where(ComplianceSession.id == session.id)
    if db.bind and db.bind.dialect.name == "postgresql":
        status_statement = status_statement.with_for_update()
    current_status = await db.scalar(status_statement)
    if current_status != ComplianceSessionStatus.NEEDS_REVIEW.value:
        raise ValueError("Session does not require human review")
    findings = await findings_for_session(
        db,
        session.id,
        posting_version_id=session.current_posting_version_id,
    )
    reviewed_finding_ids = [finding.id for finding in findings if finding.status != "no_violation"]
    review = HumanReview(
        session_id=session.id,
        reviewer_name=reviewer_name,
        decision=decision,
        notes=notes,
        finding_ids=reviewed_finding_ids,
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
        for finding in findings:
            if finding.id in reviewed_finding_ids:
                finding.resolved = True
        await db.flush()
        await validate_publishable(db, session)
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


async def validate_publishable(db: AsyncSession, session: ComplianceSession) -> None:
    from app.repositories import policies as policy_repository

    if session.current_posting_version.source == "agent":
        if session.current_posting_version.approved_at is None:
            raise ValueError("The current agent revision has not been approved")
    if not session.policy_snapshot_id:
        raise ValueError("The session has no policy snapshot")
    jurisdictions, unresolved_locations = resolve_jurisdictions(session.posting.target_locations)
    if not jurisdictions or unresolved_locations:
        raise ValueError("Hiring location scope is incomplete")
    policies = await policy_repository.applicable_policy_versions(
        db,
        session.policy_snapshot_id,
        jurisdictions=jurisdictions,
        employment_type=session.posting.employment_type,
        platform=session.posting.platform,
        at=session.started_at or session.created_at,
    )
    if not policies:
        raise ValueError("No applicable policies were found")
    findings = await findings_for_session(
        db,
        session.id,
        posting_version_id=session.current_posting_version_id,
    )
    checked_policy_ids = [finding.policy_version_id for finding in findings]
    applicable_policy_ids = {policy.id for policy in policies}
    if (
        len(checked_policy_ids) != len(applicable_policy_ids)
        or set(checked_policy_ids) != applicable_policy_ids
    ):
        raise ValueError("The current draft has not completed full policy coverage")
    unresolved_findings = [
        finding for finding in findings if finding.status != "no_violation" and not finding.resolved
    ]
    if unresolved_findings:
        raise ValueError("The current draft still has unresolved findings")


async def publish_posting(
    db: AsyncSession,
    session_id: str,
    *,
    base_version_id: str,
    publisher_name: str,
) -> None:
    session = await _lock_session(db, session_id)
    if session.status != ComplianceSessionStatus.READY_TO_PUBLISH.value:
        raise ValueError("Only a ready posting can be published")
    _validate_current_base(session, base_version_id)
    await validate_publishable(db, session)
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
