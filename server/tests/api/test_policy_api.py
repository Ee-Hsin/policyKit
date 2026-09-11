import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import policies as policy_endpoints
from app.models.entities import ComplianceSessionStatus, FindingStatus
from app.repositories import policies as policy_repository
from app.repositories import sessions as session_repository
from app.schemas.ai import PolicyAssessment, ProposedRevision

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


class FailingGateway:
    def __init__(self, _settings) -> None:
        pass

    async def check_compliance(self, **_kwargs):
        raise RuntimeError("provider unavailable")


async def create_and_publish_policy(api_client: httpx.AsyncClient) -> tuple[dict, dict]:
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


async def test_policy_input_normalizes_category_and_rejects_unknown_values(
    api_client: httpx.AsyncClient,
) -> None:
    normalized = await api_client.post(
        "/api/v1/policies",
        json={**POLICY_REQUEST, "key": "CATEGORY_001", "category": "compensation"},
    )
    invalid = await api_client.post(
        "/api/v1/policies",
        json={**POLICY_REQUEST, "key": "CATEGORY_002", "category": "Benefits"},
    )

    assert normalized.status_code == 201
    assert normalized.json()["category"] == "Compensation"
    assert normalized.json()["versions"][0]["category"] == "Compensation"
    assert invalid.status_code == 422


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
    api_client: httpx.AsyncClient,
) -> None:
    created, published = await create_and_publish_policy(api_client)

    assert published["snapshot_version"] == 1
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
    api_client: httpx.AsyncClient,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]

    approval = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/approve",
        json={
            "decisions": [{"change_id": "missing", "approved": True}],
            "recruiter_name": "Test recruiter",
        },
    )
    assert approval.status_code == 409
    assert approval.json()["detail"] == "The session is not waiting for revision approval"

    publication = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={
            "publisher_name": "Test recruiter",
            "override_reason": "Publish before the review finishes.",
        },
    )
    assert publication.status_code == 409
    assert publication.json()["detail"] == (
        "Wait for the current review step to finish before publishing"
    )


async def test_publication_override_requires_and_records_an_explanation(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    session = await session_repository.get_session(db, session_id)
    session.status = ComplianceSessionStatus.REVIEW_COMPLETE.value
    await db.commit()

    missing_reason = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={"publisher_name": "Test recruiter"},
    )
    assert missing_reason.status_code == 409
    assert missing_reason.json()["detail"] == (
        "Explain why you are overriding the PolicyKit review"
    )

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={
            "publisher_name": "Test recruiter",
            "override_reason": "  The business owner accepted this exception.  ",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.PUBLISHED.value
    assert payload["steps"][-1]["output_data"] == {
        "publisher_name": "Test recruiter",
        "overrode_review": True,
        "override_reason": "The business owner accepted this exception.",
    }


async def test_publication_override_does_not_publish_an_unapproved_agent_revision(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    session = await session_repository.get_session(db, session_id)
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
                reason="The posting contains an age preference.",
            )
        ],
    )
    await session_repository.create_proposed_revision(
        db,
        session,
        ProposedRevision(
            revised_text="Build reliable services for our learning platform and customers.",
            changes=[
                {
                    "original_text": "Python services",
                    "replacement_text": "services",
                    "reason": "Remove the unsupported preference.",
                    "policy_keys": ["GLOBAL_AGE_001"],
                }
            ],
        ),
    )

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/publish",
        json={
            "publisher_name": "Test recruiter",
            "override_reason": "The original wording is required for this role.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.PUBLISHED.value
    assert payload["current_posting_version"]["source"] == "user"
    assert payload["current_posting_version"]["content"] == SESSION_REQUEST["job_description"]
    assert payload["proposed_changes"][0]["status"] == "proposed"


async def test_message_response_includes_the_recorded_user_step(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    session = await session_repository.get_session(db, session_id)
    session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
    session.current_question = "Which location should be used?"
    await db.commit()

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/messages",
        json={"message": "Use New York."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.QUEUED.value
    assert payload["steps"][-1]["kind"] == "user_message"
    assert payload["steps"][-1]["input_data"] == {"message": "Use New York."}


async def test_recruiter_can_edit_a_posting_after_review_finishes_with_findings(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    session = await session_repository.get_session(db, session_id)
    session.status = ComplianceSessionStatus.REVIEW_COMPLETE.value
    await db.commit()
    edited_content = (
        "Build reliable Python services for our learning platform and welcome all candidates."
    )

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/edit",
        json={
            "job_description": edited_content,
            "recruiter_name": "Test recruiter",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.QUEUED.value
    assert payload["current_posting_version"]["version"] == 2
    assert payload["current_posting_version"]["source"] == "user"
    assert payload["current_posting_version"]["content"] == edited_content
    assert len(payload["posting_versions"]) == 2
    assert payload["steps"][-1]["name"] == "Recruiter edited posting"
    assert payload["steps"][-1]["input_data"] == {
        "recruiter_name": "Test recruiter",
        "from_posting_version": 1,
        "to_posting_version": 2,
    }


async def test_recruiter_cannot_edit_a_posting_during_an_active_review(
    api_client: httpx.AsyncClient,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/edit",
        json={
            "job_description": "Build a changed and reliable service for our learning platform.",
            "recruiter_name": "Test recruiter",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The posting can only be edited after a completed review with findings"
    )


async def test_proposed_revision_response_keeps_the_findings_it_addresses(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
    session = await session_repository.get_session(db, session_id)
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
                reason="The posting contains an age preference.",
            )
        ],
    )
    await session_repository.create_proposed_revision(
        db,
        session,
        ProposedRevision(
            revised_text="Build reliable services for our learning platform and clients.",
            changes=[
                {
                    "original_text": "Python services",
                    "replacement_text": "services",
                    "reason": "Remove the unsupported preference.",
                    "policy_keys": ["GLOBAL_AGE_001"],
                },
                {
                    "original_text": "customers",
                    "replacement_text": "clients",
                    "reason": "Use broader customer language.",
                    "policy_keys": ["GLOBAL_AGE_001"],
                },
            ],
        ),
    )

    response = await api_client.get(f"/api/v1/compliance-sessions/{session_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.WAITING_FOR_APPROVAL.value
    assert payload["current_posting_version"]["source"] == "agent"
    assert [finding["policy_key"] for finding in payload["findings"]] == ["GLOBAL_AGE_001"]

    changes = payload["proposed_changes"]
    decision = await api_client.post(
        f"/api/v1/compliance-sessions/{session_id}/approve",
        json={
            "decisions": [
                {"change_id": changes[0]["id"], "approved": True},
                {"change_id": changes[1]["id"], "approved": False},
            ],
            "recruiter_name": "Test recruiter",
            "notes": "Keep the original customer term.",
        },
    )

    assert decision.status_code == 200
    decided = decision.json()
    assert decided["status"] == ComplianceSessionStatus.QUEUED.value
    assert decided["current_posting_version"]["content"] == (
        "Build reliable services for our learning platform and customers."
    )
    assert [change["status"] for change in decided["proposed_changes"]] == [
        "accepted",
        "rejected",
    ]
    assert decided["steps"][-1]["input_data"]["notes"] == ("Keep the original customer term.")


async def test_publish_response_includes_the_publication_step(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await create_and_publish_policy(api_client)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    session_id = created.json()["id"]
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
        json={"publisher_name": "Test recruiter"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ComplianceSessionStatus.PUBLISHED.value
    assert payload["steps"][-1]["kind"] == "publication"
    assert payload["steps"][-1]["output_data"] == {
        "publisher_name": "Test recruiter",
        "overrode_review": False,
    }
