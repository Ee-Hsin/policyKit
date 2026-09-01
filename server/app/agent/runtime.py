"""Durable tool-calling agent runtime."""

from __future__ import annotations

from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.prompts import AGENT_INSTRUCTIONS
from app.agent.tools import AGENT_TOOLS
from app.core.config import Settings
from app.core.time import utc_now
from app.integrations.chroma import ChromaIndex
from app.integrations.openai_gateway import AIGateway
from app.models.entities import (
    ComplianceSession,
    ComplianceSessionStatus,
    FindingStatus,
    PolicyStatus,
    PolicyVersion,
    ReviewedPrecedent,
    StepStatus,
)
from app.repositories import policies as policy_repository
from app.repositories import sessions as session_repository
from app.schemas.ai import ProposedRevision
from app.services.compliance_checker import run_compliance_check
from app.services.jurisdictions import resolve_jurisdictions

TERMINAL_OR_PAUSED_STATUSES = {
    ComplianceSessionStatus.WAITING_FOR_INFORMATION.value,
    ComplianceSessionStatus.WAITING_FOR_APPROVAL.value,
    ComplianceSessionStatus.NEEDS_REVIEW.value,
    ComplianceSessionStatus.READY_TO_PUBLISH.value,
    ComplianceSessionStatus.PUBLISHED.value,
    ComplianceSessionStatus.FAILED.value,
}


class AgentToolError(ValueError):
    pass


def _version_payload(version: PolicyVersion) -> dict[str, Any]:
    return {
        "policy_key": version.policy.key,
        "title": version.title,
        "category": version.category,
        "version": version.version,
        "rule": version.rule_text,
        "rationale": version.rationale,
        "remediation": version.remediation,
        "jurisdictions": version.jurisdictions,
        "violation_examples": version.violation_examples,
        "compliant_examples": version.compliant_examples,
        "exceptions": version.exceptions,
    }


async def build_agent_state(db: AsyncSession, session: ComplianceSession) -> dict[str, Any]:
    findings = await session_repository.findings_for_session(
        db, session.id, posting_version_id=session.current_posting_version_id
    )
    changes = await session_repository.proposed_changes_for_session(db, session.id)
    jurisdictions, unresolved = resolve_jurisdictions(session.posting.target_locations)
    recent_steps = session.steps[-16:]
    return {
        "goal": session.goal,
        "session": {
            "id": session.id,
            "status": session.status,
            "agent_iterations": session.agent_iterations,
            "current_question": session.current_question,
        },
        "posting": {
            "title": session.posting.title,
            "organization_name": session.posting.organization_name,
            "target_locations": session.posting.target_locations,
            "resolved_jurisdictions": jurisdictions,
            "unresolved_locations": unresolved,
            "employment_type": session.posting.employment_type,
            "platform": session.posting.platform,
            "version": session.current_posting_version.version,
            "source": session.current_posting_version.source,
            "approved": session.current_posting_version.approved_at is not None,
            "content": session.current_posting_version.content,
        },
        "current_findings": [
            {
                "policy_key": finding.policy_version.policy.key,
                "title": finding.policy_version.title,
                "category": finding.policy_version.category,
                "status": finding.status,
                "evidence": finding.evidence_text,
                "reason": finding.reason,
                "confidence": finding.confidence,
            }
            for finding in findings
        ],
        "proposed_changes": [
            {
                "original_text": change.original_text,
                "replacement_text": change.replacement_text,
                "reason": change.reason,
                "policy_keys": change.policy_keys,
                "status": change.status,
            }
            for change in changes[-12:]
        ],
        "recent_activity": [
            {
                "kind": step.kind,
                "name": step.name,
                "status": step.status,
                "input": step.input_data if step.kind == "user_message" else {},
                "output": step.output_data,
            }
            for step in recent_steps
            if step.kind != "agent_model"
        ],
        "completion_requirements": {
            "scope_resolved": True,
            "latest_version_checked_against_all_applicable_policies": True,
            "no_violations_or_uncertainties": True,
            "agent_revision_approved_by_recruiter": True,
        },
    }


class AgentToolExecutor:
    def __init__(
        self,
        db: AsyncSession,
        session: ComplianceSession,
        ai: AIGateway,
        index: ChromaIndex,
    ):
        self.db = db
        self.session = session
        self.ai = ai
        self.index = index

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            raise AgentToolError(f"Unknown tool {name}")
        session_id = self.session.id
        started = monotonic()
        try:
            result = await handler(arguments)
        except Exception as error:
            await self.db.rollback()
            self.session = await session_repository.get_session(self.db, session_id)
            await session_repository.add_step(
                self.db,
                session_id,
                kind="tool",
                name=name,
                input_data=arguments,
                output_data={"error": str(error)},
                status=StepStatus.FAILED.value,
                duration_ms=round((monotonic() - started) * 1_000),
            )
            await self.db.commit()
            return {"error": str(error), "retryable": True}
        if name != "run_compliance_check":
            await session_repository.add_step(
                self.db,
                self.session.id,
                kind="tool",
                name=name,
                input_data=arguments,
                output_data=result,
                duration_ms=round((monotonic() - started) * 1_000),
            )
            await self.db.commit()
        return result

    async def _tool_resolve_scope(self, _: dict[str, Any]) -> dict[str, Any]:
        resolved, unresolved = resolve_jurisdictions(self.session.posting.target_locations)
        return {
            "resolved_jurisdictions": resolved,
            "unresolved_locations": unresolved,
            "needs_recruiter_input": not resolved or bool(unresolved),
        }

    async def _tool_set_hiring_locations(self, arguments: dict[str, Any]) -> dict[str, Any]:
        locations = [item.strip() for item in arguments["locations"] if item.strip()]
        if not locations:
            raise AgentToolError("At least one hiring location is required")
        self.session.posting.target_locations = locations
        await self.db.flush()
        resolved, unresolved = resolve_jurisdictions(locations)
        return {"saved": locations, "resolved": resolved, "unresolved": unresolved}

    async def _tool_run_compliance_check(self, _: dict[str, Any]) -> dict[str, Any]:
        resolved, unresolved = resolve_jurisdictions(self.session.posting.target_locations)
        if not resolved or unresolved:
            raise AgentToolError("Resolve every hiring location before checking policies")
        result = await run_compliance_check(self.db, self.session, self.ai)
        return {
            "summary": result.output.summary,
            "policies_checked": len(result.policies),
            "assessments": [
                {
                    "policy_key": finding.policy_version.policy.key,
                    "status": finding.status,
                    "evidence": finding.evidence_text,
                    "reason": finding.reason,
                    "confidence": finding.confidence,
                }
                for finding in result.findings
            ],
        }

    async def _tool_search_policies(self, arguments: dict[str, Any]) -> dict[str, Any]:
        where = None
        if arguments.get("category"):
            where = {"category": arguments["category"]}
        matches = await self.index.search("policy_chunks", arguments["query"], limit=5, where=where)
        valid: list[dict[str, Any]] = []
        for match in matches:
            version = await self.db.scalar(
                select(PolicyVersion)
                .where(
                    PolicyVersion.id == match.metadata.get("policy_version_id"),
                    PolicyVersion.status == PolicyStatus.PUBLISHED.value,
                )
                .options(selectinload(PolicyVersion.policy))
            )
            if not version:
                continue
            if arguments.get("jurisdiction"):
                requested = arguments["jurisdiction"].upper()
                available = {item.upper() for item in version.jurisdictions}
                if available and "GLOBAL" not in available and requested not in available:
                    continue
            valid.append(
                {
                    "policy_key": version.policy.key,
                    "title": version.title,
                    "category": version.category,
                    "passage": match.text,
                    "distance": match.distance,
                }
            )
        return {"matches": valid, "source": "chroma"}

    async def _tool_read_policy(self, arguments: dict[str, Any]) -> dict[str, Any]:
        policy = await policy_repository.get_policy_by_key(self.db, arguments["policy_key"])
        published = [
            version for version in policy.versions if version.status == PolicyStatus.PUBLISHED.value
        ]
        if not published:
            raise AgentToolError("Policy does not have a published version")
        return _version_payload(max(published, key=lambda item: item.version))

    async def _tool_search_reviewed_precedents(self, arguments: dict[str, Any]) -> dict[str, Any]:
        where = None
        if arguments.get("category"):
            where = {"category": arguments["category"]}
        matches = await self.index.search(
            "reviewed_precedents", arguments["query"], limit=5, where=where
        )
        ids = [match.record_id for match in matches]
        precedents = {
            item.id: item
            for item in await self.db.scalars(
                select(ReviewedPrecedent).where(ReviewedPrecedent.id.in_(ids))
            )
        }
        results = []
        for match in matches:
            precedent = precedents.get(match.record_id)
            if not precedent:
                continue
            if arguments.get("jurisdiction") and precedent.jurisdiction not in {
                "GLOBAL",
                arguments["jurisdiction"],
            }:
                continue
            results.append(
                {
                    "excerpt": precedent.excerpt,
                    "decision": precedent.decision,
                    "category": precedent.category,
                    "jurisdiction": precedent.jurisdiction,
                    "distance": match.distance,
                }
            )
        return {"matches": results, "source": "human_reviewed_precedents"}

    async def _tool_propose_revision(self, arguments: dict[str, Any]) -> dict[str, Any]:
        revision = ProposedRevision.model_validate(arguments)
        current_text = self.session.current_posting_version.content
        if revision.revised_text == current_text:
            raise AgentToolError("The proposed revision does not change the posting")
        findings = await session_repository.findings_for_session(
            self.db,
            self.session.id,
            posting_version_id=self.session.current_posting_version_id,
        )
        actionable_policy_keys = {
            finding.policy_version.policy.key
            for finding in findings
            if finding.status in {FindingStatus.VIOLATION.value, FindingStatus.UNCERTAIN.value}
        }
        if not actionable_policy_keys:
            raise AgentToolError("Run a check with actionable findings before proposing edits")
        for change in revision.changes:
            if change.original_text not in current_text:
                raise AgentToolError(
                    f"Original text is not present in the current posting: {change.original_text}"
                )
            if not set(change.policy_keys) <= actionable_policy_keys:
                raise AgentToolError("A proposed edit references a policy without a finding")
        proposed = await session_repository.create_proposed_revision(
            self.db, self.session, revision
        )
        return {
            "posting_version": proposed.version,
            "change_count": len(revision.changes),
            "status": ComplianceSessionStatus.WAITING_FOR_APPROVAL.value,
        }

    async def _tool_ask_recruiter(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.session.current_question = arguments["question"]
        self.session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
        await self.db.flush()
        return {"status": self.session.status, "reason": arguments["reason"]}

    async def _tool_escalate_to_reviewer(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
        self.session.error_message = arguments["summary"]
        await self.db.flush()
        return {
            "status": self.session.status,
            "policy_keys": arguments["policy_keys"],
        }

    async def _tool_complete_session(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.session.current_posting_version.source == "agent":
            if self.session.current_posting_version.approved_at is None:
                raise AgentToolError("The current agent revision has not been approved")
        findings = await session_repository.findings_for_session(
            self.db,
            self.session.id,
            posting_version_id=self.session.current_posting_version_id,
        )
        if not self.session.policy_snapshot_id:
            raise AgentToolError("The session has no policy snapshot")
        resolved, unresolved = resolve_jurisdictions(self.session.posting.target_locations)
        if not resolved or unresolved:
            raise AgentToolError("Hiring location scope is incomplete")
        policies = await policy_repository.applicable_policy_versions(
            self.db,
            self.session.policy_snapshot_id,
            jurisdictions=resolved,
            employment_type=self.session.posting.employment_type,
            platform=self.session.posting.platform,
        )
        if len(findings) != len(policies):
            raise AgentToolError("The current draft has not completed full policy coverage")
        unresolved_findings = [
            finding for finding in findings if finding.status != FindingStatus.NO_VIOLATION.value
        ]
        if unresolved_findings:
            raise AgentToolError("The current draft still has unresolved findings")
        self.session.status = ComplianceSessionStatus.READY_TO_PUBLISH.value
        self.session.completed_at = utc_now()
        await self.db.flush()
        return {"status": self.session.status, "summary": arguments["summary"]}


class ComplianceAgent:
    def __init__(self, settings: Settings, ai: AIGateway, index: ChromaIndex):
        self.settings = settings
        self.ai = ai
        self.index = index

    async def run(self, db: AsyncSession, session_id: str) -> None:
        session = await session_repository.get_session(db, session_id)
        while session.status == ComplianceSessionStatus.INVESTIGATING.value:
            if session.agent_iterations >= self.settings.agent_max_steps:
                session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
                session.error_message = "The agent reached its investigation step limit."
                await db.commit()
                return

            state = await build_agent_state(db, session)
            started = monotonic()
            turn = await self.ai.run_agent(
                instructions=AGENT_INSTRUCTIONS,
                state=state,
                tools=AGENT_TOOLS,
            )
            duration_ms = round((monotonic() - started) * 1_000)
            session.agent_iterations += 1
            await session_repository.add_step(
                db,
                session.id,
                kind="agent_model",
                name="Agent selected its next action",
                output_data={
                    "response_id": turn.response_id,
                    "tools": [call.name for call in turn.tool_calls],
                },
                duration_ms=duration_ms,
                input_tokens=turn.input_tokens,
                output_tokens=turn.output_tokens,
            )
            await db.commit()
            if not turn.tool_calls:
                raise AgentToolError("Agent did not select a tool")

            executor = AgentToolExecutor(db, session, self.ai, self.index)
            for call in turn.tool_calls:
                await executor.execute(call.name, call.arguments)
                session = await session_repository.get_session(db, session_id)
                if session.status in TERMINAL_OR_PAUSED_STATUSES:
                    return
            session = await session_repository.get_session(db, session_id)
