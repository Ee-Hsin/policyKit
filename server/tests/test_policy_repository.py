from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entities import PolicyStatus
from app.repositories import policies as repository
from app.schemas.policies import PolicyCreate, PolicyDraftUpdate


def policy_create(
    *, key: str = "NY_PAY_001", rule_text: str = "Include a salary range."
) -> PolicyCreate:
    return PolicyCreate(
        key=key,
        title="Salary range disclosure",
        category="compensation",
        rule_text=rule_text,
        jurisdictions=["US-NY"],
        employment_types=["full_time"],
        platforms=["policykit"],
        violation_examples=["Competitive salary"],
        compliant_examples=["Salary range: $100,000-$120,000 USD"],
        effective_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


async def test_published_versions_are_immutable_and_snapshots_preserve_history(
    db: AsyncSession,
) -> None:
    policy = await repository.create_policy(db, policy_create())
    version_one = policy.versions[0]
    policy, snapshot_one = await repository.publish_policy_version(db, policy.id, version_one.id)

    with pytest.raises(repository.PolicyStateError, match="immutable"):
        await repository.update_draft(
            db,
            policy.id,
            version_one.id,
            PolicyDraftUpdate(rule_text="A changed salary disclosure rule."),
        )

    policy = await repository.create_draft_version(db, policy.id)
    version_two = max(policy.versions, key=lambda version: version.version)
    await repository.update_draft(
        db,
        policy.id,
        version_two.id,
        PolicyDraftUpdate(rule_text="Include the salary range and its currency."),
    )
    policy, snapshot_two = await repository.publish_policy_version(db, policy.id, version_two.id)

    stored_version_one = next(version for version in policy.versions if version.version == 1)
    stored_version_two = next(version for version in policy.versions if version.version == 2)
    historical_snapshot = await repository.get_snapshot(db, snapshot_one.id)
    current_snapshot = await repository.get_snapshot(db, snapshot_two.id)

    assert stored_version_one.status == PolicyStatus.RETIRED.value
    assert stored_version_two.status == PolicyStatus.PUBLISHED.value
    assert snapshot_two.version == snapshot_one.version + 1
    assert [item.policy_version_id for item in historical_snapshot.items] == [stored_version_one.id]
    assert [item.policy_version_id for item in current_snapshot.items] == [stored_version_two.id]
    assert historical_snapshot.items[0].policy_version.rule_text == "Include a salary range."
    assert (
        current_snapshot.items[0].policy_version.rule_text
        == "Include the salary range and its currency."
    )


async def test_stale_draft_instance_cannot_modify_a_published_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as setup_db:
        policy = await repository.create_policy(setup_db, policy_create())
        policy_id = policy.id
        version_id = policy.versions[0].id

    async with session_factory() as stale_db, session_factory() as publisher_db:
        await repository.get_policy(stale_db, policy_id)
        await repository.publish_policy_version(publisher_db, policy_id, version_id)

        with pytest.raises(repository.PolicyStateError, match="immutable"):
            await repository.update_draft(
                stale_db,
                policy_id,
                version_id,
                PolicyDraftUpdate(rule_text="Mutated after publication."),
            )

    async with session_factory() as verify_db:
        stored = await repository.get_policy(verify_db, policy_id)
        assert stored.versions[0].rule_text == "Include a salary range."


async def test_new_snapshot_includes_every_currently_published_policy(
    db: AsyncSession,
) -> None:
    first = await repository.create_policy(db, policy_create())
    _, first_snapshot = await repository.publish_policy_version(db, first.id, first.versions[0].id)
    second = await repository.create_policy(
        db,
        policy_create(
            key="GLOBAL_AGE_001",
            rule_text="Do not express a preference based on age.",
        ).model_copy(
            update={
                "title": "Age-related language",
                "category": "discrimination",
                "jurisdictions": ["GLOBAL"],
            }
        ),
    )
    _, second_snapshot = await repository.publish_policy_version(
        db, second.id, second.versions[0].id
    )

    assert len(first_snapshot.items) == 1
    assert {item.policy_version.policy.key for item in second_snapshot.items} == {
        "NY_PAY_001",
        "GLOBAL_AGE_001",
    }


async def test_publish_rejects_future_activation_without_a_scheduler(
    db: AsyncSession,
) -> None:
    policy = await repository.create_policy(
        db,
        policy_create().model_copy(update={"effective_at": datetime(2100, 1, 1, tzinfo=UTC)}),
    )

    with pytest.raises(repository.PolicyStateError, match="Scheduled activation"):
        await repository.publish_policy_version(db, policy.id, policy.versions[0].id)


async def test_publish_rejects_naive_future_activation_without_type_error(
    db: AsyncSession,
) -> None:
    policy = await repository.create_policy(
        db,
        policy_create().model_copy(update={"effective_at": datetime(2100, 1, 1)}),
    )

    with pytest.raises(repository.PolicyStateError, match="Scheduled activation"):
        await repository.publish_policy_version(db, policy.id, policy.versions[0].id)


async def test_publish_rejects_an_expired_policy_without_an_explicit_effective_time(
    db: AsyncSession,
) -> None:
    policy = await repository.create_policy(
        db,
        policy_create().model_copy(
            update={"effective_at": None, "expires_at": datetime(2025, 1, 1, tzinfo=UTC)}
        ),
    )

    with pytest.raises(repository.PolicyStateError, match="Expired"):
        await repository.publish_policy_version(db, policy.id, policy.versions[0].id)


async def test_publish_rejects_a_policy_with_past_effective_and_expiration_times(
    db: AsyncSession,
) -> None:
    policy = await repository.create_policy(
        db,
        policy_create().model_copy(
            update={
                "effective_at": datetime(2024, 1, 1, tzinfo=UTC),
                "expires_at": datetime(2025, 1, 1, tzinfo=UTC),
            }
        ),
    )

    with pytest.raises(repository.PolicyStateError, match="Expired"):
        await repository.publish_policy_version(db, policy.id, policy.versions[0].id)
