"""Seed a useful local policy catalog, snapshot, and authored eval cases."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import SessionFactory
from app.evals.fixtures import AUTHORED_EVAL_CASES, validate_fixtures
from app.models.entities import (
    EvalCase,
    IndexStatus,
    Policy,
    PolicySnapshot,
    PolicySnapshotItem,
    PolicyStatus,
    PolicyVersion,
)

PUBLISHED_AT = datetime(2026, 1, 1, tzinfo=UTC)
LEGACY_PUBLISHED_AT = datetime(2025, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class PolicyVersionSeed:
    rule_text: str
    rationale: str
    remediation: str
    version: int = 1
    jurisdictions: tuple[str, ...] = ("GLOBAL",)
    enforcement_level: str = "standard"
    violation_examples: tuple[str, ...] = ()
    compliant_examples: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    status: str = PolicyStatus.PUBLISHED.value
    effective_at: datetime = PUBLISHED_AT
    expires_at: datetime | None = None
    published_at: datetime = PUBLISHED_AT


@dataclass(frozen=True)
class PolicySeed:
    key: str
    title: str
    category: str
    versions: tuple[PolicyVersionSeed, ...]


POLICY_SEEDS = (
    PolicySeed(
        key="DISC_AGE_PREFERENCE",
        title="No age-based preferences",
        category="Discrimination",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting must not state or imply that applicants are preferred, required, "
                    "or excluded because of age. Age-neutral experience requirements are allowed."
                ),
                rationale="Age preferences can exclude otherwise qualified applicants.",
                remediation="Remove age limits and age-coded preferences; state role requirements.",
                enforcement_level="high",
                violation_examples=(
                    "Applicants must be under 30.",
                    "Recent college graduates are preferred.",
                ),
                compliant_examples=(
                    "Candidates at all career stages are encouraged to apply.",
                    "This role requires three years of Python experience.",
                ),
            ),
        ),
    ),
    PolicySeed(
        key="DISC_PROTECTED_CLASS",
        title="No protected-class preferences",
        category="Discrimination",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting must not prefer, require, or exclude applicants because of race, "
                    "color, national origin, sex, gender, religion, pregnancy, or another "
                    "protected class. A documented lawful occupational qualification requires "
                    "human review."
                ),
                rationale="Hiring criteria must relate to the work rather than protected identity.",
                remediation="Replace identity requirements with the relevant job qualification.",
                enforcement_level="high",
                violation_examples=("Only women should apply.", "Seeking a white male developer."),
                compliant_examples=(
                    "Applicants of all backgrounds are welcome.",
                    "Spanish fluency is required to support Spanish-speaking customers.",
                ),
                exceptions=(
                    "A claimed lawful occupational qualification must be escalated for review.",
                ),
            ),
        ),
    ),
    PolicySeed(
        key="DISC_DISABILITY_ACCOMMODATION",
        title="Use inclusive essential-function language",
        category="Discrimination",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting may describe an essential physical function, but it must not "
                    "exclude people with disabilities when the function can be performed with a "
                    "reasonable accommodation."
                ),
                rationale="Physical requirements should describe the work, not a type of person.",
                remediation=(
                    "Describe the essential function and add reasonable-accommodation language."
                ),
                enforcement_level="high",
                violation_examples=("Able-bodied applicants only; must lift 40 pounds.",),
                compliant_examples=(
                    "Must move packages up to 40 pounds, with reasonable accommodation available.",
                ),
            ),
        ),
    ),
    PolicySeed(
        key="COMP_PAY_TERMS",
        title="State compensation terms clearly",
        category="Compensation",
        versions=(
            PolicyVersionSeed(
                version=1,
                status=PolicyStatus.RETIRED.value,
                effective_at=LEGACY_PUBLISHED_AT,
                expires_at=PUBLISHED_AT,
                published_at=LEGACY_PUBLISHED_AT,
                rule_text="When a posting states pay, it must include a numeric amount.",
                rationale="Applicants need concrete compensation information.",
                remediation="Replace general pay claims with a numeric amount.",
                violation_examples=("Competitive salary.",),
                compliant_examples=("Salary: $120,000.",),
            ),
            PolicyVersionSeed(
                version=2,
                rule_text=(
                    "When a posting states compensation, it must identify a numeric amount or "
                    "range, currency, and pay period such as hourly or annual."
                ),
                rationale="Complete pay terms let applicants compare opportunities accurately.",
                remediation="Add a numeric amount or range, currency, and pay period.",
                violation_examples=("Competitive compensation.", "Pay is $80,000."),
                compliant_examples=(
                    "The annual salary range is $80,000-$95,000 USD.",
                    "The role pays $28 USD per hour.",
                ),
            ),
        ),
    ),
    PolicySeed(
        key="COMP_NY_PAY_RANGE",
        title="New York compensation range",
        category="Compensation",
        versions=(
            PolicyVersionSeed(
                jurisdictions=("US-NY",),
                rule_text=(
                    "A posting for work that can be performed in New York must include a "
                    "good-faith minimum and maximum compensation range."
                ),
                rationale="New York applicants need the expected compensation range.",
                remediation="Add the approved minimum and maximum compensation for the role.",
                enforcement_level="high",
                violation_examples=("We offer competitive compensation.", "Salary up to $150,000."),
                compliant_examples=("The annual salary range is $120,000-$150,000 USD.",),
            ),
        ),
    ),
    PolicySeed(
        key="COMP_CA_PAY_RANGE",
        title="California compensation range",
        category="Compensation",
        versions=(
            PolicyVersionSeed(
                jurisdictions=("US-CA",),
                rule_text=(
                    "A posting for work that can be performed in California must include the "
                    "good-faith minimum and maximum pay scale for the position."
                ),
                rationale="California applicants need the expected pay scale.",
                remediation="Add the approved minimum and maximum pay scale for the position.",
                enforcement_level="high",
                violation_examples=("Pay is competitive.", "Earn up to $40 per hour."),
                compliant_examples=("The hourly pay range is $30-$40 USD.",),
            ),
        ),
    ),
    PolicySeed(
        key="EMP_UNPAID_TRIAL",
        title="No mandatory unpaid trial work",
        category="Employment status",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting for a paid role must not require productive unpaid trial shifts, "
                    "training periods, or take-home work beyond a reasonable skills assessment."
                ),
                rationale="Applicants must not provide productive labor without compensation.",
                remediation="Remove the unpaid work or state its compensation.",
                enforcement_level="high",
                violation_examples=("Two weeks of unpaid training are required.",),
                compliant_examples=("All required training is paid at $24 USD per hour.",),
                exceptions=("Short, non-productive skills assessments may be allowed.",),
            ),
        ),
    ),
    PolicySeed(
        key="EMP_WORKER_CLASSIFICATION",
        title="Do not misrepresent worker classification",
        category="Employment status",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting must not describe a worker as an independent contractor while "
                    "also imposing employee-like control. Ambiguous classifications must be "
                    "escalated because facts outside the posting can determine the result."
                ),
                rationale="Worker classification changes pay, tax, and benefit obligations.",
                remediation="Confirm the classification or revise the work arrangement.",
                enforcement_level="high",
                violation_examples=(
                    "Independent contractor working a fixed daily schedule under direct "
                    "supervision.",
                ),
                compliant_examples=(
                    "Independent contractor controls the schedule and method of completing "
                    "the project.",
                ),
            ),
        ),
    ),
    PolicySeed(
        key="TRANSPARENCY_EMPLOYER_IDENTITY",
        title="Identify the hiring organization",
        category="Transparency",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting must identify the hiring organization in the posting or through a "
                    "verified employer profile displayed with it."
                ),
                rationale=(
                    "Applicants should know which organization will receive their information."
                ),
                remediation="Add the employer name or link a verified employer profile.",
                violation_examples=(
                    "Confidential company seeks assistants. Apply by text message.",
                ),
                compliant_examples=("Acme Software is hiring a Software Engineer.",),
                exceptions=(
                    "A verified employer profile displayed by the platform satisfies the rule.",
                ),
            ),
        ),
    ),
    PolicySeed(
        key="TRANSPARENCY_ROLE_ACCURACY",
        title="Describe the role accurately",
        category="Transparency",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting must describe the actual work and must not use false job titles, "
                    "guaranteed earnings, or misleading claims about duties or advancement."
                ),
                rationale="Applicants need accurate information to make an informed decision.",
                remediation="State the actual duties and remove unsupported guarantees.",
                violation_examples=(
                    "Guaranteed $20,000 monthly income with no work or experience.",
                ),
                compliant_examples=("You will build and maintain customer-facing web services.",),
            ),
        ),
    ),
    PolicySeed(
        key="CONTENT_SENSITIVE_DATA",
        title="Do not request sensitive application data",
        category="Content",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A public posting must not ask applicants to submit Social Security numbers, "
                    "bank account details, payment card numbers, passwords, or authentication "
                    "codes."
                ),
                rationale="Sensitive data requests expose applicants to identity theft and fraud.",
                remediation="Remove the request and use a secure authorized process when needed.",
                enforcement_level="critical",
                violation_examples=("Include your Social Security number and bank details.",),
                compliant_examples=("Apply with your resume and work samples.",),
            ),
        ),
    ),
    PolicySeed(
        key="CONTENT_ILLEGAL_ACTIVITY",
        title="No illegal or fraudulent work",
        category="Content",
        versions=(
            PolicyVersionSeed(
                rule_text=(
                    "A posting must not recruit people to perform illegal activity, fraud, theft, "
                    "unauthorized access, or infringement of third-party rights."
                ),
                rationale="The platform must not facilitate illegal or fraudulent work.",
                remediation=(
                    "Reject the posting; do not rewrite an illegal role into publishable form."
                ),
                enforcement_level="critical",
                violation_examples=("Redistribute paid streaming content without permission.",),
                compliant_examples=("Manage licensed media assets for an authorized publisher.",),
            ),
        ),
    ),
)


def _version_values(seed: PolicyVersionSeed, *, title: str, category: str) -> dict[str, object]:
    return {
        "version": seed.version,
        "title": title,
        "category": category,
        "status": seed.status,
        "rule_text": seed.rule_text,
        "rationale": seed.rationale,
        "remediation": seed.remediation,
        "enforcement_level": seed.enforcement_level,
        "jurisdictions": list(seed.jurisdictions),
        "employment_types": [],
        "platforms": [],
        "violation_examples": list(seed.violation_examples),
        "compliant_examples": list(seed.compliant_examples),
        "exceptions": list(seed.exceptions),
        "effective_at": seed.effective_at,
        "expires_at": seed.expires_at,
        "published_at": seed.published_at,
        "index_status": IndexStatus.PENDING.value,
    }


async def seed_policies(db: AsyncSession) -> list[PolicyVersion]:
    published_versions: list[PolicyVersion] = []
    for seed in POLICY_SEEDS:
        policy = await db.scalar(
            select(Policy).where(Policy.key == seed.key).options(selectinload(Policy.versions))
        )
        if policy is None:
            policy = Policy(key=seed.key)
            policy.versions.extend(
                PolicyVersion(
                    **_version_values(
                        version_seed,
                        title=seed.title,
                        category=seed.category,
                    )
                )
                for version_seed in seed.versions
            )
            db.add(policy)
            await db.flush()
        versions_by_number = {version.version: version for version in policy.versions}
        missing_versions = {version.version for version in seed.versions} - set(versions_by_number)
        if missing_versions:
            raise RuntimeError(
                f"Seed policy {seed.key} exists without versions {sorted(missing_versions)}"
            )
        published = [
            version for version in policy.versions if version.status == PolicyStatus.PUBLISHED.value
        ]
        if not published:
            raise RuntimeError(f"Seed policy {seed.key} has no published version")
        published_versions.append(max(published, key=lambda item: item.version))
    return published_versions


async def seed_snapshot(
    db: AsyncSession, published_versions: list[PolicyVersion]
) -> PolicySnapshot:
    version_ids = {version.id for version in published_versions}
    snapshots = list(
        await db.scalars(
            select(PolicySnapshot)
            .options(selectinload(PolicySnapshot.items))
            .order_by(PolicySnapshot.version.desc())
        )
    )
    for snapshot in snapshots:
        if {item.policy_version_id for item in snapshot.items} == version_ids:
            return snapshot

    next_version = (await db.scalar(select(func.max(PolicySnapshot.version))) or 0) + 1
    snapshot = PolicySnapshot(version=next_version)
    snapshot.items.extend(
        PolicySnapshotItem(policy_version_id=policy_version_id)
        for policy_version_id in sorted(version_ids)
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def seed_eval_cases(db: AsyncSession) -> int:
    validate_fixtures({seed.key for seed in POLICY_SEEDS})
    updated = 0
    for fixture in AUTHORED_EVAL_CASES:
        eval_case = await db.scalar(select(EvalCase).where(EvalCase.name == fixture.name))
        values = {
            "posting_text": fixture.posting_text,
            "jurisdictions": list(fixture.jurisdictions),
            "expected_assessments": dict(fixture.expected_assessments),
            "source": "authored",
            "active": True,
        }
        if eval_case is None:
            db.add(EvalCase(name=fixture.name, **values))
        else:
            for field, value in values.items():
                setattr(eval_case, field, value)
        updated += 1
    await db.flush()
    return updated


async def seed_database() -> None:
    async with SessionFactory() as db:
        await seed_policies(db)
        published_versions = list(
            await db.scalars(
                select(PolicyVersion).where(PolicyVersion.status == PolicyStatus.PUBLISHED.value)
            )
        )
        snapshot = await seed_snapshot(db, published_versions)
        eval_count = await seed_eval_cases(db)
        await db.commit()
    print(
        f"Seeded {len(published_versions)} published policies, "
        f"snapshot {snapshot.version}, and {eval_count} eval cases."
    )
    print("Chroma indexing was not run; use `python -m app.scripts.reindex` when ready.")


if __name__ == "__main__":
    asyncio.run(seed_database())
