"""Background worker that claims durable queued compliance sessions."""

import asyncio
import logging

from app.agent.runtime import ComplianceAgent
from app.core.config import Settings
from app.core.database import SessionFactory
from app.integrations.chroma import ChromaIndex
from app.integrations.openai_gateway import OpenAIGateway
from app.models.entities import ComplianceSessionStatus, StepStatus
from app.repositories import sessions as session_repository

logger = logging.getLogger(__name__)


class AgentWorker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                worked = await self.run_once()
            except Exception:
                logger.exception("Agent worker iteration failed")
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.settings.agent_poll_interval_seconds
                    )
                except TimeoutError:
                    pass

    async def run_once(self) -> bool:
        async with SessionFactory() as db:
            recovered = await session_repository.recover_stale_sessions(
                db, self.settings.agent_stale_after_seconds
            )
            if recovered:
                logger.info("Recovered %s interrupted compliance sessions", recovered)
            session = await session_repository.claim_next_queued_session(db)
            if not session:
                return False
            try:
                ai = OpenAIGateway(self.settings)
                agent = ComplianceAgent(self.settings, ai, ChromaIndex(self.settings, ai))
                await agent.run(db, session.id)
            except Exception as error:
                logger.exception("Compliance agent failed for session %s", session.id)
                await db.rollback()
                session = await session_repository.get_session(db, session.id)
                session.status = ComplianceSessionStatus.FAILED.value
                session.error_message = str(error)
                await session_repository.add_step(
                    db,
                    session.id,
                    kind="system",
                    name="Agent run failed",
                    output_data={"error": str(error)},
                    status=StepStatus.FAILED.value,
                )
                await db.commit()
            return True
