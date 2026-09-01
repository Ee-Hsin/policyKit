"""Policy persistence and snapshot queries."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time import utc_now
from app.models.entities import (
    IndexStatus,
    Policy,
    PolicySnapshot,
    PolicySnapshotItem,
    PolicyStatus,
    PolicyVersion,
)
from app.schemas.policies import PolicyCreate, PolicyDraftUpdate


class PolicyNotFoundError(LookupError):
    pass


class PolicyStateError(ValueError):
    pass


async def create_policy(db: AsyncSession, data: PolicyCreate) -> Policy:
    existing = await db.scalar(select(Policy).where(Policy.key == data.key))
    if existing:
        raise PolicyStateError(f"Policy key {data.key} already exists")

    policy = Policy(key=data.key)
    version_fields = data.model_dump(exclude={"key"})
    policy.versions.append(PolicyVersion(version=1, **version_fields))
    db.add(policy)
    await db.commit()
    return await get_policy(db, policy.id)


async def get_policy(db: AsyncSession, policy_id: str) -> Policy:
    policy = await db.scalar(
        select(Policy).where(Policy.id == policy_id).options(selectinload(Policy.versions))
    )
    if not policy:
        raise PolicyNotFoundError(policy_id)
    return policy


async def get_policy_by_key(db: AsyncSession, key: str) -> Policy:
    policy = await db.scalar(
        select(Policy).where(Policy.key == key).options(selectinload(Policy.versions))
    )
    if not policy:
        raise PolicyNotFoundError(key)
    return policy


async def list_policies(db: AsyncSession) -> list[Policy]:
    result = await db.scalars(
        select(Policy).options(selectinload(Policy.versions)).order_by(Policy.key)
    )
    return list(result.unique())


async def update_draft(
    db: AsyncSession, policy_id: str, version_id: str, data: PolicyDraftUpdate
) -> Policy:
    policy = await get_policy(db, policy_id)
    version = next((item for item in policy.versions if item.id == version_id), None)
    if not version:
        raise PolicyNotFoundError(version_id)
    if version.status not in {PolicyStatus.DRAFT.value, PolicyStatus.TESTING.value}:
        raise PolicyStateError("Published policy versions are immutable")

    values = data.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(version, field, value)
    await db.commit()
    return await get_policy(db, policy_id)


async def create_draft_version(db: AsyncSession, policy_id: str) -> Policy:
    policy = await get_policy(db, policy_id)
    if any(version.status == PolicyStatus.DRAFT.value for version in policy.versions):
        raise PolicyStateError("This policy already has a draft version")
    latest = max(policy.versions, key=lambda item: item.version)
    fields = {
        "title": latest.title,
        "category": latest.category,
        "rule_text": latest.rule_text,
        "rationale": latest.rationale,
        "remediation": latest.remediation,
        "enforcement_level": latest.enforcement_level,
        "jurisdictions": list(latest.jurisdictions),
        "employment_types": list(latest.employment_types),
        "platforms": list(latest.platforms),
        "violation_examples": list(latest.violation_examples),
        "compliant_examples": list(latest.compliant_examples),
        "exceptions": list(latest.exceptions),
        "effective_at": latest.effective_at,
        "expires_at": latest.expires_at,
    }
    policy.versions.append(PolicyVersion(version=latest.version + 1, **fields))
    await db.commit()
    return await get_policy(db, policy_id)


async def publish_policy_version(
    db: AsyncSession, policy_id: str, version_id: str
) -> tuple[Policy, PolicySnapshot]:
    policy = await get_policy(db, policy_id)
    version = next((item for item in policy.versions if item.id == version_id), None)
    if not version:
        raise PolicyNotFoundError(version_id)
    if version.status not in {PolicyStatus.DRAFT.value, PolicyStatus.TESTING.value}:
        raise PolicyStateError("Only a draft or testing policy can be published")
    if not version.violation_examples or not version.compliant_examples:
        raise PolicyStateError("Published policies require violation and compliant examples")
    if version.expires_at and version.effective_at and version.expires_at <= version.effective_at:
        raise PolicyStateError("Expiration must occur after the effective date")

    now = utc_now()
    for other in policy.versions:
        if other.status == PolicyStatus.PUBLISHED.value:
            other.status = PolicyStatus.RETIRED.value
    version.status = PolicyStatus.PUBLISHED.value
    version.published_at = now
    version.effective_at = version.effective_at or now
    version.index_status = IndexStatus.PENDING.value

    next_snapshot_version = (await db.scalar(select(func.max(PolicySnapshot.version))) or 0) + 1
    snapshot = PolicySnapshot(version=next_snapshot_version)
    db.add(snapshot)
    await db.flush()

    active_versions = list(
        await db.scalars(
            select(PolicyVersion).where(PolicyVersion.status == PolicyStatus.PUBLISHED.value)
        )
    )
    if version not in active_versions:
        active_versions.append(version)
    db.add_all(
        [
            PolicySnapshotItem(snapshot_id=snapshot.id, policy_version_id=active_version.id)
            for active_version in active_versions
        ]
    )

    await db.commit()
    return await get_policy(db, policy_id), await get_snapshot(db, snapshot.id)


async def get_snapshot(db: AsyncSession, snapshot_id: str) -> PolicySnapshot:
    snapshot = await db.scalar(
        select(PolicySnapshot)
        .where(PolicySnapshot.id == snapshot_id)
        .options(
            selectinload(PolicySnapshot.items)
            .selectinload(PolicySnapshotItem.policy_version)
            .selectinload(PolicyVersion.policy)
        )
    )
    if not snapshot:
        raise PolicyNotFoundError(snapshot_id)
    return snapshot


async def get_latest_snapshot(db: AsyncSession) -> PolicySnapshot | None:
    snapshot_id = await db.scalar(
        select(PolicySnapshot.id).order_by(PolicySnapshot.version.desc()).limit(1)
    )
    return await get_snapshot(db, snapshot_id) if snapshot_id else None


def policy_applies(
    version: PolicyVersion,
    jurisdictions: list[str],
    employment_type: str,
    platform: str,
    at: datetime,
) -> bool:
    policy_jurisdictions = {item.upper() for item in version.jurisdictions}
    requested_jurisdictions = {item.upper() for item in jurisdictions}
    jurisdiction_match = (
        not policy_jurisdictions
        or "GLOBAL" in policy_jurisdictions
        or bool(policy_jurisdictions & requested_jurisdictions)
    )
    employment_match = not version.employment_types or employment_type in version.employment_types
    platform_match = not version.platforms or platform in version.platforms
    effective = version.effective_at is None or version.effective_at <= at
    unexpired = version.expires_at is None or version.expires_at > at
    return jurisdiction_match and employment_match and platform_match and effective and unexpired


async def applicable_policy_versions(
    db: AsyncSession,
    snapshot_id: str,
    jurisdictions: list[str],
    employment_type: str,
    platform: str,
    at: datetime | None = None,
) -> list[PolicyVersion]:
    snapshot = await get_snapshot(db, snapshot_id)
    check_time = at or utc_now()
    return [
        item.policy_version
        for item in snapshot.items
        if policy_applies(item.policy_version, jurisdictions, employment_type, platform, check_time)
    ]


async def search_canonical_policies(
    db: AsyncSession, *, category: str | None = None, jurisdiction: str | None = None
) -> list[PolicyVersion]:
    statement = (
        select(PolicyVersion)
        .where(PolicyVersion.status == PolicyStatus.PUBLISHED.value)
        .options(selectinload(PolicyVersion.policy))
    )
    if category:
        statement = statement.where(func.lower(PolicyVersion.category) == category.lower())
    versions = list(await db.scalars(statement))
    if jurisdiction:
        needle = jurisdiction.upper()
        versions = [
            version
            for version in versions
            if not version.jurisdictions
            or "GLOBAL" in {item.upper() for item in version.jurisdictions}
            or needle in {item.upper() for item in version.jurisdictions}
        ]
    return versions
