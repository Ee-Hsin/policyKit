# PolicyKit

An AI-agent specializing in compliance to review job postings for policy violations. Using OpenAI's language models and vector search, PolicyKit acts as your intelligent compliance officer, ensuring job postings on your platform
meet all of your platform's policies while learning from previous reviews to improve efficiency.

## Features
- **AI Compliance Agent**: An intelligent system that understands and enforces complex policy requirements, detecting violations with high accuracy.
- **Retrieval-Augmented Generation (RAG)**: Uses vector embeddings to find and reuse results from similar job postings for efficiency and consistency. Successful classifications are embedded and added to the database for quicker classification in subsequent requests.
- **Vector Database**: Uses Chroma, a dedicated vector database, for efficient similarity search and storage of job posting embeddings.
- **Flexible Policy Schema**: Supports both `StandardViolation` and `SafetyKitViolation` types for nuanced violation reporting.
- **Async FastAPI Backend**: High-performance, async API for real-time job posting checks.
- **Seeding & Testing**: Includes scripts to seed the database with example job postings and policies.

## System Architecture

### AI Agent Design
The PolicyKit AI agent follows the following design:

<div style="display: flex; justify-content: space-between;">
    <img src="docs/images/Agent_Design_Left.png" alt="PolicyKit AI Agent Architecture - Left Side" style="width: 40%;""">
    <img src="docs/images/Agent_Design_right.png" alt="PolicyKit AI Agent Architecture - Right Side" style="width: 49%;""">
</div>

For a detailed, interactive view of the system architecture, you can open the [PolicyKit.drawio](PolicyKit.drawio) file in [draw.io](https://app.diagrams.net/)

# Design Choices Explanation

## 1. **Input Validation and Safety Checks**

I began by validating that the input is indeed a job posting and safe to process. This included checking for prompt injection or other potentially malicious input. I implemented a **gating mechanism** to enforce this safety, inspired by the gating design pattern:

> ![Gating Pattern](https://github.com/user-attachments/assets/afbefe68-c2eb-4240-9704-67ed504f6bc4)

FYI, this pattern is described in Anthropic’s article on [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents), which I have used as a building block for everything I've since learned about AI agents

---

## 2. **Using a Vector Database as a Semantic Cache**

I used **ChromaDB** as a vector database — not for traditional RAG in the usual sense, but as a **semantic cache**.

Initially, I considered using RAG to retrieve relevant policies. However, I realized that this approach assumes the input (job posting) is semantically similar to the policies it's meant to comply with. That’s often **not the case** — especially when a job post *violates* a policy. For example, a job offering “420-themed rewards” is unlikely to be semantically close to “mentions of illegal substances are prohibited.”

Therefore:
- I embedded **edge cases** like job postings that subtly violate policies
- I stored **classified job postings** in the vector DB. Since most postings follow consistent patterns, this allows the vector DB to function as a **semantic cache**. The more data the system sees, the faster and smarter it becomes.
- This enables **fast short-circuiting**: if a new posting is similar to a previously classified one, we can retrieve that result instantly without running the full classification pipeline again.

---

## 3. **Fallback: Orchestrator-Worker Model for New or Uncached Inputs**

If the vector search doesn't return a confident classification (i.e., it’s a **new or rare case**), the system falls back to a **multi-agent architecture** using an **Orchestrator-Worker pattern**:

> ![Orchestrator Diagram](https://github.com/user-attachments/assets/852dc5af-211e-4c4c-86c6-d44654edea9e)

Here’s how it works:
- The **Orchestrator** is given a high-level overview: a summary of each policy category and what it covers.
- Based on the job posting, it dynamically selects relevant categories and **spawns Workers** to investigate each one.
- Each **Worker** receives the **full list of policies** within their category and performs a detailed compliance check.
- All Workers run **concurrently** using `asyncio`.
- The individual results are **aggregated and returned** to the client with the policy categories and potential violations clearly identified.

---

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
- Install PostgreSQL:
  ```sh
  brew install postgresql
  ```

### 2. Database Setup
- Ensure PostgreSQL is running and create the database:
  ```sh
  createdb policykit
  ```
- Run migrations:
  ```sh
  alembic upgrade head
  ```

### 3. Seeding the Database
The project includes several seeding scripts to populate the database with initial data:

#### a. Seed Policies
To seed the vector database with policy categories and their respective policies:
```sh
python -m app.scripts.seed_policies
```
This script includes policies that cover:
- Discrimination
- Legal Compliance
- Workplace Standards
- Compensation
- Privacy and Security

#### b. Seed Job Postings
This script populates the database with example job postings and their embeddings for RAG:
```sh
python -m app.scripts.seed_job_postings
```
The script includes examples of:
- Gender and age discrimination
- Illegal activities
- Copyright infringement
- Academic misconduct
- Privacy violations
- Multiple violation types

#### c. Verify Seeding
You can verify the seeded data using PostgreSQL:
```sh
# Check policy categories
psql policykit -c "SELECT * FROM policy_categories;"

# Check policies
psql policykit -c "SELECT p.id, p.title, c.name as category FROM policies p JOIN policy_categories c ON p.category_id = c.id;"
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
- **SafetyKitViolation**: Used for prompt injection, or other safety-related issues

### RAG & Vector Search
- When a new job posting is checked, its embedding is generated and compared to existing embeddings in Chroma.
- If a similar posting is found (above a similarity threshold), its result is reused for efficiency.
- Otherwise, the posting is checked against all policies and the result is stored in Chroma for future RAG.
- Chroma provides efficient similarity search using HNSW (Hierarchical Navigable Small World) algorithm.

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
- For vector search issues, verify that:
  - The Chroma database is properly initialized in the `.chroma` directory
  - The job posting embeddings collection exists
  - Your virtual environment is activated
  - All dependencies are installed

## License
MIT 
