import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.openai_gateway import (
    IncompleteClassifierResponseError,
    OpenAIGateway,
)
from app.models.entities import FindingStatus
from app.schemas.ai import ComplianceCheckOutput, PolicyAssessment


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        openai_checker_model="test-checker",
        openai_checker_reasoning_effort="medium",
        openai_checker_max_output_tokens=12_000,
        openai_checker_policy_batch_size=4,
        openai_store_responses=False,
    )


def completed_response(response_id: str, policy_ids: list[str]) -> SimpleNamespace:
    output = ComplianceCheckOutput(
        input_type="job_posting",
        assessments=[
            PolicyAssessment(
                policy_id=policy_id,
                status=FindingStatus.NO_VIOLATION,
                reason="No prohibited language is present.",
            )
            for policy_id in policy_ids
        ],
        summary="The supplied policies were assessed.",
    )
    return SimpleNamespace(
        id=response_id,
        status="completed",
        output_parsed=output,
        incomplete_details=None,
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


def incomplete_response(response_id: str, reason: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        status="incomplete",
        output_parsed=None,
        incomplete_details=SimpleNamespace(reason=reason),
        usage=SimpleNamespace(input_tokens=100, output_tokens=12_000),
    )


def gateway_with_responses(*responses: SimpleNamespace) -> tuple[OpenAIGateway, AsyncMock]:
    parse = AsyncMock(side_effect=responses)
    gateway = object.__new__(OpenAIGateway)
    gateway.settings = settings()
    gateway.client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    return gateway, parse


async def test_checker_batches_policies_and_combines_complete_results() -> None:
    policy_ids = [f"policy-{index}" for index in range(5)]
    posting = ("Software engineering role. " + "Detailed responsibility. " * 4_000)[:100_000]
    assert len(posting) == 100_000
    gateway, parse = gateway_with_responses(
        completed_response("response-1", policy_ids[:4]),
        completed_response("response-2", policy_ids[4:]),
    )

    result = await gateway.check_compliance(
        posting=posting,
        policies=[{"policy_id": policy_id} for policy_id in policy_ids],
    )

    assert [assessment.policy_id for assessment in result.output.assessments] == policy_ids
    assert result.response_ids == ["response-1", "response-2"]
    assert result.input_tokens == 200
    assert result.output_tokens == 100
    assert [call.kwargs["max_output_tokens"] for call in parse.await_args_list] == [
        12_000,
        12_000,
    ]
    assert all(
        json.loads(call.kwargs["input"])["posting"] == posting for call in parse.await_args_list
    )


async def test_checker_retries_token_exhaustion_once_with_a_larger_limit() -> None:
    gateway, parse = gateway_with_responses(
        incomplete_response("response-incomplete", "max_output_tokens"),
        completed_response("response-complete", ["policy-1"]),
    )

    result = await gateway.check_compliance(
        posting="A sufficiently detailed software engineering job posting.",
        policies=[{"policy_id": "policy-1"}],
    )

    assert [call.kwargs["max_output_tokens"] for call in parse.await_args_list] == [
        12_000,
        24_000,
    ]
    assert result.response_ids == ["response-complete"]
    assert [attempt.response_id for attempt in result.attempts] == [
        "response-incomplete",
        "response-complete",
    ]
    assert result.input_tokens == 200
    assert result.output_tokens == 12_050


async def test_checker_does_not_retry_a_content_filter_stop() -> None:
    gateway, parse = gateway_with_responses(
        incomplete_response("response-filtered", "content_filter")
    )

    with pytest.raises(IncompleteClassifierResponseError) as raised:
        await gateway.check_compliance(
            posting="A sufficiently detailed software engineering job posting.",
            policies=[{"policy_id": "policy-1"}],
        )

    assert parse.await_count == 1
    assert raised.value.reason == "content_filter"
    assert raised.value.details() == {
        "error": "Classifier response was stopped by the content filter",
        "incomplete_reason": "content_filter",
        "response_id": "response-filtered",
        "input_tokens": 100,
        "output_tokens": 12_000,
        "attempts": [
            {
                "response_id": "response-filtered",
                "status": "incomplete",
                "incomplete_reason": "content_filter",
                "input_tokens": 100,
                "output_tokens": 12_000,
                "max_output_tokens": 12_000,
                "policy_count": 1,
            }
        ],
    }
