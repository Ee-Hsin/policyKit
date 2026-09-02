import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import AgentToolError, AgentToolExecutor, ComplianceAgent
from app.core.config import Settings
from app.integrations.chroma import SemanticMatch
from app.models.entities import (
    AgentStep,
    ComplianceCacheEntry,
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


async def test_invalid_exact_cache_entry_is_recomputed(db: AsyncSession) -> None:
    snapshot = await policy_snapshot(db)
    session = await compliance_session(db, snapshot)
    ai = FakeAI(output_factory=output_factory({}))
    await run_compliance_check(db, session, ai)
    cached = await db.scalar(select(ComplianceCacheEntry))
    assert cached is not None
    cached.result = {"invalid": "cached payload"}
    await db.commit()

    await run_compliance_check(db, session, ai)

    assert len(ai.compliance_calls) == 2


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


async def test_completion_rejects_findings_from_a_previous_location_scope(
    db: AsyncSession,
) -> None:
    snapshot = PolicySnapshot(version=1, items=[])
    db.add(snapshot)
    for key, jurisdiction in (("NY_POLICY", "US-NY"), ("CA_POLICY", "US-CA")):
        policy = Policy(key=key)
        version = PolicyVersion(
            version=1,
            title=key,
            category="content",
            status=PolicyStatus.PUBLISHED.value,
            rule_text=f"Rule for {jurisdiction} with enough detail.",
            jurisdictions=[jurisdiction],
            violation_examples=["Violation"],
            compliant_examples=["Compliant"],
        )
        policy.versions.append(version)
        db.add(policy)
        await db.flush()
        snapshot.items.append(PolicySnapshotItem(policy_version_id=version.id))
    await db.commit()
    session = await compliance_session(db, snapshot)
    ai = FakeAI(output_factory=output_factory({}))
    await run_compliance_check(db, session, ai)
    executor = AgentToolExecutor(db, session, ai, FakeIndex())

    await executor.execute("set_hiring_locations", {"locations": ["California"]})
    result = await executor.execute("complete_session", {"summary": "Ready to publish"})

    assert result == {
        "error": "The current draft has not completed full policy coverage",
        "retryable": True,
    }


async def test_revision_rejects_undeclared_changes(db: AsyncSession) -> None:
    snapshot = await policy_snapshot(db, count=1)
    session = await compliance_session(db, snapshot)
    policy_id = snapshot.items[0].policy_version_id
    ai = FakeAI(
        output_factory=output_factory({policy_id: FindingStatus.VIOLATION}),
        cache_namespace="fake-revision-checker",
    )
    await run_compliance_check(db, session, ai)
    executor = AgentToolExecutor(db, session, ai, FakeIndex())

    result = await executor.execute(
        "propose_revision",
        {
            "revised_text": (
                "Build and operate reliable Go services for our learning platform. Extra change."
            ),
            "changes": [
                {
                    "original_text": "Python",
                    "replacement_text": "Go",
                    "reason": "Resolve the supported policy finding.",
                    "policy_keys": ["POLICY_001"],
                }
            ],
        },
    )

    assert result == {
        "error": "The revised posting contains changes that were not declared",
        "retryable": True,
    }


async def test_revision_accepts_a_declared_sentence_deletion_without_double_spacing(
    db: AsyncSession,
) -> None:
    snapshot = await policy_snapshot(db, count=1)
    session = await compliance_session(db, snapshot)
    session.current_posting_version.content = (
        "Build reliable Python services. Recent graduates preferred. Mentor teammates."
    )
    await db.commit()
    policy_id = snapshot.items[0].policy_version_id
    ai = FakeAI(
        output_factory=output_factory({policy_id: FindingStatus.VIOLATION}),
        cache_namespace="fake-deletion-checker",
    )
    await run_compliance_check(db, session, ai)
    executor = AgentToolExecutor(db, session, ai, FakeIndex())

    result = await executor.execute(
        "propose_revision",
        {
            "revised_text": "Build reliable Python services. Mentor teammates.",
            "changes": [
                {
                    "original_text": "Recent graduates preferred.",
                    "replacement_text": "",
                    "reason": "Remove the supported age preference finding.",
                    "policy_keys": ["POLICY_001"],
                }
            ],
        },
    )

    assert result["status"] == ComplianceSessionStatus.WAITING_FOR_APPROVAL.value


async def test_human_approval_records_and_resolves_reviewed_findings(
    db: AsyncSession,
) -> None:
    snapshot = await policy_snapshot(db, count=1)
    session = await compliance_session(db, snapshot)
    policy_id = snapshot.items[0].policy_version_id
    ai = FakeAI(
        output_factory=output_factory({policy_id: FindingStatus.VIOLATION}),
        cache_namespace="fake-human-review-checker",
    )
    await run_compliance_check(db, session, ai)
    session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
    await db.commit()

    review = await session_repository.add_human_review(
        db,
        session,
        reviewer_name="Policy reviewer",
        decision="approve",
        notes="Approved as an explicit policy exception.",
    )

    stored = await session_repository.get_session(db, session.id)
    findings = await session_repository.findings_for_session(
        db,
        session.id,
        posting_version_id=session.current_posting_version_id,
    )
    assert stored.status == ComplianceSessionStatus.READY_TO_PUBLISH.value
    assert review.finding_ids == [findings[0].id]
    assert findings[0].resolved is True


async def test_policy_search_uses_pinned_canonical_policy_text(
    db: AsyncSession,
) -> None:
    snapshot = await policy_snapshot(db, count=1)
    session = await compliance_session(db, snapshot)
    pinned_version = snapshot.items[0].policy_version
    index = FakeIndex(
        matches=[
            SemanticMatch(
                record_id="newer-result",
                text="A newer policy outside the snapshot.",
                distance=0.01,
                metadata={"policy_version_id": "not-in-the-snapshot"},
            ),
            SemanticMatch(
                record_id=pinned_version.id,
                text="Stale vector-store text that must not be trusted.",
                distance=0.02,
                metadata={"policy_version_id": pinned_version.id},
            ),
        ]
    )
    executor = AgentToolExecutor(db, session, FakeAI(), index)

    result = await executor.execute(
        "search_policies",
        {"query": "policy rule", "category": "Content", "jurisdiction": None},
    )

    assert result["matches"] == [
        {
            "policy_key": "POLICY_001",
            "title": "Policy 1",
            "category": "content",
            "passage": pinned_version.rule_text,
            "distance": 0.02,
        }
    ]
    assert index.search_calls == [
        {
            "collection_name": "policy_chunks",
            "query": "policy rule",
            "limit": 15,
            "where": {"category": "content"},
        }
    ]


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
    supplied_tool_names = {tool["name"] for tool in ai.agent_calls[0]["tools"]}
    assert supplied_tool_names == {"run_compliance_check"}


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
