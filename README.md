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
    agent --> orchestrator["Agent LLM"]
    agent --> tools["State-scoped Python tools"]
    tools --> checker["Full-policy checker"]
    checker --> classifier["Classifier LLM"]
    tools --> db
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
| FastAPI | Recruiter sessions, policy administration, edit decisions, and publication APIs |
| LLM | Agent tool selection and structured policy assessment |
| PostgreSQL | Policies, snapshots, posting versions, findings, recruiter decisions, audit steps, and exact cache |
| Next.js | Recruiter workspace and policy-administration interface |

PostgreSQL is always authoritative. Python selects every applicable policy from the
session's pinned snapshot. The classifier must return one result for each selected policy.

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

The audit trail includes tool inputs and outputs, model response IDs, token use, latency,
evidence, posting versions, exact edits, and recruiter decisions. A periodic worker
recovery pass returns interrupted sessions to the queue.

## Publication safeguards

`complete_session` and the clean publication path enforce these conditions:

- Every recruiter location resolves to a supported concrete jurisdiction.
- The latest posting has one assessment for every applicable policy.
- Every assessment is `no_violation`.
- An agent-authored posting version has explicit recruiter approval.
- The assessment set matches the current posting version and the pinned policy snapshot.

The override publication path requires a recruiter explanation and stores it in the audit
trail. It never publishes an unapproved agent revision. An override can run after the
current agent step pauses or finishes, which prevents a publication race with the worker.

Policy applicability is evaluated at the session start time. A policy that expires while a
review is in progress remains part of that review, while new sessions use the current
policy set. Published policy versions are immutable. PostgreSQL locks serialize policy
publication so concurrent changes cannot create conflicting snapshots.

## Policy administration

An administrator can create, test, version, and publish policies from the web interface.
A policy includes its category, canonical scope, enforcement level, rule, remediation,
exceptions, and both violation and compliant examples. Category is restricted to
`Discrimination`, `Compensation`, `Employment status`, `Transparency`, or `Content`.

![Versioned policies in the policy library](docs/images/policykit-policy-library.png)

![The compact policy editor](docs/images/policykit-policy-editor.png)

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
| `read_policy` | Read one canonical policy from the pinned snapshot |
| `propose_revision` | Declare the smallest supported edits; Python reconstructs the draft |
| `ask_recruiter` | Pause for a missing business fact |
| `finish_with_findings` | End the review when findings require a recruiter decision |
| `complete_session` | Ask Python to apply the clean-check gate |

The runtime rejects unknown tools, tools that were not offered in the current state,
multiple tool calls in one turn, overlapping edits, non-unique source text, edits tied to
the wrong finding, and changes outside the declared edit set.

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
authenticated recruiter and policy-admin roles at the FastAPI boundary, plus managed
PostgreSQL, secret management, rate limits, and monitoring.
