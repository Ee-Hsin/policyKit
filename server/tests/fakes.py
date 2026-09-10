from collections.abc import Callable
from typing import Any

from app.integrations.openai_gateway import ComplianceModelResult
from app.schemas.ai import AgentTurn, ComplianceCheckOutput


class FakeAI:
    def __init__(
        self,
        *,
        compliance_output: ComplianceCheckOutput | None = None,
        agent_turns: list[AgentTurn] | None = None,
        output_factory: Callable[[str, list[dict[str, Any]]], ComplianceCheckOutput] | None = None,
        cache_namespace: str = "fake-checker-v1",
    ) -> None:
        self.compliance_output = compliance_output
        self.agent_turns = list(agent_turns or [])
        self.output_factory = output_factory
        self.checker_cache_namespace = cache_namespace
        self.compliance_calls: list[dict[str, Any]] = []
        self.agent_calls: list[dict[str, Any]] = []

    async def check_compliance(
        self, *, posting: str, policies: list[dict[str, Any]]
    ) -> ComplianceModelResult:
        self.compliance_calls.append({"posting": posting, "policies": policies})
        output = (
            self.output_factory(posting, policies)
            if self.output_factory
            else self.compliance_output
        )
        if output is None:
            raise AssertionError("The test did not configure a compliance response")
        return ComplianceModelResult(
            output=output,
            response_id="fake-compliance-response",
            input_tokens=10,
            output_tokens=5,
        )

    async def run_agent(
        self,
        *,
        instructions: str,
        state: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> AgentTurn:
        self.agent_calls.append({"instructions": instructions, "state": state, "tools": tools})
        if not self.agent_turns:
            raise AssertionError("The test did not configure another agent turn")
        return self.agent_turns.pop(0)
