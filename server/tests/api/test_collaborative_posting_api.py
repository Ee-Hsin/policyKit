import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.endpoints import sessions as session_endpoints
from app.api.v1.endpoints import writing_assistance as writing_endpoints
from app.integrations.openai_gateway import MissingAIConfigurationError
from app.models.entities import (
    ComplianceSession,
    ComplianceSessionStatus,
    JobPosting,
    PostingVersion,
)
from app.repositories import sessions as session_repository
from app.schemas.ai import (
    InitialPostingDraftOutput,
    ProposedEdit,
    ProposedRevision,
    WritingSuggestionOutput,
)
from tests.api.test_policy_api import POLICY_REQUEST, SESSION_REQUEST, create_and_publish_policy


class UnexpectedGateway:
    def __init__(self, _settings) -> None:
        raise AssertionError("This action must not call OpenAI")


class FakeWritingGateway:
    def __init__(
        self,
        *,
        initial: InitialPostingDraftOutput | None = None,
        suggestion: WritingSuggestionOutput | None = None,
    ) -> None:
        self.initial = initial
        self.suggestion = suggestion
        self.draft_calls: list[dict] = []
        self.suggestion_calls: list[dict] = []

    async def draft_posting(self, *, details: dict) -> InitialPostingDraftOutput:
        self.draft_calls.append(details)
        if self.initial is None:
            raise AssertionError("No initial draft was configured")
        return self.initial

    async def suggest_writing(self, **arguments) -> WritingSuggestionOutput:
        self.suggestion_calls.append(arguments)
        if self.suggestion is None:
            raise AssertionError("No writing suggestion was configured")
        return self.suggestion


async def test_initial_draft_is_typed_and_not_saved(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    fake = FakeWritingGateway(
        initial=InitialPostingDraftOutput(
            suggested_content=(
                "Software Engineer\n\nBuild reliable services for a growing learning platform."
            )
        )
    )
    monkeypatch.setattr(writing_endpoints, "OpenAIGateway", lambda _settings: fake)

    response = await api_client.post(
        "/api/v1/writing-assistance/drafts",
        json={
            "title": "Software Engineer",
            "role_ideas": "Build reliable services and help teammates learn.",
            "organization_name": "Example Learning",
            "target_locations": ["New York"],
            "employment_type": "full_time",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"suggested_content": fake.initial.suggested_content}
    assert fake.draft_calls == [
        {
            "title": "Software Engineer",
            "role_ideas": "Build reliable services and help teammates learn.",
            "organization_name": "Example Learning",
            "target_locations": ["New York"],
            "employment_type": "full_time",
        }
    ]
    assert await db.scalar(select(func.count()).select_from(JobPosting)) == 0
    assert await db.scalar(select(func.count()).select_from(ComplianceSession)) == 0


async def test_initial_draft_returns_controlled_model_errors(
    api_client: httpx.AsyncClient,
    monkeypatch,
) -> None:
    class MissingGateway:
        def __init__(self, _settings) -> None:
            raise MissingAIConfigurationError("OPENAI_API_KEY is required")

    monkeypatch.setattr(writing_endpoints, "OpenAIGateway", MissingGateway)
    response = await api_client.post(
        "/api/v1/writing-assistance/drafts",
        json={"title": "Engineer", "role_ideas": "Build dependable software services."},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENAI_API_KEY is required"


async def test_create_and_save_do_not_call_openai_or_queue_work(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    monkeypatch.setattr(session_endpoints, "OpenAIGateway", UnexpectedGateway)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    first = created.json()["current_posting_version"]

    saved = await api_client.post(
        f"/api/v1/compliance-sessions/{created.json()['id']}/posting-versions",
        json={
            "base_version_id": first["id"],
            "content": "Build dependable Python services for our learning platform and customers.",
        },
    )

    assert created.status_code == 201
    assert created.json()["status"] == ComplianceSessionStatus.DRAFT.value
    assert created.json()["policy_snapshot_version"] is None
    assert saved.status_code == 201
    payload = saved.json()
    assert payload["status"] == ComplianceSessionStatus.DRAFT.value
    assert payload["current_posting_version"]["version"] == 2
    assert payload["current_posting_version"]["source"] == "recruiter"
    assert [version["content"] for version in payload["posting_versions"]] == [
        SESSION_REQUEST["job_description"],
        "Build dependable Python services for our learning platform and customers.",
    ]
    assert payload["steps"][-1]["kind"] == "user_edit"
    assert await session_repository.claim_next_queued_session(db) is None


async def test_save_rejects_stale_and_unchanged_drafts(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    base_id = payload["current_posting_version"]["id"]
    changed_text = "Build dependable services for our learning platform and customers worldwide."

    unchanged = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/posting-versions",
        json={"base_version_id": base_id, "content": SESSION_REQUEST["job_description"]},
    )
    first_save = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/posting-versions",
        json={"base_version_id": base_id, "content": changed_text},
    )
    stale_save = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/posting-versions",
        json={"base_version_id": base_id, "content": f"{changed_text} Additional stale edit."},
    )

    assert unchanged.status_code == 409
    assert unchanged.json()["detail"] == "The saved draft is unchanged"
    assert first_save.status_code == 201
    assert stale_save.status_code == 409
    assert stale_save.json()["detail"] == "The posting changed after this draft was loaded"
    versions = await db.scalars(select(PostingVersion))
    assert len(list(versions)) == 2


async def test_writing_suggestion_is_a_preview_and_can_limit_changes_to_a_selection(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    draft_text = payload["current_posting_version"]["content"]
    selection = "reliable Python services"
    selection_start = draft_text.index(selection)
    selection_end = selection_start + len(selection)
    fake = FakeWritingGateway(
        suggestion=WritingSuggestionOutput(
            suggested_text="dependable Python services",
            summary="Used clearer wording.",
        )
    )
    monkeypatch.setattr(session_endpoints, "OpenAIGateway", lambda _settings: fake)

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/writing-suggestions",
        json={
            "base_version_id": payload["current_posting_version"]["id"],
            "draft_text": draft_text,
            "instruction": "Make this phrase clearer.",
            "selection_start": selection_start,
            "selection_end": selection_end,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "base_version_id": payload["current_posting_version"]["id"],
        "suggested_text": draft_text.replace(selection, "dependable Python services"),
        "summary": "Used clearer wording.",
    }
    assert fake.suggestion_calls == [
        {
            "draft_text": draft_text,
            "instruction": "Make this phrase clearer.",
            "selection_start": selection_start,
            "selection_end": selection_end,
        }
    ]
    stored = await session_repository.get_session(db, payload["id"])
    assert stored.status == ComplianceSessionStatus.DRAFT.value
    assert stored.current_posting_version_id == payload["current_posting_version"]["id"]
    assert len(stored.posting.versions) == 1


async def test_writing_suggestion_rechecks_the_base_after_the_model_call(
    api_client: httpx.AsyncClient,
    monkeypatch,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    fake = FakeWritingGateway(
        suggestion=WritingSuggestionOutput(
            suggested_text="Build clear and dependable services for a learning platform.",
            summary="Made the draft concise.",
        )
    )
    monkeypatch.setattr(session_endpoints, "OpenAIGateway", lambda _settings: fake)
    validation_calls = 0

    async def changing_base(_db, _session_id: str, _base_version_id: str) -> None:
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 2:
            raise ValueError("The posting changed after this draft was loaded")

    monkeypatch.setattr(session_endpoints.repository, "validate_writing_base", changing_base)

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/writing-suggestions",
        json={
            "base_version_id": payload["current_posting_version"]["id"],
            "draft_text": payload["current_posting_version"]["content"],
            "instruction": "Make this concise.",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "The posting changed after this draft was loaded"
    assert validation_calls == 2
    assert len(fake.suggestion_calls) == 1


async def test_check_is_explicit_and_keeps_the_first_pinned_snapshot(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()

    first_check = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/check",
        json={"base_version_id": payload["current_posting_version"]["id"]},
    )
    first_snapshot_version = first_check.json()["policy_snapshot_version"]
    stored = await session_repository.get_session(db, payload["id"])
    first_started_at = stored.started_at
    stored.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
    await db.commit()

    saved = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/posting-versions",
        json={
            "base_version_id": payload["current_posting_version"]["id"],
            "content": "Build reliable services for customers and support engineering teammates.",
        },
    )
    await create_and_publish_policy(
        api_client,
        monkeypatch,
        policy_request={**POLICY_REQUEST, "key": "GLOBAL_ACCURACY_002"},
    )
    second_check = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/check",
        json={"base_version_id": saved.json()["current_posting_version"]["id"]},
    )

    assert first_check.status_code == 202
    assert first_snapshot_version == 1
    assert saved.status_code == 201
    assert saved.json()["status"] == ComplianceSessionStatus.DRAFT.value
    assert saved.json()["policy_snapshot_version"] == first_snapshot_version
    assert second_check.status_code == 202
    assert second_check.json()["policy_snapshot_version"] == first_snapshot_version
    refreshed = await session_repository.get_session(db, payload["id"])
    assert refreshed.started_at == first_started_at


async def test_check_requires_a_current_base_and_a_published_policy(
    api_client: httpx.AsyncClient,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()

    missing_policy = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/check",
        json={"base_version_id": payload["current_posting_version"]["id"]},
    )
    stale = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/check",
        json={"base_version_id": "stale-version"},
    )

    assert missing_policy.status_code == 409
    assert missing_policy.json()["detail"] == (
        "Publish at least one policy before starting a compliance check"
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "The posting changed after this draft was loaded"


async def test_failed_check_can_retry_the_same_saved_version(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    session = await session_repository.get_session(db, payload["id"])
    session.status = ComplianceSessionStatus.FAILED.value
    session.error_message = "The provider was temporarily unavailable."
    await db.commit()

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/check",
        json={"base_version_id": payload["current_posting_version"]["id"]},
    )

    assert response.status_code == 202
    assert response.json()["status"] == ComplianceSessionStatus.QUEUED.value
    assert response.json()["error_message"] is None
    assert response.json()["check_state"] == "running"


async def test_check_state_marks_results_from_an_older_version_as_stale(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    version_id = payload["current_posting_version"]["id"]
    assert payload["check_state"] == "never_run"

    await session_repository.add_step(
        db,
        payload["id"],
        kind="compliance_check",
        name="Checked all applicable policies",
        input_data={"posting_version": 1, "posting_version_id": version_id},
    )
    await db.commit()
    current = await api_client.get(f"/api/v1/compliance-sessions/{payload['id']}")
    assert current.json()["check_state"] == "current"

    saved = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/posting-versions",
        json={
            "base_version_id": version_id,
            "content": "Build reliable services, mentor teammates, and support our customers.",
        },
    )

    assert saved.status_code == 201
    assert saved.json()["check_state"] == "stale"
    assert saved.json()["last_checked_posting_version_id"] == version_id


async def test_stale_answer_cannot_queue_a_newer_posting_version(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    original_version_id = payload["current_posting_version"]["id"]
    session = await session_repository.get_session(db, payload["id"])
    session.status = ComplianceSessionStatus.WAITING_FOR_INFORMATION.value
    session.current_question = "Which location should be used?"
    await db.commit()
    saved = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/posting-versions",
        json={
            "base_version_id": original_version_id,
            "content": "Build reliable services from our New York office and mentor teammates.",
        },
    )

    stale_answer = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/messages",
        json={"base_version_id": original_version_id, "message": "Use New York."},
    )

    assert stale_answer.status_code == 409
    refreshed = await session_repository.get_session(db, payload["id"])
    await db.refresh(refreshed)
    assert refreshed.status == ComplianceSessionStatus.DRAFT.value
    assert refreshed.current_posting_version_id == saved.json()["current_posting_version"]["id"]


async def test_publish_reloads_the_session_before_changing_status(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    original_version_id = payload["current_posting_version"]["id"]
    stale_session = await session_repository.get_session(db, payload["id"])
    stale_session.status = ComplianceSessionStatus.READY_TO_PUBLISH.value
    await db.commit()

    async with session_factory() as other_db:
        saved = await session_repository.create_user_posting_version(
            other_db,
            payload["id"],
            base_version_id=original_version_id,
            content="Build reliable services, work with customers, and mentor teammates.",
        )

    try:
        await session_repository.publish_posting(
            db,
            payload["id"],
            base_version_id=original_version_id,
            publisher_name="Test recruiter",
        )
    except ValueError as error:
        assert str(error) == "Only a ready posting can be published"
    else:
        raise AssertionError("A stale session was published")

    refreshed = await session_repository.get_session(db, payload["id"])
    assert refreshed.status == ComplianceSessionStatus.DRAFT.value
    assert refreshed.current_posting_version_id == saved.current_posting_version_id


async def test_long_full_draft_requires_a_selected_passage(
    api_client: httpx.AsyncClient,
    monkeypatch,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    monkeypatch.setattr(session_endpoints, "OpenAIGateway", UnexpectedGateway)

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/writing-suggestions",
        json={
            "base_version_id": payload["current_posting_version"]["id"],
            "draft_text": "A" * 12_001,
            "instruction": "Make this clearer.",
        },
    )

    assert response.status_code == 422


async def test_selected_writing_help_uses_unicode_character_offsets(
    api_client: httpx.AsyncClient,
    monkeypatch,
) -> None:
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    draft_text = "Join our team 🚀 and build reliable Python services for learners."
    selected_text = "reliable Python services"
    selection_start = draft_text.index(selected_text)
    selection_end = selection_start + len(selected_text)
    fake = FakeWritingGateway(
        suggestion=WritingSuggestionOutput(
            suggested_text="dependable Python services",
            summary="Used clearer wording.",
        )
    )
    monkeypatch.setattr(session_endpoints, "OpenAIGateway", lambda _settings: fake)

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/writing-suggestions",
        json={
            "base_version_id": payload["current_posting_version"]["id"],
            "draft_text": draft_text,
            "instruction": "Make this clearer.",
            "selection_start": selection_start,
            "selection_end": selection_end,
        },
    )

    assert response.status_code == 200
    assert response.json()["suggested_text"] == draft_text.replace(
        selected_text, "dependable Python services"
    )


async def test_revision_rejection_note_is_sent_back_to_the_agent(
    api_client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch,
) -> None:
    await create_and_publish_policy(api_client, monkeypatch)
    created = await api_client.post("/api/v1/compliance-sessions", json=SESSION_REQUEST)
    payload = created.json()
    await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/check",
        json={"base_version_id": payload["current_posting_version"]["id"]},
    )
    session = await session_repository.get_session(db, payload["id"])
    proposed = await session_repository.create_proposed_revision(
        db,
        session,
        ProposedRevision(
            revised_text=SESSION_REQUEST["job_description"].replace("reliable", "dependable"),
            changes=[
                ProposedEdit(
                    original_text="reliable",
                    replacement_text="dependable",
                    reason="Use more direct wording.",
                    policy_keys=[POLICY_REQUEST["key"]],
                )
            ],
        ),
    )

    response = await api_client.post(
        f"/api/v1/compliance-sessions/{payload['id']}/approve",
        json={
            "base_version_id": proposed.id,
            "approved": False,
            "reviewer_name": "Test recruiter",
            "notes": "Keep the original wording and shorten the final sentence.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == ComplianceSessionStatus.QUEUED.value
    assert (
        response.json()["current_posting_version"]["id"] == payload["current_posting_version"]["id"]
    )
    assert response.json()["steps"][-1]["input_data"] == {
        "message": "Keep the original wording and shorten the final sentence."
    }
