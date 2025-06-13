"""Vector store implementation using Chroma."""

import chromadb
from chromadb.config import Settings
from typing import List, Optional, Tuple, Dict, Any
import os
from pathlib import Path
import json
import uuid

class ChromaVectorStore:
    """Vector store implementation using Chroma."""
    
    def __init__(self, persist_directory: str = ".chroma"):
        """Initialize the vector store.
        
        Args:
            persist_directory: Directory to persist the Chroma database
        """
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Create or get the collection
        self.collection = self.client.get_or_create_collection(
            name="job_postings",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
    
    async def add_job_posting(self, job_description: str, embedding: List[float], has_violations: bool, violations: Optional[List[Dict]] = None) -> None:
        """Add a job posting to the vector store."""
        # Convert violations to a JSON string, defaulting to empty list if None
        violations_str = json.dumps(violations) if violations else "[]"
        
        # Add to Chroma collection
        self.collection.add(
            ids=[str(uuid.uuid4())],  # Generate a random UUID for the ID
            embeddings=[embedding],
            documents=[job_description],
            metadatas=[{
                "has_violations": has_violations,
                "violations": violations_str
            }]
        )
    
    async def find_similar_job_postings(
        self,
        embedding: List[float],
        threshold: float = 0.98,
        limit: int = 1
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """Find similar job postings using vector similarity.
        
        Args:
            embedding: The embedding vector to compare against
            threshold: Similarity threshold (0-1)
            limit: Maximum number of results to return
            
        Returns:
            Tuple of (job posting metadata, similarity score) if found, None otherwise
        """
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            include=["metadatas", "distances"]
        )
        
        # Check if we have any results
        if not results["ids"] or not results["ids"][0]:
            return None
            
        # Get the first result's data
        distance = results["distances"][0][0]
        metadata = results["metadatas"][0][0]
        
        # Parse violations back from JSON string if present
        if metadata.get("violations"):
            metadata["violations"] = json.loads(metadata["violations"])
        
        # Convert distance to similarity score (Chroma uses L2 distance)
        # We'll convert it to a similarity score between 0 and 1
        similarity = 1 / (1 + distance)  # Convert distance to similarity
        
        if similarity < threshold:
            return None
            
        return metadata, similarity
    
    def reset(self):
        """Reset the vector store."""
        self.client.reset() 