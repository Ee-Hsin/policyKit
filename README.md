# PolicyKit

PolicyKit is a pre-publication compliance agent for job postings. It investigates a
draft, checks the complete applicable policy set, asks for missing facts, proposes exact
edits, and stops for human approval before publication.

## What the product does

A recruiter enters a job description and additional information such as the hiring
locations and employment type. PolicyKit then:

1. Determines which policies apply from the information provided.
2. Checks the posting against every applicable policy.
3. Highlights problematic text, explains each finding, and proposes exact edits.
4. Lets the recruiter accept or reject each edit and optionally explain rejected edits.
5. Applies the accepted edits and checks the revised posting again. Rejected edits and
recruiter feedback return to the agent for the next review cycle.
6. Lets the recruiter publish regardless of the review outcome. If PolicyKit has not
cleared the posting, the recruiter must provide an explanation, which is stored in
the audit trail.

## System architecture

```mermaid
flowchart LR
    recruiter["Recruiter"] --> web["Next.js web app"]
    admin["Policy admin"] --> web
    web --> api["FastAPI"]
    api --> db[("PostgreSQL\nsource of truth")]
    worker["Python agent worker"] -->|Claims queued sessions| db
    worker --> agent["Tool-calling runtime"]
    agent --> orchestrator["Orchestrator LLM"]
    agent --> tools["State-scoped Python tools"]
    tools --> checker["Full-policy checker"]
    checker --> classifier["Classifier LLM"]
    tools --> db
```

Clients communicate with our server which adds policies and sessions to the database. When a new enqueued session is added, a worker acquires a lock on it, sets it to investigating, and kicks off a review. We can run many workers if we expect a lot of traffic, and at a much larger scale, we could use a dedicated message-queue here.

There are two model roles:

- The orchestrator model sees the current state of the session and available tools. It chooses one action at a time.
- The classifier LLM is invoked by the `run_compliance_check` tool call. For every batch of applicable policies (4 by default), the system makes a classifier LLM call with those policies supplied, and asked to return an assessment per policy.

Importantly, the orchestrator agent is driven by the available tools we provide it. (The classifiers have no access to tools)

### Agent tools

The orchestrator receives a subset of these tools, depending on the current state:

| Tool | Purpose |
| --- | --- |
| `ask_recruiter` | Pause to ask for a missing business fact |
| `set_hiring_locations` | Saves a location supplied by the recruiter |
| `run_compliance_check` | Spawns classifier agents to check every applicable policy |
| `read_policy` | Loads a specific policy from the database |
| `propose_revision` | Declare an edit to the draft |
| `finish_with_findings` | To end the review with findings for recruiter |
| `complete_session` | Available when no violations, python then runs `validate_publishable` |

The runtime rejects multiple tool calls in one turn, overlapping edits, edits tied to
the wrong finding, and changes outside the declared edit set.

## Session lifecycle

```mermaid
stateDiagram-v2
    [*] --> queued: Recruiter submits draft
    queued --> investigating: Worker claims session
    investigating --> waiting_for_information: Required fact is missing
    waiting_for_information --> queued: Recruiter answers
    investigating --> waiting_for_approval: Agent proposes exact edits
    waiting_for_approval --> queued: Recruiter submits edit decisions
    investigating --> review_complete: Findings require a recruiter decision
    investigating --> ready_to_publish: Complete clean check
    ready_to_publish --> published: Publication gate passes
    waiting_for_information --> published: Recruiter overrides review
    waiting_for_approval --> published: Recruiter overrides review
    review_complete --> published: Recruiter overrides review
    investigating --> failed: Unrecoverable error
    failed --> published: Recruiter overrides review
```

## Publication

Once the orchestrator calls `complete_session`, we enforce these conditions:

- Every recruiter location resolves to a supported concrete jurisdiction.
- The latest posting has a `no_violation` assessment for every applicable policy.
- An agent-authored posting has explicit recruiter approval.
- The assessment set matches the current posting version.

Recruiters can publish a posting with violations via an override publication path, though
it requires an explanation which we stores in the database.

A recruiter can publish after the current agent step pauses or finishes, even if the review has unresolved findings or has failed.
However, if we have not cleared the posting, the recruiter must provide an override explanation, which is stored in the database.

## Policy administration

An administrator can create, test, version, and publish policies from the web interface.

Policy states are:

```text
draft -> testing -> published -> retired
```

## Local setup

Requirements:

- Python 3.12+
- Node.js 22+
- PostgreSQL 14+

Copy the environment template and add an LLM provider API key:

```bash
cp .env.example .env
```

Start PostgreSQL with Docker:

```bash
docker compose up -d postgres
```

Then set:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policykit
```

You can instead use a local PostgreSQL install and create the database with
`createdb policykit`. The default local URL is `postgresql+asyncpg:///policykit`.

Install, migrate, and seed the backend:

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_data
```

The seed is deterministic and makes no LLM calls.

Start FastAPI and its in-process worker:

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Start the web app in another terminal:

```bash
cd client
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The OpenAPI schema is at
[http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json).
If the frontend uses another origin, add it to `CORS_ORIGINS`.

## Configuration

The complete template is in [`.env.example`](.env.example). Important settings include:

| Setting | Default | Meaning |
| --- | --- | --- |
| `OPENAI_AGENT_MODEL` | `gpt-5.4-mini` | Chooses the next allowed tool |
| `OPENAI_CHECKER_MODEL` | `gpt-5.4-mini` | Produces typed per-policy assessments |
| `OPENAI_CHECKER_REASONING_EFFORT` | `medium` | Checker reasoning level |
| `OPENAI_CHECKER_MAX_OUTPUT_TOKENS` | `12000` | Initial output limit for each policy batch |
| `OPENAI_CHECKER_POLICY_BATCH_SIZE` | `4` | Policies assessed per structured model response |
| `OPENAI_STORE_RESPONSES` | `false` | LLM response-storage choice |
| `RUN_AGENT_WORKER` | `true` | Runs the queue worker with FastAPI |
| `AGENT_MAX_STEPS` | `12` | Maximum investigation actions per run |
| `AGENT_STALE_AFTER_SECONDS` | `300` | Interrupted-run recovery threshold |

For a separate worker deployment, start the API with `RUN_AGENT_WORKER=false` and run:

```bash
cd server
.venv/bin/python -m app.scripts.run_worker
```

## Validation and evals

No-cost backend checks:

```bash
cd server
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/python -m compileall -q app tests
.venv/bin/pip check
.venv/bin/pytest -q
.venv/bin/python -m app.evals.runner
```

Frontend checks:

```bash
cd client
npm run typecheck
npm run build
npm audit --audit-level=high
```

Live evals are explicit because they use API credit:

```bash
cd server
.venv/bin/python -m app.evals.runner --live --limit 5
.venv/bin/python -m app.evals.runner --live
```

See [docs/evaluation.md](docs/evaluation.md) for metric definitions and
[docs/architecture.md](docs/architecture.md) for the detailed data and trust boundaries.
