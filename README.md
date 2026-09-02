# PolicyKit

PolicyKit is a pre-publication compliance agent for job postings. It investigates a
draft, checks every applicable platform policy, asks for missing facts, proposes precise
revisions, and requires human approval before a revised posting can be published.

The project is designed around a clear safety boundary: the OpenAI agent controls the
investigation, while Python controls permissions, policy coverage, evidence validation,
versioning, and the final publication gate.

## Product flow

1. A recruiter submits a draft and its hiring locations.
2. Python resolves which jurisdictions apply.
3. The `run_compliance_check` tool loads every applicable policy from an immutable
   PostgreSQL snapshot.
4. A constrained OpenAI call assesses every policy and cites exact posting text.
5. Python rejects incomplete policy coverage or invalid evidence offsets.
6. The agent can read policies, search ChromaDB, ask a recruiter a focused question, or
   propose a revision.
7. Agent revisions pause for recruiter approval and are checked again after approval.
8. Python permits publication only after the latest approved draft has a complete clean
   check.

## Technology responsibilities

| Technology | Responsibility |
| --- | --- |
| Python | Agent runtime, tools, deterministic validation, worker, and evals |
| FastAPI | Session, policy administration, review, publication, and event APIs |
| OpenAI | Tool selection, structured policy assessment, and embeddings |
| PostgreSQL | Canonical policies, snapshots, drafts, findings, approvals, and audit history |
| ChromaDB | Rebuildable semantic index for policies and human-reviewed precedents |
| Next.js | Recruiter workspace and policy administration interface |

ChromaDB never stores the authoritative policy or returns a final verdict. Search results
are hydrated and validated against PostgreSQL. Exact classifier reuse is keyed by posting
text, policy snapshot, policy IDs, prompt version, and model configuration.

## Local setup

Requirements:

- Python 3.12+
- Node.js 22+
- PostgreSQL 14+

Copy the environment template and add an OpenAI project key:

```bash
cp .env.example .env
```

Create the local database:

```bash
createdb policykit
```

Install and migrate the backend:

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_data
```

Start the API and its in-process durable worker:

```bash
cd server
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Install and start the web app in another terminal:

```bash
cd client
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). FastAPI documentation is available
at [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json).

PostgreSQL can also be started with `docker compose up -d postgres` when Docker is
available. For that Docker service, set `DATABASE_URL` to
`postgresql+asyncpg://postgres:postgres@localhost:5432/policykit`. ChromaDB uses an
embedded persistent database under `.data/chroma` by default.

## Policy administration

An administrator creates a draft policy with a stable key, complete rule, scope,
remediation, exceptions, and both violation and compliant examples. Publishing creates an
immutable version and a new policy snapshot. Prior sessions continue to reference their
original snapshot.

Policy states are:

```text
draft -> testing -> published -> retired
```

Published versions cannot be edited. Creating a new draft copies the latest version so an
administrator can test and publish a replacement.

## Agent tools

The orchestrator can call:

- `set_hiring_locations`
- `run_compliance_check`
- `search_policies`
- `read_policy`
- `search_reviewed_precedents`
- `propose_revision`
- `ask_recruiter`
- `escalate_to_reviewer`
- `complete_session`

Tool arguments are strict JSON schemas. Every call and result is stored as an agent step.
The agent has a fixed step budget and interrupted runs are recovered from PostgreSQL.

## Validation

Backend checks do not use API credit:

```bash
cd server
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/pytest -q
```

Frontend checks:

```bash
cd client
npm run typecheck
npm run build
```

Live evals are opt-in because they use the configured OpenAI account. See
[docs/evaluation.md](docs/evaluation.md).

## Architecture

See [docs/architecture.md](docs/architecture.md) for the data model, request flow, tool
boundaries, failure behavior, and extension points.
