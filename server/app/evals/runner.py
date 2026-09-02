"""Run fixture validation locally or opt into live constrained-checker evals."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.evals.fixtures import AUTHORED_EVAL_CASES, validate_fixtures

if TYPE_CHECKING:
    from app.models.entities import EvalCase, PolicyVersion


@dataclass
class EvalMetrics:
    cases: int = 0
    exact_cases: int = 0
    assessments: int = 0
    correct_assessments: int = 0
    true_violations: int = 0
    false_violations: int = 0
    missed_violations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct_assessments / self.assessments if self.assessments else 0.0

    @property
    def violation_recall(self) -> float:
        total = self.true_violations + self.missed_violations
        return self.true_violations / total if total else 1.0

    @property
    def violation_precision(self) -> float:
        total = self.true_violations + self.false_violations
        return self.true_violations / total if total else 1.0


def add_case_result(
    metrics: EvalMetrics,
    *,
    case_name: str,
    expected: dict[str, str],
    actual: dict[str, str],
) -> None:
    metrics.cases += 1
    case_matches = True
    for policy_key, expected_status in expected.items():
        actual_status = actual.get(policy_key)
        metrics.assessments += 1
        if actual_status == expected_status:
            metrics.correct_assessments += 1
        else:
            case_matches = False
            metrics.mismatches.append(
                f"{case_name}: {policy_key} expected {expected_status}, got {actual_status}"
            )
        if expected_status == "violation" and actual_status == "violation":
            metrics.true_violations += 1
        elif expected_status == "violation":
            metrics.missed_violations += 1
        elif actual_status == "violation":
            metrics.false_violations += 1
    if set(actual) != set(expected):
        case_matches = False
        metrics.mismatches.append(f"{case_name}: checker did not return the expected policy set")
    if case_matches:
        metrics.exact_cases += 1


async def load_live_inputs(
    selected_names: set[str], limit: int | None
) -> tuple[list[EvalCase], list[PolicyVersion]]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.database import SessionFactory
    from app.models.entities import EvalCase, Policy, PolicyStatus, PolicyVersion

    async with SessionFactory() as db:
        case_statement = select(EvalCase).where(EvalCase.active.is_(True)).order_by(EvalCase.name)
        if selected_names:
            case_statement = case_statement.where(EvalCase.name.in_(selected_names))
        if limit is not None:
            case_statement = case_statement.limit(limit)
        cases = list(await db.scalars(case_statement))
        policies = list(
            await db.scalars(
                select(PolicyVersion)
                .where(PolicyVersion.status == PolicyStatus.PUBLISHED.value)
                .options(selectinload(PolicyVersion.policy))
                .join(Policy)
                .order_by(PolicyVersion.category, Policy.key)
            )
        )
    if not cases:
        raise RuntimeError("No active eval cases matched. Run the seed script first.")
    if not policies:
        raise RuntimeError("No published policies exist. Run the seed script first.")
    return cases, policies


async def run_live(selected_names: set[str], limit: int | None) -> int:
    from app.core.config import get_settings
    from app.integrations.openai_gateway import OpenAIGateway
    from app.repositories.policies import policy_applies
    from app.services.compliance_checker import (
        normalize_evidence_offsets,
        policy_payload,
        validate_model_output,
    )

    settings = get_settings()
    gateway = OpenAIGateway(settings)
    cases, published_policies = await load_live_inputs(selected_names, limit)
    metrics = EvalMetrics()

    for case in cases:
        applicable = [
            version
            for version in published_policies
            if policy_applies(
                version,
                jurisdictions=case.jurisdictions,
                employment_type="full_time",
                platform="policykit",
                at=case.created_at,
            )
        ]
        keys_by_id = {version.id: version.policy.key for version in applicable}
        expected = {policy_key: "no_violation" for policy_key in keys_by_id.values()}
        unexpected_fixture_keys = set(case.expected_assessments) - set(expected)
        if unexpected_fixture_keys:
            raise RuntimeError(
                f"Eval case {case.name} expects policies outside its scope: "
                f"{sorted(unexpected_fixture_keys)}"
            )
        expected.update(case.expected_assessments)

        response = await gateway.check_compliance(
            posting=case.posting_text,
            policies=[policy_payload(version) for version in applicable],
        )
        if response.output.input_type != "job_posting":
            raise RuntimeError(f"Checker rejected eval case {case.name} as non-job content")
        normalize_evidence_offsets(case.posting_text, response.output)
        validate_model_output(case.posting_text, applicable, response.output)
        actual = {
            keys_by_id[assessment.policy_id]: assessment.status.value
            for assessment in response.output.assessments
        }
        reasons = {
            keys_by_id[assessment.policy_id]: assessment.reason
            for assessment in response.output.assessments
        }
        add_case_result(
            metrics,
            case_name=case.name,
            expected=expected,
            actual=actual,
        )
        metrics.input_tokens += response.input_tokens or 0
        metrics.output_tokens += response.output_tokens or 0
        result = "PASS" if all(actual[key] == value for key, value in expected.items()) else "FAIL"
        print(f"{result} {case.name} ({len(applicable)} policies)")
        if result == "FAIL":
            for policy_key, expected_status in expected.items():
                actual_status = actual[policy_key]
                if actual_status != expected_status:
                    print(
                        f"  {policy_key}: expected {expected_status}, got {actual_status}; "
                        f"{reasons[policy_key]}"
                    )

    print()
    print(f"Exact cases: {metrics.exact_cases}/{metrics.cases}")
    print(f"Assessment accuracy: {metrics.accuracy:.1%}")
    print(f"Violation recall: {metrics.violation_recall:.1%}")
    print(f"Violation precision: {metrics.violation_precision:.1%}")
    print(f"Tokens: {metrics.input_tokens} input, {metrics.output_tokens} output")
    if metrics.mismatches:
        print("Mismatches:")
        for mismatch in metrics.mismatches:
            print(f"- {mismatch}")
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the configured OpenAI checker. This incurs API usage.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Run one named database case. May be supplied more than once.",
    )
    parser.add_argument("--limit", type=int, help="Limit the number of live cases.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy_keys = {
        "DISC_AGE_PREFERENCE",
        "DISC_PROTECTED_CLASS",
        "DISC_DISABILITY_ACCOMMODATION",
        "COMP_PAY_TERMS",
        "COMP_NY_PAY_RANGE",
        "COMP_CA_PAY_RANGE",
        "EMP_UNPAID_TRIAL",
        "EMP_WORKER_CLASSIFICATION",
        "TRANSPARENCY_EMPLOYER_IDENTITY",
        "TRANSPARENCY_ROLE_ACCURACY",
        "CONTENT_SENSITIVE_DATA",
        "CONTENT_ILLEGAL_ACTIVITY",
    }
    validate_fixtures(policy_keys)
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be greater than zero")
    if not args.live:
        print(f"Validated {len(AUTHORED_EVAL_CASES)} authored eval fixtures.")
        print("No API calls were made. Add --live to run the configured OpenAI checker.")
        return 0
    return asyncio.run(run_live(set(args.case), args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
