# Policy Checker API

A FastAPI-based service for checking job postings against policy violations.

## Features

- Job posting verification
- Security checks for prompt injection
- Policy violation detection
- Parallel policy investigations
- Structured output with confidence scores

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

3. Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Running the API

Start the API server:
```bash
cd app
uvicorn main:app --reload
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
│   └── prompts.py
├── data/
│   └── sample_policies.json
├── models/
├── schemas/
│   └── policy.py
├── services/
│   └── policy_checker.py
└── main.py
```

## Development

- The API is built with FastAPI
- Uses Pydantic for data validation
- OpenAI's GPT-4 for policy checking
- Async/await for parallel processing 