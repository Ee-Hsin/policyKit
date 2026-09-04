import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import policies as policy_endpoints
from app.models.entities import ComplianceSessionStatus, FindingStatus, PostingVersion
from app.repositories import policies as policy_repository
from app.repositories import sessions as session_repository
from app.schemas.ai import PolicyAssessment

POLICY_REQUEST = {
    "key": "GLOBAL_AGE_001",
    "title": "Age-related language",
    "category": "discrimination",
    "rule_text": "Do not express a candidate preference based on age.",
    "jurisdictions": ["GLOBAL"],
    "violation_examples": ["Recent graduates preferred"],
    "compliant_examples": ["Candidates at all career stages are welcome"],
}

SESSION_REQUEST = {
    "title": "Software Engineer",
    "job_description": "Build reliable Python services for our learning platform and customers.",
    "target_locations": ["New York"],
}


class NoCostGateway:
    def __init__(self, _settings) -> None:
        pass

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(len(text))] for text in texts]


class NoCostIndex:
    def __init__(self, _settings, _ai) -> None:
        pass

    async def index_policy(self, _version) -> None:
        return None


class FailingGateway:
    def __init__(self, _settings) -> None:
        pass

    async def check_compliance(self, **_kwargs):
        raise RuntimeError("provider unavailable")


async def create_and_publish_policy(
    api_client: httpx.AsyncClient,
    monkeypatch,
    policy_request: dict = POLICY_REQUEST,
) -> tuple[dict, dict]:
    monkeypatch.setattr(policy_endpoints, "OpenAIGateway", NoCostGateway)
    monkeypatch.setattr(policy_endpoints, "ChromaIndex", NoCostIndex)
    created_response = await api_client.post("/api/v1/policies", json=policy_request)
    assert created_response.status_code == 201
    created = created_response.json()
    version = created["versions"][0]
    publish_response = await api_client.post(
        f"/api/v1/policies/{created['id']}/versions/{version['id']}/publish"
    )
    assert publish_response.status_code == 200
    return created, publish_response.json()


async def test_health_uses_the_test_database(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}


async def test_session_starts_as_an_unscheduled_draft_without_a_policy_snapshot(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)

    assert response.status_code == 201
    assert response.json()["status"] == ComplianceSessionStatus.DRAFT.value
    assert response.json()["policy_snapshot_version"] is None


async def test_session_rejects_scope_values_that_could_skip_policies(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/compliance-sessions",
        json={
            **SESSION_REQUEST,
            "employment_type": "full-time",
            "platform": "PolicyKit",
        },
    )

    assert response.status_code == 422


async def test_policy_input_normalizes_scope_and_rejects_unknown_values(
    api_client: httpx.AsyncClient,
) -> None:
    normalized = await api_client.post(
        "/api/v1/policies",
        json={
            **POLICY_REQUEST,
            "key": "NY_AGE_001",
            "jurisdictions": ["New York"],
            "employment_types": ["full_time"],
            "platforms": ["policykit"],
        },
    )
    invalid = await api_client.post(
        "/api/v1/policies",
        json={
            **POLICY_REQUEST,
            "key": "UNKNOWN_SCOPE_001",
            "jurisdictions": ["Atlantis"],
            "employment_types": ["full-time"],
            "platforms": ["PolicyKit"],
        },
    )
    invalid_canonical = await api_client.post(
        "/api/v1/policies",
        json={
            **POLICY_REQUEST,
            "key": "INVALID_CODE_001",
            "jurisdictions": ["US-NYX"],
        },
    )

    assert normalized.status_code == 201
    assert normalized.json()["versions"][0]["jurisdictions"] == ["US-NY"]
    assert invalid.status_code == 422
    assert invalid_canonical.status_code == 422


async def test_policy_input_preserves_the_canonical_canada_scope(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/policies",
        json={
            **POLICY_REQUEST,
            "key": "CA_AGE_001",
            "jurisdictions": ["CA"],
        },
    )

    assert response.status_code == 201
    assert response.json()["versions"][0]["jurisdictions"] == ["CA"]


async def test_policy_patch_rejects_null_for_required_fields(
    api_client: httpx.AsyncClient,
) -> None:
    created = await api_client.post("/api/v1/policies", json=POLICY_REQUEST)
    payload = created.json()

    response = await api_client.patch(
        f"/api/v1/policies/{payload['id']}/versions/{payload['versions'][0]['id']}",
        json={"title": None, "jurisdictions": None},
    )

    assert response.status_code == 422


async def test_policy_test_returns_a_controlled_provider_error(
    api_client: httpx.AsyncClient,
    monkeypatch,
) -> None:
    created = await api_client.post("/api/v1/policies", json=POLICY_REQUEST)
    payload = created.json()
    monkeypatch.setattr(policy_endpoints, "OpenAIGateway", FailingGateway)

    response = await api_client.post(
        f"/api/v1/policies/{payload['id']}/versions/{payload['versions'][0]['id']}/test",
        json={"posting_text": "A sufficiently long example job posting for testing."},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Policy test could not complete"


async def test_admin_can_publish_a_policy_and_session_is_pinned_to_its_snapshot(
    api_client: httpx.AsyncClient, monkeypatch
) -> None:
    created, published = await create_and_publish_policy(api_client, monkeypatch)

    assert published["snapshot_version"] == 1
    assert published["index_status"] == "indexed"
    assert published["policy"]["versions"][0]["status"] == "published"

    response = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "draft"
    assert session["policy_snapshot_version"] is None
    assert session["current_posting_version"]["source"] == "user"

    check = await api_client.post(
        f"/api/v1/compliance-sessions/{session['id']}/check",
        json={"base_version_id": session["current_posting_version"]["id"]},
    )
    assert check.status_code == 202
    assert check.json()["status"] == "queued"
    assert check.json()["policy_snapshot_version"] == 1

    update_response = await api_client.patch(
        f"/api/v1/policies/{created['id']}/versions/{created['versions'][0]['id']}",
        json={"rule_text": "Try to mutate this published version."},
    )
    assert update_response.status_code == 409
    assert update_response.json()["detail"] == "Published policy versions are immutable"


async def test_session_approval_and_publish_endpoints_enforce_state(
    api_client: httpx.AsyncClient, monkeypatch
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]

    approval = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/approve",
        json={
            "base_version_id": created.json()["current_posting_version"]["id"],
            "approved": True,
            "reviewer_name": "Test recruiter",
        },
    )
    assert approval.status_code == 409
    assert approval.json()["detail"] == "The session is not waiting for revision approval"

    publication = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={
            "base_version_id": created.json()["current_posting_version"]["id"],
            "publisher_name": "Test recruiter",
        },
    )
    assert publication.status_code == 409
    assert publication.json()["detail"] == "Only a ready posting can be published"


async def test_message_response_includes_the_recorded_user_step(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/check",
        json={"base_version_id": created.json()["current_posting_version"]["id"]},
    )
    session = await session_repository.get_session(db, session_id)
    session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
    session.current_question = "Which location should be used?"
    await db.commit()

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/messages",
        json={
            "base_version_id": created.json()["current_posting_version"]["id"],
            "message": "Use New York.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.QUEUED.value
    assert payload["steps"][-1]["kind"] == "user_message"
    assert payload["steps"][-1]["input_data"] == {"message": "Use New York."}


async def test_publish_response_includes_the_publication_step(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/check",
        json={"base_version_id": created.json()["current_posting_version"]["id"]},
    )
    session = await session_repository.get_session(db, session_id)
    snapshot = await policy_repository.get_snapshot(db, session.policy_snapshot_id)
    policy_version_id = snapshot.items[0].policy_version_id
    await session_repository.replace_findings(
        db,
        session,
        [
            PolicyAssessment(
                policy_id=policy_version_id,
                status=FindingStatus.NO_VIOLATION,
                reason="The posting contains no prohibited age preference.",
            )
        ],
    )
    session.status = ComplianceSessionStatus.READY_TO_PUBLISH.value
    await db.commit()

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={
            "base_version_id": session.current_posting_version_id,
            "publisher_name": "Test recruiter",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.PUBLISHED.value
    assert payload["steps"][-1]["kind"] == "publication"
    assert payload["steps"][-1]["output_data"] == {"publisher_name": "Test recruiter"}


async def test_reviewer_cannot_approve_an_unchecked_escalated_session(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/check",
        json={"base_version_id": created.json()["current_posting_version"]["id"]},
    )
    session = await session_repository.get_session(db, session_id)
    session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
    await db.commit()

    queue = await api_client.get("/api/v1/reviews")
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()] == [session_id]

    reviewed = await api_client.post(
        f"/api/v1/reviews/{session_id}",
        json={
            "base_version_id": session.current_posting_version_id,
            "reviewer_name": "Policy reviewer",
            "decision": "approve",
            "notes": "Reviewed against the source policy.",
        },
    )
    assert reviewed.status_code == 409
    assert reviewed.json()["detail"] == ("The current draft has not completed full policy coverage")


async def test_reviewer_cannot_promote_evidence_from_an_older_posting_version(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    await api_client.post(
        f"/api/v1/compliance-sessions/{created.json()['id']}/check",
        json={"base_version_id": created.json()["current_posting_version"]["id"]},
    )
    session = await session_repository.get_session(db, created.json()["id"])
    snapshot = await policy_repository.get_snapshot(db, session.policy_snapshot_id)
    policy_version_id = snapshot.items[0].policy_version_id
    await session_repository.replace_findings(
        db,
        session,
        [
            PolicyAssessment(
                policy_id=policy_version_id,
                status=FindingStatus.VIOLATION,
                evidence_text="Python services",
                evidence_start=15,
                evidence_end=30,
                reason="Test finding for the original posting.",
            )
        ],
    )
    old_findings = await session_repository.findings_for_session(
        db,
        session.id,
        posting_version_id=session.current_posting_version_id,
    )
    new_version = PostingVersion(
        posting_id=session.posting_id,
        version=2,
        content="Build reliable services for our learning platform and customers.",
        source="user",
    )
    db.add(new_version)
    await db.flush()
    session.current_posting_version_id = new_version.id
    session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
    await db.commit()

    response = await api_client.post(
        f"/api/v1/reviews/{session.id}",
        json={
            "base_version_id": session.current_posting_version_id,
            "reviewer_name": "Policy reviewer",
            "decision": "reject",
            "promote_to_precedent": True,
            "finding_id": old_findings[0].id,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Finding is not part of the current posting version"


async def test_review_decision_requires_the_current_posting_version(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session = await session_repository.get_session(db, created.json()["id"])
    first_version_id = session.current_posting_version_id
    second_version = PostingVersion(
        posting_id=session.posting_id,
        version=2,
        content="Build dependable Python services and support our learning platform customers.",
        source="recruiter",
    )
    db.add(second_version)
    await db.flush()
    session.current_posting_version_id = second_version.id
    session.current_posting_version = second_version
    session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
    await db.commit()

    stale_review = await api_client.post(
        f"/api/v1/reviews/{session.id}",
        json={
            "base_version_id": first_version_id,
            "reviewer_name": "Policy reviewer",
            "decision": "reject",
            "notes": "This decision belongs to the earlier draft.",
        },
    )
    assert stale_review.status_code == 409
    assert stale_review.json()["detail"] == "The posting changed after this draft was loaded"

    current_review = await api_client.post(
        f"/api/v1/reviews/{session.id}",
        json={
            "base_version_id": second_version.id,
            "reviewer_name": "Policy reviewer",
            "decision": "reject",
            "notes": "Add the missing employment details before another check.",
        },
    )
    assert current_review.status_code == 200
    assert current_review.json()["status"] == ComplianceSessionStatus.REJECTED.value

    unchanged_retry = await api_client.post(
        f"/api/v1/compliance-sessions/{session.id}/check",
        json={"base_version_id": second_version.id},
    )
    assert unchanged_retry.status_code == 409

    edited = await api_client.post(
        f"/api/v1/compliance-sessions/{session.id}/posting-versions",
        json={
            "base_version_id": second_version.id,
            "content": (
                "Build dependable Python services, support our learning platform customers, "
                "and join a full-time New York team."
            ),
        },
    )
    assert edited.status_code == 201
    assert edited.json()["status"] == ComplianceSessionStatus.DRAFT.value
