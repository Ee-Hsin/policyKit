import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import policies as policy_endpoints
from app.models.entities import ComplianceSessionStatus
from app.repositories import sessions as session_repository

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


async def create_and_publish_policy(
    api_client: httpx.AsyncClient, monkeypatch
) -> tuple[dict, dict]:
    monkeypatch.setattr(policy_endpoints, "OpenAIGateway", NoCostGateway)
    monkeypatch.setattr(policy_endpoints, "ChromaIndex", NoCostIndex)
    created_response = await api_client.post("/api/v1/policies", json=POLICY_REQUEST)
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


async def test_session_requires_a_published_policy_snapshot(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Publish at least one policy before starting a compliance session"
    )


async def test_admin_can_publish_a_policy_and_session_is_pinned_to_its_snapshot(
    api_client: httpx.AsyncClient, monkeypatch
) -> None:
    created, published = await create_and_publish_policy(api_client, monkeypatch)

    assert published["snapshot_version"] == 1
    assert published["index_status"] == "indexed"
    assert published["policy"]["versions"][0]["status"] == "published"

    response = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    assert response.status_code == 202
    session = response.json()
    assert session["status"] == "queued"
    assert session["policy_snapshot_version"] == 1
    assert session["current_posting_version"]["source"] == "user"

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
        json={"approved": True, "reviewer_name": "Test recruiter"},
    )
    assert approval.status_code == 409
    assert approval.json()["detail"] == "The session is not waiting for revision approval"

    publication = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={"publisher_name": "Test recruiter"},
    )
    assert publication.status_code == 409
    assert publication.json()["detail"] == "Only a ready posting can be published"


async def test_reviewer_cannot_approve_an_unchecked_escalated_session(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    session = await session_repository.get_session(db, session_id)
    session.status = ComplianceSessionStatus.NEEDS_REVIEW.value
    await db.commit()

    queue = await api_client.get("/api/v1/reviews")
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()] == [session_id]

    reviewed = await api_client.post(
        f"/api/v1/reviews/{session_id}",
        json={
            "reviewer_name": "Policy reviewer",
            "decision": "approve",
            "notes": "Reviewed against the source policy.",
        },
    )
    assert reviewed.status_code == 409
    assert reviewed.json()["detail"] == ("The current draft has not completed full policy coverage")
