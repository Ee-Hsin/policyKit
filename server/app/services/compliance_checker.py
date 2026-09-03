"""Constrained full-policy compliance check and deterministic validation."""

import hashlib
import json
from dataclasses import dataclass
from time import monotonic

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.openai_gateway import AIGateway
from app.models.entities import (
    ComplianceCacheEntry,
    ComplianceFinding,
    ComplianceSession,
    PolicyVersion,
)
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
        "title": version.title,
        "category": version.category,
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


def normalize_evidence_offsets(posting: str, output: ComplianceCheckOutput) -> None:
    for assessment in output.assessments:
        evidence = assessment.evidence_text
        if evidence is None:
            continue
        start = assessment.evidence_start
        end = assessment.evidence_end
        if start is not None and end is not None and posting[start:end] == evidence:
            continue
        first_match = posting.find(evidence)
        if first_match < 0 or posting.find(evidence, first_match + 1) >= 0:
            continue
        assessment.evidence_start = first_match
        assessment.evidence_end = first_match + len(evidence)


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
        at=session.created_at,
    )
    if not policies:
        raise InvalidComplianceOutputError("No applicable policies were found")

    cache_input = {
        "posting": session.current_posting_version.content,
        "policy_snapshot_id": session.policy_snapshot_id,
        "policy_version_ids": sorted(policy.id for policy in policies),
        "model_namespace": ai.checker_cache_namespace,
    }
    cache_key = hashlib.sha256(json.dumps(cache_input, sort_keys=True).encode("utf-8")).hexdigest()
    cached = await db.scalar(
        select(ComplianceCacheEntry).where(ComplianceCacheEntry.cache_key == cache_key)
    )
    started = monotonic()
    if cached:
        try:
            output = ComplianceCheckOutput.model_validate(cached.result)
            normalize_evidence_offsets(session.current_posting_version.content, output)
            validate_model_output(session.current_posting_version.content, policies, output)
        except (ValidationError, InvalidComplianceOutputError):
            await db.delete(cached)
            await db.flush()
            cached = None
    if not cached:
        model_result = await ai.check_compliance(
            posting=session.current_posting_version.content,
            policies=[policy_payload(policy) for policy in policies],
        )
        output = model_result.output
        normalize_evidence_offsets(session.current_posting_version.content, output)
        response_id = model_result.response_id
        input_tokens = model_result.input_tokens
        output_tokens = model_result.output_tokens
    else:
        response_id = "exact-cache"
        input_tokens = 0
        output_tokens = 0
    duration_ms = round((monotonic() - started) * 1_000)
    if output.input_type != "job_posting":
        raise InvalidComplianceOutputError("The submitted content is not a job posting")
    validate_model_output(session.current_posting_version.content, policies, output)
    if not cached:
        cache_values = {
            "cache_key": cache_key,
            "policy_snapshot_id": session.policy_snapshot_id,
            "model_namespace": ai.checker_cache_namespace,
            "result": output.model_dump(mode="json"),
        }
        dialect_name = db.bind.dialect.name if db.bind else ""
        if dialect_name == "postgresql":
            await db.execute(
                postgresql_insert(ComplianceCacheEntry)
                .values(**cache_values)
                .on_conflict_do_nothing(index_elements=["cache_key"])
            )
        elif dialect_name == "sqlite":
            await db.execute(
                sqlite_insert(ComplianceCacheEntry)
                .values(**cache_values)
                .on_conflict_do_nothing(index_elements=["cache_key"])
            )
        else:
            db.add(ComplianceCacheEntry(**cache_values))
    findings = await session_repository.replace_findings(db, session, output.assessments)
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
            "summary": output.summary,
            "violation_count": sum(finding.status == "violation" for finding in findings),
            "uncertain_count": sum(finding.status == "uncertain" for finding in findings),
            "response_id": response_id,
            "cache_hit": cached is not None,
        },
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    await db.commit()
    return ComplianceCheckResult(output=output, policies=policies, findings=findings)
