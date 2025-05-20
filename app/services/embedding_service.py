"""Service for handling embeddings and similarity search."""

from typing import List, Optional, Tuple
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import array
from app.core.config import settings
from app.models.job_posting import JobPostingEmbedding
from app.schemas.policy import FinalOutput

class EmbeddingService:
    def __init__(self, db: AsyncSession, api_key: Optional[str] = None):
        self.db = db
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text using OpenAI's API."""
        response = await self.client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text
        )
        
        return response.data[0].embedding
    
    async def find_similar_job_postings(self, embedding: List[float], threshold: float) -> Optional[Tuple[JobPostingEmbedding, float]]:
        """
        Find similar job postings using cosine similarity.
        Returns the most similar job posting and its similarity score if above threshold.
        """
        
        print("before query")
            
        # Using cosine similarity with pgvector
        query = select(
            JobPostingEmbedding,
            (1 - JobPostingEmbedding.embedding.cosine_distance(embedding)).label('similarity')
        ).order_by(
            JobPostingEmbedding.embedding.cosine_distance(embedding)
        ).limit(1)
        
        print("after query")
        
        # print("query: ", query)
        
        result = await self.db.execute(query)
        
        print("result: ", result)
        row = result.first()
        
        print("row: ", row)
        
        if row and row.similarity >= threshold:
            print("row similarity: ", row.similarity)
            job_posting = row[0]
            job_posting.similarity_score = row.similarity
            return job_posting, row.similarity
            
        return None
    
    async def store_job_posting(self, job_description: str, has_violations: bool, violations: Optional[List[dict]] = None) -> JobPostingEmbedding:
        """Store a new job posting with its embedding and policy check results."""
        embedding = await self.get_embedding(job_description)
        
        job_posting = JobPostingEmbedding(
            job_description=job_description,
            embedding=embedding,
            has_violations=has_violations,
            violations=violations
        )
        
        self.db.add(job_posting)
        await self.db.commit()
        await self.db.refresh(job_posting)
        
        return job_posting
    
    def convert_to_final_output(self, job_posting: JobPostingEmbedding) -> FinalOutput:
        """Convert a JobPostingEmbedding to FinalOutput format."""
        
        print("job_posting: ", job_posting.has_violations)
        print("job_posting violations: ", job_posting.violations)
        return FinalOutput(
            has_violations=job_posting.has_violations,
            violations=job_posting.violations if job_posting.violations else []
        ) 