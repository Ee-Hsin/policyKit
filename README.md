# PolicyKit

A modern, AI-powered job posting policy checker with Retrieval-Augmented Generation (RAG), vector search, and robust policy violation detection.

## Features
- **Policy Violation Detection**: Checks job postings for discrimination, legal, privacy, and academic misconduct violations.
- **Retrieval-Augmented Generation (RAG)**: Uses vector embeddings to find and reuse results from similar job postings for efficiency and consistency.
- **Vector Database**: Stores job posting embeddings in PostgreSQL with pgvector for fast similarity search.
- **Flexible Policy Schema**: Supports both `StandardViolation` and `SafetyKitViolation` types for nuanced violation reporting.
- **Async FastAPI Backend**: High-performance, async API for real-time job posting checks.
- **Seeding & Testing**: Includes scripts to seed the database with example job postings and policies.

## Setup

### 1. Install Dependencies
- Create and activate a Python virtual environment:
  ```sh
  python3 -m venv venv
  source venv/bin/activate
  ```
- Install Python dependencies:
  ```sh
  pip install -r requirements.txt
  ```
- Install PostgreSQL and [pgvector](https://github.com/pgvector/pgvector):
  ```sh
  brew install postgresql
  brew install pgvector
  ```

### 2. Database Setup
- Ensure PostgreSQL is running and create the database:
  ```sh
  createdb policykit
  ```
- Enable the vector extension and run migrations:
  ```sh
  psql policykit -c "CREATE EXTENSION IF NOT EXISTS vector;"
  alembic upgrade head
  ```

### 3. Seeding Example Data
- Seed the database with example job postings and embeddings:
  ```sh
  python -m app.scripts.seed_job_postings
  ```

## API Usage

### Check a Job Posting
Send a POST request to `/api/v1/check-posting`:
```sh
curl -X POST http://localhost:8000/api/v1/check-posting \
  -H "Content-Type: application/json" \
  -d '{"job_description": "Looking for a young, energetic female candidate to join our team. Must be under 30 years old."}'
```

#### Example Response
```json
{
  "has_violations": true,
  "violations": [
    {
      "category": "Discrimination",
      "policy": ["No Gender Discrimination", "No Age Discrimination"],
      "reasoning": "Job posting specifies gender and age requirements",
      "content": "Looking for a young, energetic female candidate to join our team. Must be under 30 years old."
    }
  ],
  "metadata": null
}
```

### Violation Types
- **StandardViolation**: Used for most policy violations (discrimination, legal, privacy, academic, etc.)
- **SafetyKitViolation**: Used for prompt injection, scam, or other safety-related issues

### RAG & Vector Search
- When a new job posting is checked, its embedding is generated and compared to existing embeddings in the database.
- If a similar posting is found (above a similarity threshold), its result is reused for efficiency.
- Otherwise, the posting is checked against all policies and the result is stored for future RAG.

## Extending Policies
- Add new policies and categories in the database.
- Update the seeding script (`app/scripts/seed_job_postings.py`) to add more edge cases or new violation types.

## Development & Testing
- Run tests with pytest:
  ```sh
  python -m pytest tests/api/test_policy_api.py -v -s
  ```
- Example test cases are provided for all major violation types and edge cases.

## Troubleshooting
- If you encounter errors related to missing fields or database issues, ensure migrations are up to date and the database is seeded.
- For vector search issues, verify that the `pgvector` extension is enabled and the `job_posting_embeddings` table exists.

## License
MIT 