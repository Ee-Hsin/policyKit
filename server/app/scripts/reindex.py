"""Rebuild Chroma indexes from the current PostgreSQL source of truth."""

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.integrations.chroma import ChromaIndex
from app.integrations.openai_gateway import OpenAIGateway
from app.models.entities import IndexStatus, PolicyStatus, PolicyVersion, ReviewedPrecedent


async def rebuild_indexes() -> None:
    settings = get_settings()
    ai = OpenAIGateway(settings)
    index = ChromaIndex(settings, ai)
    indexed_policies = 0
    indexed_precedents = 0
    failed = 0

    async with SessionFactory() as db:
        policies = list(
            await db.scalars(
                select(PolicyVersion)
                .where(PolicyVersion.status == PolicyStatus.PUBLISHED.value)
                .options(selectinload(PolicyVersion.policy))
            )
        )
        precedents = list(await db.scalars(select(ReviewedPrecedent)))
        for version in policies:
            try:
                await index.index_policy(version)
                version.index_status = IndexStatus.INDEXED.value
                indexed_policies += 1
            except Exception:
                version.index_status = IndexStatus.FAILED.value
                failed += 1
        for precedent in precedents:
            try:
                await index.index_precedent(precedent)
                precedent.index_status = IndexStatus.INDEXED.value
                indexed_precedents += 1
            except Exception:
                precedent.index_status = IndexStatus.FAILED.value
                failed += 1
        await db.commit()

    print(
        f"Indexed {indexed_policies} policies and {indexed_precedents} precedents; "
        f"{failed} records failed."
    )


if __name__ == "__main__":
    asyncio.run(rebuild_indexes())
