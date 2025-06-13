"""Job posting model with vector embeddings."""

from sqlalchemy import Column, Integer, String, Float, JSON, Boolean
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class JobPostingEmbedding(Base):
    """Model for storing job posting embeddings and their policy check results."""
    
    __tablename__ = "job_posting_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    job_description = Column(String, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # Vector embedding of the job description
    has_violations = Column(Boolean, nullable=False)
    violations = Column(JSON, nullable=True)  # Store the violations as JSON
    similarity_score = Column(Float, nullable=True)  # For storing similarity scores during search
    
    def __repr__(self):
        return f"<JobPostingEmbedding(id={self.id}, has_violations={self.has_violations})>" 