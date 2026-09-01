"""Constrained full-policy compliance check and deterministic validation."""

from dataclasses import dataclass
from time import monotonic

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.openai_gateway import AIGateway
from app.models.entities import ComplianceFinding, ComplianceSession, PolicyVersion
from app.repositories import policies as policy_repository
from app.repositories import sessions as session_repository
from app.schemas.ai import ComplianceCheckOutput
from app.services.jurisdictions import resolve_jurisdictions


class InvalidComplianceOutputError(ValueError):
    pass


@dataclass
class ComplianceCheckResult:
    output: ComplianceCheckOutput
    policies: list[PolicyVersion]
    findings: list[ComplianceFinding]


def policy_payload(version: PolicyVersion) -> dict:
    return {
        "policy_id": version.id,
        "policy_key": version.policy.key,
        "title": version.policy.title,
        "category": version.policy.category,
        "rule": version.rule_text,
        "rationale": version.rationale,
        "remediation": version.remediation,
        "violation_examples": version.violation_examples,
        "compliant_examples": version.compliant_examples,
        "exceptions": version.exceptions,
    }


def validate_model_output(
    posting: str, policies: list[PolicyVersion], output: ComplianceCheckOutput
) -> None:
    expected_ids = {policy.id for policy in policies}
    returned_ids = [assessment.policy_id for assessment in output.assessments]
    if len(returned_ids) != len(set(returned_ids)):
        raise InvalidComplianceOutputError("Classifier assessed a policy more than once")
    if set(returned_ids) != expected_ids:
        missing = expected_ids - set(returned_ids)
        unexpected = set(returned_ids) - expected_ids
        raise InvalidComplianceOutputError(
            f"Classifier policy coverage mismatch; missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    for assessment in output.assessments:
        if assessment.status.value == "violation" and not assessment.evidence_text:
            raise InvalidComplianceOutputError(
                f"Violation {assessment.policy_id} does not contain evidence"
            )
        if assessment.evidence_text is None:
            continue
        assert assessment.evidence_start is not None
        assert assessment.evidence_end is not None
        actual = posting[assessment.evidence_start : assessment.evidence_end]
        if actual != assessment.evidence_text:
            raise InvalidComplianceOutputError(
                f"Evidence offsets for {assessment.policy_id} do not match the posting"
            )


async def run_compliance_check(
    db: AsyncSession, session: ComplianceSession, ai: AIGateway
) -> ComplianceCheckResult:
    if not session.policy_snapshot_id:
        raise InvalidComplianceOutputError("Session does not have a policy snapshot")
    jurisdictions, _ = resolve_jurisdictions(session.posting.target_locations)
    policies = await policy_repository.applicable_policy_versions(
        db,
        session.policy_snapshot_id,
        jurisdictions=jurisdictions,
        employment_type=session.posting.employment_type,
        platform=session.posting.platform,
    )
    if not policies:
        raise InvalidComplianceOutputError("No applicable policies were found")

    started = monotonic()
    result = await ai.check_compliance(
        posting=session.current_posting_version.content,
        policies=[policy_payload(policy) for policy in policies],
    )
    duration_ms = round((monotonic() - started) * 1_000)
    if result.output.input_type != "job_posting":
        raise InvalidComplianceOutputError("The submitted content is not a job posting")
    validate_model_output(session.current_posting_version.content, policies, result.output)
    findings = await session_repository.replace_findings(db, session, result.output.assessments)
    await session_repository.add_step(
        db,
        session.id,
        kind="compliance_check",
        name="Checked all applicable policies",
        input_data={
            "posting_version": session.current_posting_version.version,
            "policy_keys": [policy.policy.key for policy in policies],
        },
        output_data={
            "summary": result.output.summary,
            "violation_count": sum(
                finding.status == "violation" for finding in findings
            ),
            "uncertain_count": sum(finding.status == "uncertain" for finding in findings),
            "response_id": result.response_id,
        },
        duration_ms=duration_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    await db.commit()
    return ComplianceCheckResult(output=result.output, policies=policies, findings=findings)
