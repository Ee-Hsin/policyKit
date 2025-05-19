# PolicyKit

A FastAPI-based service for checking job postings against policy violations, with database-backed policy management.

## Features

- Job posting verification with confidence scoring
- Security checks for prompt injection
- Policy violation detection with parallel processing
- Category-based policy investigation
- Structured output with confidence scores
- Database-backed policy management
- Async database operations
- Parallel policy investigations with timeout handling

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your configuration:
```
OPENAI_API_KEY=your_api_key_here
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=policykit
```

4. Set up the database:
```bash
# Create the database
createdb policykit

# Run migrations
alembic upgrade head
```

## Policy Structure

The system uses a hierarchical structure for policies:

1. **Policy Categories**: Top-level groupings of related policies
   - Each category has a name, ID, and description
   - Categories are used to organize policies by type (e.g., "Discrimination", "Legal", "Compensation")
   - Categories are scored for relevance to the job posting

2. **Policies**: Individual rules within each category
   - Each policy has a title, description, and ID
   - Policies can have additional metadata in JSON format
   - Policies are linked to their parent category
   - Policies can include examples of violations

### Example Policy Structure

```python
# Example category
discrimination_category = {
    "name": "Discrimination",
    "description": "Policies related to discrimination, bias, and equal opportunity",
    "policies": [
        {
            "title": "No Age Discrimination",
            "description": "Job postings must not discriminate based on age",
            "extra_metadata": {
                "examples": ["must be under 30", "recent graduate only"]
            }
        },
        {
            "title": "No Gender Discrimination",
            "description": "Job postings must not discriminate based on gender",
            "extra_metadata": {
                "examples": ["male candidates only", "female preferred"]
            }
        }
    ]
}
```

### Populating the Database

You can populate the database with policies using SQLAlchemy. Here's an example script:

```python
from app.core.database import async_session_factory
from app.models.policy import PolicyCategory, Policy

async def populate_policies():
    async with async_session_factory() as session:
        # Create a category
        discrimination = PolicyCategory(
            name="Discrimination",
            description="Policies related to discrimination, bias, and equal opportunity"
        )
        session.add(discrimination)
        await session.flush()  # Get the category ID

        # Add policies to the category
        policies = [
            Policy(
                category_id=discrimination.id,
                title="No Age Discrimination",
                description="Job postings must not discriminate based on age",
                extra_metadata={
                    "examples": ["must be under 30", "recent graduate only"]
                }
            ),
            Policy(
                category_id=discrimination.id,
                title="No Gender Discrimination",
                description="Job postings must not discriminate based on gender",
                extra_metadata={
                    "examples": ["male candidates only", "female preferred"]
                }
            )
        ]
        session.add_all(policies)
        await session.commit()

# Run the population script
import asyncio
asyncio.run(populate_policies())
```

Save this script as `scripts/populate_policies.py` and run it after setting up your database:

```bash
python scripts/populate_policies.py
```

## Running the API

Start the API server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### POST /api/v1/check-posting
Check a job posting for policy violations.

Request body:
```json
{
    "job_description": "string",
    "image_path": "string (optional)"
}
```

Response:
```json
{
    "has_violations": boolean,
    "violations": [
        {
            "category": "string",
            "policy": ["string"],
            "reasoning": "string",
            "content": "string"
        }
    ]
}
```

### GET /api/v1/health
Health check endpoint.

## Project Structure

```
app/
├── api/
│   └── v1/
│       └── endpoints/
│           └── policy_checker.py
├── core/
│   ├── config.py
│   ├── database.py
│   └── prompts.py
├── models/
│   └── policy.py
├── schemas/
│   └── policy.py
├── services/
│   └── policy_checker.py
├── migrations/
│   └── versions/
└── main.py
```

## Development

- The API is built with FastAPI
- Uses Pydantic for data validation
- OpenAI's GPT-4 for policy checking
- Async/await for parallel processing
- SQLAlchemy for database operations
- Alembic for database migrations

## Configuration Settings

Key configuration settings in `.env`:
- `JOB_POSTING_CONFIDENCE_THRESHOLD`: 0.9 (Confidence required to reject non-job postings)
- `POLICY_INVESTIGATION_CONFIDENCE_THRESHOLD`: 0.7 (Minimum confidence to investigate a category)
- `FINAL_OUTPUT_CONFIDENCE_THRESHOLD`: 0.85 (Minimum confidence to report a violation)
- `MAX_PARALLEL_INVESTIGATIONS`: 3 (Maximum number of parallel category investigations)
- `LLM_INVESTIGATION_TIMEOUT`: 30 (Timeout in seconds for LLM investigations)

## Testing

Run the tests:
```bash
pytest tests/
```

The test suite includes:
- API endpoint tests
- Policy violation detection tests
- Database integration tests 