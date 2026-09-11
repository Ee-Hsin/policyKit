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
    JobPosting,
    PolicySnapshot,
    PolicyVersion,
    PostingVersion,
    ProposedChange,
    RevisionDecision,
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
    decisions: dict[str, bool],
    recruiter_name: str,
    notes: str | None,
) -> None:
    proposed_changes = await proposed_changes_for_session(db, session.id)
    pending = [
        change for change in proposed_changes if change.status == ChangeStatus.PROPOSED.value
    ]
    if not pending:
        raise ValueError("This session has no proposed changes awaiting approval")
    pending_by_id = {change.id: change for change in pending}
    if set(decisions) != set(pending_by_id):
        raise ValueError("Choose accept or reject for every proposed change")

    accepted = [change for change in pending if decisions[change.id]]
    rejected = [change for change in pending if not decisions[change.id]]
    for change in pending:
        change.status = (
            ChangeStatus.ACCEPTED.value if decisions[change.id] else ChangeStatus.REJECTED.value
        )

    previous_ids = {change.from_posting_version_id for change in pending}
    if len(previous_ids) != 1:
        raise ValueError("Proposed changes do not share the same source posting")
    previous_id = previous_ids.pop()
    previous = await db.get(PostingVersion, previous_id)
    if not previous:
        raise ValueError("The source posting for these changes is unavailable")

    revision_decision = RevisionDecision(
        session_id=session.id,
        recruiter_name=recruiter_name,
        decision="approve" if not rejected else "reject" if not accepted else "partial",
        notes=notes,
    )
    db.add(revision_decision)

    if not rejected:
        session.current_posting_version.approved_at = utc_now()
    elif accepted:
        replacements = []
        for change in accepted:
            if previous.content.count(change.original_text) != 1:
                raise ValueError("A proposed change no longer matches the source posting")
            start = previous.content.index(change.original_text)
            end = start + len(change.original_text)
            if (
                not change.replacement_text
                and start > 0
                and end < len(previous.content)
                and previous.content[start - 1] == " "
                and previous.content[end] == " "
            ):
                end += 1
            replacements.append((start, end, change.replacement_text))
        replacements.sort()
        revised_parts = []
        cursor = 0
        for start, end, replacement in replacements:
            revised_parts.extend((previous.content[cursor:start], replacement))
            cursor = end
        revised_parts.append(previous.content[cursor:])
        latest_version_number = (
            await db.scalar(
                select(func.max(PostingVersion.version)).where(
                    PostingVersion.posting_id == session.posting_id
                )
            )
            or 0
        )
        selected_revision = PostingVersion(
            posting_id=session.posting_id,
            version=latest_version_number + 1,
            content="".join(revised_parts),
            source="agent",
            approved_at=utc_now(),
        )
        db.add(selected_revision)
        await db.flush()
        for change in accepted:
            change.to_posting_version_id = selected_revision.id
        session.current_posting_version_id = selected_revision.id
        session.current_posting_version = selected_revision
    else:
        session.current_posting_version_id = previous_id
        session.current_posting_version = previous

    if rejected:
        await add_step(
            db,
            session.id,
            kind="user_message",
            name="Recruiter reviewed proposed changes",
            input_data={
                "rejected_changes": [
                    {
                        "original_text": change.original_text,
                        "replacement_text": change.replacement_text,
                    }
                    for change in rejected
                ],
                "notes": notes,
            },
        )
    session.current_question = None
    session.status = ComplianceSessionStatus.QUEUED.value
    await db.commit()


async def record_recruiter_posting_edit(
    db: AsyncSession,
    session: ComplianceSession,
    *,
    content: str,
    recruiter_name: str,
) -> None:
    if session.status != ComplianceSessionStatus.REVIEW_COMPLETE.value:
        raise ValueError("The posting can only be edited after a completed review with findings")
    if content == session.current_posting_version.content:
        raise ValueError("Change the posting before starting another review")

    previous_version = session.current_posting_version.version
    latest_version_number = (
        await db.scalar(
            select(func.max(PostingVersion.version)).where(
                PostingVersion.posting_id == session.posting_id
            )
        )
        or 0
    )
    edited = PostingVersion(
        version=latest_version_number + 1,
        content=content,
        source="user",
    )
    session.posting.versions.append(edited)
    await db.flush()
    session.current_posting_version_id = edited.id
    session.current_posting_version = edited
    session.current_question = None
    session.error_message = None
    session.completed_at = None
    session.status = ComplianceSessionStatus.QUEUED.value
    await add_step(
        db,
        session.id,
        kind="user_message",
        name="Recruiter edited posting",
        input_data={
            "recruiter_name": recruiter_name,
            "from_posting_version": previous_version,
            "to_posting_version": edited.version,
        },
    )
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
        at=session.created_at,
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
    unresolved_findings = [finding for finding in findings if finding.status != "no_violation"]
    if unresolved_findings:
        raise ValueError("The current draft still has unresolved findings")


async def publish_posting(
    db: AsyncSession,
    session: ComplianceSession,
    publisher_name: str,
    *,
    override_reason: str | None = None,
) -> None:
    override_reason = override_reason.strip() if override_reason else None
    if session.status == ComplianceSessionStatus.PUBLISHED.value:
        raise ValueError("This posting has already been published")

    overrode_review = session.status != ComplianceSessionStatus.READY_TO_PUBLISH.value
    if overrode_review:
        overridable_statuses = {
            ComplianceSessionStatus.WAITING_FOR_INFORMATION.value,
            ComplianceSessionStatus.WAITING_FOR_APPROVAL.value,
            ComplianceSessionStatus.REVIEW_COMPLETE.value,
            ComplianceSessionStatus.FAILED.value,
        }
        if session.status not in overridable_statuses:
            raise ValueError("Wait for the current review step to finish before publishing")
        if not override_reason:
            raise ValueError("Explain why you are overriding the PolicyKit review")

        if (
            session.current_posting_version.source == "agent"
            and session.current_posting_version.approved_at is None
        ):
            changes = await proposed_changes_for_session(db, session.id)
            source_ids = {
                change.from_posting_version_id
                for change in changes
                if change.status == ChangeStatus.PROPOSED.value
                and change.to_posting_version_id == session.current_posting_version_id
            }
            if len(source_ids) != 1:
                raise ValueError("The recruiter draft for this proposed revision is unavailable")
            source = await db.get(PostingVersion, source_ids.pop())
            if not source:
                raise ValueError("The recruiter draft for this proposed revision is unavailable")
            session.current_posting_version_id = source.id
            session.current_posting_version = source
    else:
        await validate_publishable(db, session)

    publication_data = {
        "publisher_name": publisher_name,
        "overrode_review": overrode_review,
    }
    if overrode_review:
        publication_data["override_reason"] = override_reason
    await add_step(
        db,
        session.id,
        kind="publication",
        name="Posting published",
        output_data=publication_data,
    )
    session.status = ComplianceSessionStatus.PUBLISHED.value
    session.completed_at = utc_now()
    await db.commit()
