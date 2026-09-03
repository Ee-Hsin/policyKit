"""PolicyKit FastAPI application."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.worker import AgentWorker
from app.api.v1.router import router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        worker = AgentWorker(app_settings)
        worker_task: asyncio.Task | None = None
        if app_settings.run_agent_worker:
            worker_task = asyncio.create_task(worker.run_forever())
        app.state.settings = app_settings
        app.state.agent_worker = worker
        yield
        worker.stop()
        if worker_task:
            await worker_task

    application = FastAPI(
        title=app_settings.app_name,
        description="Pre-publication job-posting compliance agent",
        version="2.0.0",
        openapi_url=f"{app_settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix=app_settings.api_v1_prefix)
    return application


app = create_app()
