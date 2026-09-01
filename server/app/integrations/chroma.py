"""ChromaDB indexes for policies and reviewed precedents."""

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.api import ClientAPI

from app.core.config import Settings
from app.integrations.openai_gateway import AIGateway
from app.models.entities import PolicyVersion, ReviewedPrecedent


@dataclass
class SemanticMatch:
    record_id: str
    text: str
    distance: float | None
    metadata: dict[str, Any]


class ChromaIndex:
    def __init__(self, settings: Settings, ai: AIGateway):
        self.settings = settings
        self.ai = ai
        self._client: ClientAPI | None = None

    def _get_client(self) -> ClientAPI:
        if self._client is not None:
            return self._client
        if self.settings.chroma_mode == "persistent":
            self.settings.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.settings.chroma_persist_directory)
            )
        elif self.settings.chroma_mode == "http":
            headers = (
                {"x-chroma-token": self.settings.chroma_api_key}
                if self.settings.chroma_api_key
                else None
            )
            self._client = chromadb.HttpClient(
                host=self.settings.chroma_host,
                port=self.settings.chroma_port,
                ssl=self.settings.chroma_ssl,
                headers=headers,
                tenant=self.settings.chroma_tenant or "default_tenant",
                database=self.settings.chroma_database or "default_database",
            )
        else:
            raise RuntimeError("ChromaDB is disabled")
        return self._client

    def _collection(self, name: str):
        return self._get_client().get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    async def index_policy(self, version: PolicyVersion) -> None:
        text = "\n".join(
            part
            for part in [
                version.policy.title,
                version.rule_text,
                "Violation examples: " + " | ".join(version.violation_examples),
                "Compliant examples: " + " | ".join(version.compliant_examples),
                "Exceptions: " + " | ".join(version.exceptions),
            ]
            if part and not part.endswith(": ")
        )
        embedding = (await self.ai.embed([text]))[0]
        self._collection("policy_chunks").upsert(
            ids=[version.id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[
                {
                    "policy_id": version.policy_id,
                    "policy_key": version.policy.key,
                    "policy_version_id": version.id,
                    "version": version.version,
                    "category": version.policy.category,
                    "jurisdictions": ",".join(version.jurisdictions),
                }
            ],
        )

    async def index_precedent(self, precedent: ReviewedPrecedent) -> None:
        embedding = (await self.ai.embed([precedent.excerpt]))[0]
        self._collection("reviewed_precedents").upsert(
            ids=[precedent.id],
            documents=[precedent.excerpt],
            embeddings=[embedding],
            metadatas=[
                {
                    "policy_version_id": precedent.policy_version_id,
                    "decision": precedent.decision,
                    "jurisdiction": precedent.jurisdiction,
                    "category": precedent.category,
                }
            ],
        )

    async def search(
        self,
        collection_name: str,
        query: str,
        *,
        limit: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[SemanticMatch]:
        embedding = (await self.ai.embed([query]))[0]
        result = self._collection(collection_name).query(
            query_embeddings=[embedding],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            SemanticMatch(
                record_id=record_id,
                text=documents[index] or "",
                metadata=metadatas[index] or {},
                distance=distances[index],
            )
            for index, record_id in enumerate(ids)
        ]
