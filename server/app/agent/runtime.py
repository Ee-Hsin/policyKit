"""Durable tool-calling agent runtime."""

from __future__ import annotations

from time import monotonic
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    PolicyVersion,
    ReviewedPrecedent,
    StepStatus,
)
from app.repositories import policies as policy_repository
from app.repositories import sessions as session_repository
from app.schemas.ai import ProposedEditSet, ProposedRevision
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
    steps = await session_repository.steps_for_session(db, session.id)
    jurisdictions, unresolved = resolve_jurisdictions(session.posting.target_locations)
    applicable_policy_ids: set[str] = set()
    if session.policy_snapshot_id and jurisdictions and not unresolved:
        applicable_policy_ids = {
            policy.id
            for policy in await policy_repository.applicable_policy_versions(
                db,
                session.policy_snapshot_id,
                jurisdictions=jurisdictions,
                employment_type=session.posting.employment_type,
                platform=session.posting.platform,
                at=session.created_at,
            )
        }
    checked_policy_ids = [finding.policy_version_id for finding in findings]
    check_is_current = bool(applicable_policy_ids) and (
        len(checked_policy_ids) == len(applicable_policy_ids)
        and set(checked_policy_ids) == applicable_policy_ids
    )
    recent_steps = steps[-16:]
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
        "compliance_check": {
            "current": check_is_current,
            "applicable_policy_count": len(applicable_policy_ids),
        },
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


def available_agent_tools(state: dict[str, Any]) -> list[dict[str, Any]]:
    posting = state["posting"]
    scope_ready = bool(posting["resolved_jurisdictions"]) and not posting["unresolved_locations"]
    if not scope_ready:
        allowed = {"set_hiring_locations", "ask_recruiter", "escalate_to_reviewer"}
    elif state["compliance_check"]["applicable_policy_count"] == 0:
        allowed = {"escalate_to_reviewer"}
    elif not state["compliance_check"]["current"]:
        allowed = {"run_compliance_check"}
    elif any(
        finding["status"] != FindingStatus.NO_VIOLATION.value
        for finding in state["current_findings"]
    ):
        allowed = {
            "search_policies",
            "read_policy",
            "search_reviewed_precedents",
            "propose_revision",
            "ask_recruiter",
            "escalate_to_reviewer",
        }
    else:
        allowed = {"complete_session"}
    return [tool for tool in AGENT_TOOLS if tool["name"] in allowed]


class AgentToolExecutor:
    def __init__(
        self,
        db: AsyncSession,
        session: ComplianceSession,
        ai: AIGateway,
        index: ChromaIndex,
        allowed_tool_names: set[str] | None = None,
    ):
        self.db = db
        self.session = session
        self.ai = ai
        self.index = index
        self.allowed_tool_names = allowed_tool_names

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        session_id = self.session.id
        started = monotonic()
        try:
            if self.allowed_tool_names is not None and name not in self.allowed_tool_names:
                raise AgentToolError(f"Tool {name} is not available in the current session state")
            handler = getattr(self, f"_tool_{name}", None)
            if handler is None:
                raise AgentToolError(f"Unknown tool {name}")
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
            where = {"category": arguments["category"].lower()}
        matches = await self.index.search(
            "policy_chunks", arguments["query"], limit=15, where=where
        )
        if not self.session.policy_snapshot_id:
            raise AgentToolError("The session has no policy snapshot")
        snapshot = await policy_repository.get_snapshot(self.db, self.session.policy_snapshot_id)
        pinned_versions = {item.policy_version_id: item.policy_version for item in snapshot.items}
        valid: list[dict[str, Any]] = []
        for match in matches:
            version = pinned_versions.get(match.metadata.get("policy_version_id"))
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
                    "passage": version.rule_text,
                    "distance": match.distance,
                }
            )
        return {"matches": valid, "source": "chroma"}

    async def _tool_read_policy(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.session.policy_snapshot_id:
            raise AgentToolError("The session has no policy snapshot")
        snapshot = await policy_repository.get_snapshot(self.db, self.session.policy_snapshot_id)
        version = next(
            (
                item.policy_version
                for item in snapshot.items
                if item.policy_version.policy.key == arguments["policy_key"]
            ),
            None,
        )
        if not version:
            raise AgentToolError("Policy is not present in this session's snapshot")
        return _version_payload(version)

    async def _tool_search_reviewed_precedents(self, arguments: dict[str, Any]) -> dict[str, Any]:
        where = None
        if arguments.get("category"):
            where = {"category": arguments["category"].lower()}
        matches = await self.index.search(
            "reviewed_precedents", arguments["query"], limit=15, where=where
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
            requested_jurisdiction = (arguments.get("jurisdiction") or "").upper()
            if requested_jurisdiction and precedent.jurisdiction.upper() not in {
                "GLOBAL",
                requested_jurisdiction,
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
        edit_set = ProposedEditSet.model_validate(arguments)
        current_text = self.session.current_posting_version.content
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
        replacements: list[tuple[int, int, str]] = []
        for change in edit_set.changes:
            if change.original_text == change.replacement_text:
                raise AgentToolError("A proposed edit does not change its source text")
            if current_text.count(change.original_text) != 1:
                raise AgentToolError(
                    "Each original text must occur exactly once in the current posting: "
                    f"{change.original_text}"
                )
            if not set(change.policy_keys) <= actionable_policy_keys:
                raise AgentToolError("A proposed edit references a policy without a finding")
            start = current_text.index(change.original_text)
            end = start + len(change.original_text)
            if (
                not change.replacement_text
                and start > 0
                and end < len(current_text)
                and current_text[start - 1] == " "
                and current_text[end] == " "
            ):
                end += 1
            replacements.append((start, end, change.replacement_text))
        replacements.sort()
        if any(
            current[0] < previous[1]
            for previous, current in zip(replacements, replacements[1:], strict=False)
        ):
            raise AgentToolError("Proposed edits overlap")
        revised_parts: list[str] = []
        cursor = 0
        for start, end, replacement in replacements:
            revised_parts.extend((current_text[cursor:start], replacement))
            cursor = end
        revised_parts.append(current_text[cursor:])
        revision = ProposedRevision(
            revised_text="".join(revised_parts),
            changes=edit_set.changes,
        )
        if revision.revised_text == current_text:
            raise AgentToolError("The proposed revision does not change the posting")
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
        await session_repository.validate_publishable(self.db, self.session)
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
            offered_tools = available_agent_tools(state)
            turn = await self.ai.run_agent(
                instructions=AGENT_INSTRUCTIONS,
                state=state,
                tools=offered_tools,
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
            if len(turn.tool_calls) != 1:
                raise AgentToolError("Agent must select exactly one available tool")

            executor = AgentToolExecutor(
                db,
                session,
                self.ai,
                self.index,
                allowed_tool_names={tool["name"] for tool in offered_tools},
            )
            for call in turn.tool_calls:
                await executor.execute(call.name, call.arguments)
                session = await session_repository.get_session(db, session_id)
                if session.status in TERMINAL_OR_PAUSED_STATUSES:
                    return
            session = await session_repository.get_session(db, session_id)
