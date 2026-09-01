import pytest

from app.models.entities import FindingStatus, PolicyVersion
from app.schemas.ai import ComplianceCheckOutput, PolicyAssessment
from app.services.compliance_checker import InvalidComplianceOutputError, validate_model_output


def policy_version(policy_id: str) -> PolicyVersion:
    return PolicyVersion(
        id=policy_id,
        policy_id=f"policy-{policy_id}",
        version=1,
        rule_text="A sufficiently detailed policy rule.",
    )


def assessment(
    policy_id: str,
    *,
    status: FindingStatus = FindingStatus.NO_VIOLATION,
    evidence_text: str | None = None,
    evidence_start: int | None = None,
    evidence_end: int | None = None,
) -> PolicyAssessment:
    return PolicyAssessment(
        policy_id=policy_id,
        status=status,
        evidence_text=evidence_text,
        evidence_start=evidence_start,
        evidence_end=evidence_end,
        reason="Test assessment",
        confidence=0.9,
    )


def output(*assessments: PolicyAssessment) -> ComplianceCheckOutput:
    return ComplianceCheckOutput(
        input_type="job_posting",
        assessments=list(assessments),
        summary="Test result",
    )


def test_accepts_exact_policy_coverage_and_exact_evidence_offsets() -> None:
    posting = "Recent graduates preferred for this software engineering role."
    evidence = "Recent graduates preferred"

    validate_model_output(
        posting,
        [policy_version("age"), policy_version("salary")],
        output(
            assessment(
                "age",
                status=FindingStatus.VIOLATION,
                evidence_text=evidence,
                evidence_start=0,
                evidence_end=len(evidence),
            ),
            assessment("salary"),
        ),
    )


@pytest.mark.parametrize(
    ("assessments", "message"),
    [
        ([assessment("age")], "coverage mismatch"),
        (
            [assessment("age"), assessment("age"), assessment("salary")],
            "more than once",
        ),
        ([assessment("age"), assessment("unknown")], "coverage mismatch"),
    ],
)
def test_rejects_missing_duplicate_or_unknown_policy_assessments(
    assessments: list[PolicyAssessment], message: str
) -> None:
    with pytest.raises(InvalidComplianceOutputError, match=message):
        validate_model_output(
            "A detailed software engineering job posting.",
            [policy_version("age"), policy_version("salary")],
            output(*assessments),
        )


def test_rejects_violation_without_evidence() -> None:
    with pytest.raises(InvalidComplianceOutputError, match="does not contain evidence"):
        validate_model_output(
            "A detailed software engineering job posting.",
            [policy_version("age")],
            output(assessment("age", status=FindingStatus.VIOLATION)),
        )


def test_rejects_evidence_that_does_not_match_posting_offsets() -> None:
    with pytest.raises(InvalidComplianceOutputError, match="do not match"):
        validate_model_output(
            "Recent graduates preferred for this role.",
            [policy_version("age")],
            output(
                assessment(
                    "age",
                    status=FindingStatus.VIOLATION,
                    evidence_text="graduates preferred",
                    evidence_start=0,
                    evidence_end=19,
                )
            ),
        )
