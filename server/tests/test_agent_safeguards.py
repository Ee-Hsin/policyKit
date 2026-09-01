import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import AgentToolError, AgentToolExecutor, ComplianceAgent
from app.core.config import Settings
from app.models.entities import (
    AgentStep,
    ComplianceSessionStatus,
    FindingStatus,
    Policy,
    PolicySnapshot,
    PolicySnapshotItem,
    PolicyStatus,
    PolicyVersion,
)
from app.repositories import sessions as session_repository
from app.schemas.ai import AgentTurn, ComplianceCheckOutput, PolicyAssessment
from app.schemas.sessions import ComplianceSessionCreate
from app.services.compliance_checker import run_compliance_check
from tests.fakes import FakeAI, FakeIndex


async def policy_snapshot(db: AsyncSession, *, count: int = 2) -> PolicySnapshot:
    snapshot = PolicySnapshot(version=1, items=[])
    db.add(snapshot)
    for index in range(count):
        policy = Policy(key=f"POLICY_{index + 1:03}")
        version = PolicyVersion(
            version=1,
            title=f"Policy {index + 1}",
            category="content",
            status=PolicyStatus.PUBLISHED.value,
            rule_text=f"Policy rule {index + 1} has enough detail.",
            jurisdictions=["GLOBAL"],
            violation_examples=[f"Violation {index + 1}"],
            compliant_examples=[f"Compliant {index + 1}"],
        )
        policy.versions.append(version)
        db.add(policy)
        await db.flush()
        snapshot.items.append(PolicySnapshotItem(policy_version_id=version.id))
    await db.commit()
    return snapshot


async def compliance_session(db: AsyncSession, snapshot: PolicySnapshot):
    session = await session_repository.create_session(
        db,
        ComplianceSessionCreate(
            title="Software Engineer",
            job_description=(
                "Build and operate reliable Python services for our learning platform."
            ),
            target_locations=["New York"],
        ),
        snapshot,
    )
    session.status = ComplianceSessionStatus.INVESTIGATING.value
    await db.commit()
    return await session_repository.get_session(db, session.id)


def output_factory(statuses: dict[str, FindingStatus]):
    def build(posting: str, policies: list[dict]) -> ComplianceCheckOutput:
        assessments = []
        for policy in policies:
            status = statuses.get(policy["policy_id"], FindingStatus.NO_VIOLATION)
            if status == FindingStatus.VIOLATION:
                evidence = "Python"
                start = posting.index(evidence)
                end = start + len(evidence)
            else:
                evidence = None
                start = None
                end = None
            assessments.append(
                PolicyAssessment(
                    policy_id=policy["policy_id"],
                    status=status,
                    evidence_text=evidence,
                    evidence_start=start,
                    evidence_end=end,
                    reason="Deterministic fake assessment",
                    confidence=0.95,
                )
            )
        return ComplianceCheckOutput(
            input_type="job_posting",
            assessments=assessments,
            summary="Deterministic fake result",
        )

    return build


async def test_compliance_check_sends_every_applicable_policy_and_persists_findings(
    db: AsyncSession,
) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    ai = FakeAI(output_factory=output_factory({}))

    result = await run_compliance_check(db, session, ai)

    assert len(ai.compliance_calls) == 1
    assert {policy["policy_key"] for policy in ai.compliance_calls[0]["policies"]} == {
        "POLICY_001",
        "POLICY_002",
    }
    assert len(result.findings) == 2
    assert {finding.policy_version_id for finding in result.findings} == {
        policy.id for policy in result.policies
    }


async def test_identical_compliance_check_uses_the_exact_cache(db: AsyncSession) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    ai = FakeAI(output_factory=output_factory({}))

    await run_compliance_check(db, session, ai)
    await run_compliance_check(db, session, ai)

    assert len(ai.compliance_calls) == 1
    steps = list(
        await db.scalars(
            select(AgentStep).where(AgentStep.session_id == session.id).order_by(AgentStep.sequence)
        )
    )
    assert steps[-1].output_data["cache_hit"] is True
    assert steps[-1].input_tokens == 0
    assert steps[-1].output_tokens == 0


async def test_completion_rejects_missing_or_unresolved_policy_assessments(
    db: AsyncSession,
) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    executor = AgentToolExecutor(db, session, FakeAI(), FakeIndex())
    first_policy_id = snapshot.items[0].policy_version_id

    incomplete = await executor.execute("complete_session", {"summary": "Ready to publish"})
    assert incomplete == {
        "error": "The current draft has not completed full policy coverage",
        "retryable": True,
    }

    violating_ai = FakeAI(
        output_factory=output_factory({first_policy_id: FindingStatus.VIOLATION}),
        cache_namespace="fake-violating-checker",
    )
    await run_compliance_check(db, session, violating_ai)

    unresolved = await executor.execute("complete_session", {"summary": "Ready to publish"})
    assert unresolved == {
        "error": "The current draft still has unresolved findings",
        "retryable": True,
    }

    clean_ai = FakeAI(output_factory=output_factory({}), cache_namespace="fake-clean-checker")
    await run_compliance_check(db, session, clean_ai)
    result = await executor.execute("complete_session", {"summary": "Ready to publish"})

    assert result["status"] == ComplianceSessionStatus.READY_TO_PUBLISH.value


async def test_completion_rejects_an_unapproved_agent_revision(db: AsyncSession) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    session.current_posting_version.source = "agent"
    session.current_posting_version.approved_at = None
    await db.commit()
    executor = AgentToolExecutor(db, session, FakeAI(), FakeIndex())

    result = await executor.execute("complete_session", {"summary": "Ready to publish"})

    assert result == {
        "error": "The current agent revision has not been approved",
        "retryable": True,
    }


async def test_agent_rejects_a_turn_without_a_tool_call(db: AsyncSession) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    ai = FakeAI(agent_turns=[AgentTurn(tool_calls=[])])
    agent = ComplianceAgent(
        Settings(
            database_url="sqlite+aiosqlite://",
            chroma_mode="disabled",
            run_agent_worker=False,
        ),
        ai,
        FakeIndex(),
    )

    with pytest.raises(AgentToolError, match="did not select a tool"):
        await agent.run(db, session.id)

    steps = list(
        await db.scalars(
            select(AgentStep).where(AgentStep.session_id == session.id).order_by(AgentStep.sequence)
        )
    )
    assert steps[-1].kind == "agent_model"
    assert steps[-1].output_data["tools"] == []


async def test_agent_escalates_when_it_reaches_the_iteration_limit(
    db: AsyncSession,
) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    session.agent_iterations = 2
    await db.commit()
    ai = FakeAI()
    agent = ComplianceAgent(
        Settings(
            database_url="sqlite+aiosqlite://",
            chroma_mode="disabled",
            run_agent_worker=False,
            agent_max_steps=2,
        ),
        ai,
        FakeIndex(),
    )

    await agent.run(db, session.id)

    stored = await session_repository.get_session(db, session.id)
    assert stored.status == ComplianceSessionStatus.NEEDS_REVIEW.value
    assert stored.error_message == "The agent reached its investigation step limit."
    assert ai.agent_calls == []
