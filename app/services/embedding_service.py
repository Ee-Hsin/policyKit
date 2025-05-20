"""Service for handling embeddings and similarity search."""

from typing import List, Optional, Tuple, Dict, Any
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.schemas.policy import FinalOutput
from app.core.vector_store import ChromaVectorStore

class EmbeddingService:
    def __init__(self, db: AsyncSession, api_key: Optional[str] = None):
        self.db = db
        self.client = AsyncOpenAI(api_key=api_key)
        self.vector_store = ChromaVectorStore()
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text using OpenAI's API."""
        response = await self.client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text
        )
        
        return response.data[0].embedding
    
    async def find_similar_job_postings(self, embedding: List[float], threshold: float) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Find similar job postings using vector similarity.
        Returns the most similar job posting and its similarity score if above threshold.
        """
        return await self.vector_store.find_similar_job_postings(embedding, threshold)
    
    async def store_job_posting(self, job_description: str, has_violations: bool, violations: Optional[List[dict]] = None) -> str:
        """Store a new job posting with its embedding and policy check results."""
        embedding = await self.get_embedding(job_description)
        return await self.vector_store.add_job_posting(
            job_description=job_description,
            embedding=embedding,
            has_violations=has_violations,
            violations=violations
        )
    
    def convert_to_final_output(self, job_posting: Dict[str, Any]) -> FinalOutput:
        """Convert a job posting from the vector store to a FinalOutput."""
        return FinalOutput(
            has_violations=job_posting["has_violations"],
            violations=job_posting["violations"]
        ) 