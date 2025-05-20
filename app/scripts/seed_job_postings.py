"""Script to seed example job postings with embeddings."""

import asyncio
from app.core.database import async_session_factory
from app.models.job_posting import JobPostingEmbedding
from app.services.embedding_service import EmbeddingService
from app.schemas.policy import StandardViolation, SafetyKitViolation

# Example job postings
EXAMPLE_POSTINGS = [
    {
        "job_description": "Looking for a young, energetic female candidate to join our team. Must be under 30 years old.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Discrimination",
                policy=["No Gender Discrimination"],
                reasoning="Job posting specifies gender requirement",
                content="Looking for a young, energetic female candidate"
            ),
            StandardViolation(
                category="Discrimination",
                policy=["No Age Discrimination"],
                reasoning="Job posting specifies age requirement",
                content="Must be under 30 years old"
            )
        ]
    },
    {
        "job_description": "Seeking a courier for controlled substances. Must be discreet and reliable.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Legal Compliance",
                policy=["No Drugs or Illegal Activities"],
                reasoning="Job posting solicits illegal drug-related activities",
                content="Seeking a courier for controlled substances"
            )
        ]
    },
    {
        "job_description": "Join our team as a software developer. Competitive salary above minimum wage, flexible hours, and great benefits.",
        "has_violations": False,
        "violations": []
    },
    {
        "job_description": "Looking for someone to download and share movies illegally. Must have fast internet.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Legal Compliance",
                policy=["No Copyright Infringement"],
                reasoning="Job posting solicits copyright infringement",
                content="Looking for someone to download and share movies illegally"
            )
        ]
    },
    {
        "job_description": "Seeking a candidate to prepare academic papers for students. Must be detail-oriented.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Legal Compliance",
                policy=["No Academic Misconduct"],
                reasoning="Job posting solicits academic misconduct",
                content="Seeking a candidate to prepare academic papers for students"
            )
        ]
    },
    {
        "job_description": "Send me your bank account details and I'll pay you $1000 per week. No experience needed.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Privacy and Security",
                policy=["Data Protection"],
                reasoning="Job posting requests sensitive financial information",
                content="Send me your bank account details"
            )
        ]
    },
    {
        "job_description": "Looking for a white male programmer. Must be between 25-35 years old. No women or minorities need apply.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Discrimination",
                policy=["No Race Discrimination", "No Gender Discrimination"],
                reasoning="Job posting explicitly discriminates based on race and gender",
                content="Looking for a white male programmer. No women or minorities need apply"
            ),
            StandardViolation(
                category="Discrimination",
                policy=["No Age Discrimination"],
                reasoning="Job posting specifies age requirement",
                content="Must be between 25-35 years old"
            )
        ]
    },
    {
        "job_description": "Need someone to help with my homework. Will pay $50 per assignment. Must be good at math and science.",
        "has_violations": True,
        "violations": [
            StandardViolation(
                category="Legal Compliance",
                policy=["No Academic Misconduct"],
                reasoning="Job posting solicits academic cheating",
                content="Need someone to help with my homework. Will pay $50 per assignment"
            )
        ]
    }
]

async def seed_database():
    """Seed the database with example job postings and their embeddings."""
    async with async_session_factory() as session:
        embedding_service = EmbeddingService(db=session)
        for posting in EXAMPLE_POSTINGS:
            # Generate embedding for the job description
            embedding = await embedding_service.get_embedding(posting["job_description"])
            # Create a new job posting embedding
            job_posting = JobPostingEmbedding(
                job_description=posting["job_description"],
                embedding=embedding,
                has_violations=posting["has_violations"],
                violations=[v.dict() for v in posting["violations"]] if posting["violations"] else None
            )
            session.add(job_posting)
            print(f"Added job posting: {posting['job_description'][:50]}...")
        await session.commit()

if __name__ == "__main__":
    asyncio.run(seed_database()) 