from app.agent import worker as worker_module
from app.agent.worker import AgentWorker
from app.core.config import Settings


class FakeDatabaseContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return None


async def test_each_worker_iteration_recovers_stale_sessions(monkeypatch) -> None:
    recovery_calls: list[int] = []

    async def recover_stale_sessions(_db, stale_after_seconds: int) -> int:
        recovery_calls.append(stale_after_seconds)
        return 0

    async def claim_next_queued_session(_db):
        return None

    monkeypatch.setattr(worker_module, "SessionFactory", FakeDatabaseContext)
    monkeypatch.setattr(
        worker_module.session_repository,
        "recover_stale_sessions",
        recover_stale_sessions,
    )
    monkeypatch.setattr(
        worker_module.session_repository,
        "claim_next_queued_session",
        claim_next_queued_session,
    )
    worker = AgentWorker(
        Settings(
            database_url="sqlite+aiosqlite://",
            chroma_mode="disabled",
            run_agent_worker=False,
            agent_stale_after_seconds=45,
        )
    )

    assert await worker.run_once() is False
    assert await worker.run_once() is False
    assert recovery_calls == [45, 45]
