# PolicyKit

PolicyKit is a pre-publication compliance agent for job postings. It investigates a
draft, checks the complete applicable policy set, asks for missing facts, proposes exact
edits, and stops for human approval before publication.

![PolicyKit recruiter experience](docs/images/policykit-home.png)

The main design rule is simple: the model chooses the next investigation action, while
Python controls what the action can do. OpenAI cannot access the database, edit a policy,
approve its own revision, or publish a posting.

## What the product does

A recruiter enters a job description, hiring locations, employer, and employment type.
PolicyKit then:

1. Resolves the locations to canonical jurisdictions such as `US`, `US-NY`, or `GB`.
2. Pins the session to an immutable PostgreSQL policy snapshot.
3. Gives the agent only the tools that are valid for the current session state.
4. Runs a typed classifier against every applicable policy, not a retrieved sample.
5. Validates full policy coverage and every quoted evidence offset in Python.
6. Asks one focused question when required information is missing.
7. Builds any proposed revision from declared edits on the server.
8. Waits for recruiter approval, then checks the approved revision again.
9. Re-runs the deterministic publication gate before recording publication.

![A proposed revision waiting for recruiter approval](docs/images/policykit-review.png)

## System architecture

```mermaid
flowchart LR
    recruiter["Recruiter"] --> web["Next.js web app"]
    admin["Policy admin"] --> web
    web --> api["FastAPI"]
    api --> db[("PostgreSQL\nsource of truth")]
    api --> queue["Durable queued session"]
    queue --> worker["Python agent worker"]
    worker --> agent["Tool-calling orchestrator"]
    agent --> orchestrator["OpenAI agent model"]
    agent --> tools["State-scoped Python tools"]
    tools --> checker["Full-policy checker"]
    checker --> classifier["OpenAI structured classifier"]
    tools --> db
    tools <--> chroma[("ChromaDB\nderived index")]
    chroma --> embeddings["OpenAI embeddings"]
```

There are two model roles:

- The **orchestrator** sees the goal, the current posting, session state, recent activity,
  and the tools available in that state. It chooses exactly one action at a time.
- The **classifier** has no tools. Python supplies every applicable policy from the pinned
  snapshot and requires one structured assessment per policy.

This split lets the workflow be agentic without giving the model authority over policy
scope or publication.

## Technology responsibilities

| Technology | Responsibility |
| --- | --- |
| Python | Agent runtime, tool permissions, validation, recovery, cache keys, and evals |
| FastAPI | Recruiter sessions, policy administration, human review, and publication APIs |
| OpenAI | Agent tool selection, structured policy assessment, and embeddings |
| PostgreSQL | Policies, snapshots, posting versions, findings, approvals, audit steps, and exact cache |
| ChromaDB | Rebuildable semantic search over policies and human-reviewed precedents |
| Next.js | Recruiter workspace and policy-administration interface |

PostgreSQL is always authoritative. Chroma returns candidates for investigation only.
Python restricts policy search results to the session's pinned snapshot and hydrates the
canonical text from PostgreSQL. Retrieval never narrows the mandatory full-policy check.

## Session lifecycle

```mermaid
stateDiagram-v2
    [*] --> queued: Recruiter submits draft
    queued --> investigating: Worker claims session
    investigating --> waiting_for_information: Required fact is missing
    waiting_for_information --> queued: Recruiter answers
    investigating --> waiting_for_approval: Agent proposes exact edits
    waiting_for_approval --> queued: Recruiter approves revision
    waiting_for_approval --> waiting_for_information: Recruiter requests changes
    investigating --> needs_review: Policy judgment is ambiguous
    needs_review --> ready_to_publish: Reviewer resolves findings
    investigating --> ready_to_publish: Complete clean check
    ready_to_publish --> published: Publication gate passes
    investigating --> failed: Unrecoverable error
```

Every transition is stored. The audit trail includes tool inputs and outputs, model
response IDs, token use, latency, evidence, posting versions, exact edits, and human
decisions. A periodic worker recovery pass returns interrupted sessions to the queue.

## Publication safeguards

`complete_session` and the publication endpoint both enforce these conditions:

- Every recruiter location resolves to a supported concrete jurisdiction.
- The latest posting has one assessment for every applicable policy.
- No unresolved `violation` or `uncertain` finding remains.
- An agent-authored posting version has explicit recruiter approval.
- The assessment set matches the current posting version and the pinned policy snapshot.

Policy applicability is evaluated at the session start time. A policy that expires while a
review is in progress remains part of that review, while new sessions use the current
policy set. Published policy versions are immutable. PostgreSQL locks serialize policy
publication and human-review decisions so stale writes cannot change history.

## Policy administration

An administrator can create, test, version, and publish policies from the web interface.
A policy includes its canonical scope, enforcement level, rule, remediation, exceptions,
and both violation and compliant examples.

![Versioned policies and Chroma index status](docs/images/policykit-policy-library.png)

Publishing a version retires the prior live version and creates a new immutable snapshot.
Sessions already in progress keep their original snapshot. Policy and location inputs are
normalized at the API boundary so free-form strings cannot silently skip a scoped rule.

Policy states are:

```text
draft -> testing -> published -> retired
```

## Agent tools

The orchestrator can receive these strict tools, depending on the current state:

| Tool | Purpose |
| --- | --- |
| `set_hiring_locations` | Save a location supplied by the recruiter |
| `run_compliance_check` | Check every applicable policy |
| `search_policies` | Retrieve related indexed policy passages for investigation |
| `read_policy` | Read one canonical policy from the pinned snapshot |
| `search_reviewed_precedents` | Retrieve similar human-reviewed evidence |
| `propose_revision` | Declare the smallest supported edits; Python reconstructs the draft |
| `ask_recruiter` | Pause for a missing business fact |
| `escalate_to_reviewer` | Request policy judgment from a person |
| `complete_session` | Ask Python to apply the clean-check gate |

The runtime rejects unknown tools, tools that were not offered in the current state,
multiple tool calls in one turn, overlapping edits, non-unique source text, edits tied to
the wrong finding, and changes outside the declared edit set.

## Local setup

Requirements:

- Python 3.12+
- Node.js 22+
- PostgreSQL 14+

Copy the environment template and add an OpenAI project key:

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

The seed is deterministic and makes no OpenAI calls. Build the derived Chroma index when
the API key is ready:

```bash
.venv/bin/python -m app.scripts.reindex
```

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
| `OPENAI_STORE_RESPONSES` | `false` | OpenAI response-storage choice |
| `CHROMA_MODE` | `persistent` | `persistent`, `http`, or `disabled` |
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

The September 3, 2026 verification run passed all 13 authored cases with 100% assessment
accuracy, violation recall, and violation precision. The suite covers compliant controls,
minimal pairs, multi-policy violations, missing pay ranges, uncertainty, illegal work,
sensitive-data requests, and prompt injection inside untrusted posting text. Model results
can vary, so the live suite should be rerun after prompt, model, policy, or schema changes.

See [docs/evaluation.md](docs/evaluation.md) for metric definitions and
[docs/architecture.md](docs/architecture.md) for the detailed data and trust boundaries.

## Production boundary

This repository is a working product prototype. It does not yet include an external
identity provider or multi-tenant authorization. A production deployment must add
authenticated recruiter, reviewer, and policy-admin roles at the FastAPI boundary, plus
managed PostgreSQL, managed Chroma, secret management, rate limits, and monitoring.
