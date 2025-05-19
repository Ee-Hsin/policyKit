# PolicyKit

A FastAPI-based service for checking job postings against policy violations, with database-backed policy management.

## Features

- Job posting verification
- Security checks for prompt injection
- Policy violation detection
- Parallel policy investigations
- Structured output with confidence scores
- Database-backed policy management
- Async database operations

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

## Testing

Run the tests:
```bash
pytest tests/
```

The test suite includes:
- API endpoint tests
- Policy violation detection tests
- Database integration tests 