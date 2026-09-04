# PolicyKit

PolicyKit helps recruiters create and improve job postings, then checks them against
company policies and local requirements before publication.

A recruiter can start with short role ideas or paste an existing posting. The posting
opens as an editable draft. Writing help is optional, and a compliance run starts only
when the recruiter selects **Check latest draft**. A person makes every final text and
publication decision.

In this prototype, “publish” means that PolicyKit records the posting as approved inside
PolicyKit. It does not send the posting to LinkedIn, Indeed, or another job site.

![Start a job posting from ideas or existing text](docs/images/policykit-home.png)

![Review an exact compliance edit before accepting it](docs/images/policykit-review.png)

## The main ideas

- A **draft** is the current editable job posting.
- A **saved version** is a copy of the draft at one point in time. Saved versions do not
  change. A later save creates another version, so people can see and restore earlier text.
- A **policy** is a company rule or local requirement for a job posting.
- A **policy snapshot** is the fixed set of policy versions used by one compliance run.
- An **agent** is the Python-controlled review process. Its router model chooses from
  actions allowed by the Python server.
- A **finding** is the result for one policy, with the reason and exact evidence when the
  posting has a problem.

## What a recruiter can do

1. Choose **Start from ideas** or **Paste a posting**.
2. For ideas, enter the known role facts and ask the writing model for a first draft. For
   pasted text, open the draft without a model call.
3. Edit and save the posting directly. Each save creates a new version.
4. Optionally ask for a focused writing suggestion. PolicyKit shows a preview. The
   recruiter can accept it into the editor or discard it.
5. Select **Check latest draft** to start the full compliance agent.
6. Read the policy findings, quoted evidence, agent activity, and any proposed compliance
   edit.
7. Approve or reject model-proposed text. Model text is never accepted automatically.
8. Run another check when the posting changes. An old result is marked **stale** and
   cannot make a newer version ready.
9. If a policy reviewer rejects the posting, edit and save a new version before checking
   again.
10. Record the posting as published only after the current version passes every
   publication rule.

```mermaid
flowchart TD
    start["Create a posting"] --> path{"How do you want to start?"}
    path -->|"Short role ideas"| ideas["Generate a first draft with OpenAI"]
    path -->|"Existing text"| paste["Paste the posting"]
    ideas --> draft["Editable saved draft"]
    paste --> draft
    draft -->|"Edit and save; no OpenAI call"| version["New saved version"]
    version --> draft
    draft -->|"Optional writing help"| preview["Preview a suggestion"]
    preview -->|"Accept into editor"| draft
    preview -->|"Discard; no OpenAI call"| draft
    draft -->|"Check latest draft"| agent["Full compliance agent run"]
    agent --> result["Findings and proposed compliance edits"]
    result -->|"Posting changes"| stale["Old check becomes stale"]
    stale --> draft
    result -->|"Current check has no open findings"| ready["Ready for internal publication"]
```

## What happens during Check latest draft?

**Check latest draft** is one explicit request to start the full agent. The run can use:

- A **router model** to choose the next allowed action.
- A **checker model** to compare the complete saved posting with every applicable policy.
- **Policy search** to find useful policy passages.
- **Reviewed-precedent search** to find related past human decisions.
- A **proposed compliance edit** when a small text change can address a finding.

The agent can take more than one step, so one run can make more than one OpenAI request.
The Python server supplies the allowed actions and the complete required policy list. It
also rejects incomplete policy results, bad evidence locations, unsupported edits, and
attempts to publish before the current version is ready.

When the agent proposes text, it creates a preview for the recruiter. The agent cannot
approve its own text. If the recruiter accepts a proposed compliance edit, PolicyKit
checks the changed posting again before it can become ready.

## Current and stale checks

A compliance result belongs to one exact saved posting version.

- **Never run** means no saved version has completed a compliance check.
- **Running** means the requested agent run is waiting or in progress.
- **Current** means the latest completed check belongs to the current saved version.
- **Stale** means the posting changed after the last completed check.

Typing in the editor does not change the saved version. After the recruiter saves new
text, PolicyKit keeps the older version and its audit history, marks its check stale, and
requires a check of the new version before publication.

## Safety and human control

The OpenAI models cannot connect directly to PostgreSQL and cannot publish a posting.
Python decides:

- Which policy versions apply.
- Which actions the agent may use at each step.
- Whether every required policy has exactly one result.
- Whether quoted evidence matches the saved posting.
- Whether an agent edit changes only declared text.
- Whether the recruiter approved model-proposed text.
- Whether the current saved version is ready for publication.

If the agent needs missing facts, it asks the recruiter. If a result needs judgment, it
can send the session to a policy reviewer. The reviewer can approve an exception, request
changes, or reject the posting. PolicyKit records that human decision.

## How the parts fit together

```mermaid
flowchart LR
    recruiter["Recruiter"] --> web["Next.js website"]
    manager["Policy manager"] --> web
    web --> api["FastAPI and Python"]
    api <--> postgres[("PostgreSQL official record")]
    api -->|"Optional writing request"| writer["OpenAI writing model"]
    api -->|"Explicit compliance request"| worker["Background agent worker"]
    worker <--> router["OpenAI router model"]
    worker --> checker["OpenAI checker model"]
    worker -.->|"supporting search"| chroma[("ChromaDB")]
    postgres --> reindex["Policy and precedent indexing"]
    reindex --> textNumbers["OpenAI turns text into numbers"]
    textNumbers --> chroma
```

## What each technology does

| Technology | Job in PolicyKit |
| --- | --- |
| Python | Selects applicable policies, runs allowed agent tools, validates model output, and enforces publication rules |
| FastAPI | Provides the web API and live session updates |
| PostgreSQL | Stores the official policies, policy snapshots, saved posting versions, findings, changes, human decisions, and audit activity |
| OpenAI | Generates optional writing help, routes agent steps, checks policies, and turns text into numbers that Chroma can compare by meaning |
| ChromaDB | Finds related policy text and reviewed precedents by meaning |
| Next.js | Provides the recruiter editor and policy-management website |

PostgreSQL is the official record. ChromaDB contains derived search copies. A Chroma
result cannot add or remove a required policy, decide that a posting passes, or publish
anything. Python reads the official text from PostgreSQL before it gives a search result
to the agent. The Chroma data can be rebuilt from PostgreSQL.

## Privacy and OpenAI cost

These actions do **not** call OpenAI:

- Typing or saving a draft.
- Viewing a posting, version history, finding, or policy.
- Loading an older version into the editor.
- Accepting a writing preview into the local editor.
- Discarding a writing preview.

These actions can call OpenAI and use API credit:

- **Generate draft** sends the supplied role ideas and role details to the writing model.
- Writing help for selected text sends the selection and up to 1,500 characters from each
  side as nearby context. It does not send the rest of the draft.
- Writing help without a selection sends the full draft, up to 12,000 characters.
- **Check latest draft** starts the full agent. The router receives the saved posting and
  session state. The checker receives the full saved posting and the full applicable
  policy text. Search steps can turn search text into numbers for meaning-based
  comparison.
- Testing or publishing a policy, rebuilding Chroma data, and running live model
  evaluations can also call OpenAI.

PolicyKit can reuse an exact saved compliance result when the posting, policy snapshot,
policy versions, checker model, and checker instructions are unchanged. A changed posting
requires a new result. The agent has a maximum step count, model output limits, request
timeouts, and limited provider retries, but this prototype has no user rate limit or
spending budget.

Saved drafts, versions, findings, approvals, reviewer decisions, and agent activity are
stored in PostgreSQL. Initial writing output and writing previews are not saved by the
writing endpoints; they become saved only if the recruiter puts the text in the editor
and saves a version. The browser also keeps unsaved editor text on that device so it can
restore the text after accidental Back, Forward, refresh, or tab-close actions.
`OPENAI_STORE_RESPONSES=false` is the default application setting, but data sent to
OpenAI is still subject to the provider's API data rules.

This prototype has no sign-in, rate limiting, or separation between customer accounts.
Do not expose it to the public internet or use confidential production data without
adding those controls.

## Policy management

A policy manager can create, test, update, and publish policies in the website.

![Published policies and their search status](docs/images/policykit-policy-library.png)

Each policy contains where it applies, its rule text, reason, recommended fix, examples, and
exceptions. A published policy version cannot change. The manager creates a new version
instead.

PolicyKit pins the latest published policy snapshot when the recruiter first selects
**Check latest draft**. Later runs in the same session keep that snapshot, even if a
manager publishes a newer policy version. This keeps repeated checks consistent. A new
session uses the latest policy set when its first check starts.

## Run PolicyKit locally

You need:

- Python 3.12 or newer.
- Node.js 22 or newer.
- PostgreSQL 14 or newer.
- Docker Desktop if you want Docker to run PostgreSQL.
- An OpenAI API key for writing, agent, checker, search-index, policy-test, and live-eval
  requests.

Copy the example settings and add your OpenAI key:

```bash
cp .env.example .env
```

### 1. Start PostgreSQL

With Docker:

```bash
docker compose up -d postgres
```

Use this value in `.env` for the Docker database:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policykit
```

If PostgreSQL is installed directly, run `createdb policykit`. The default local value is
`postgresql+asyncpg:///policykit`.

### 2. Prepare and start the Python server

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_data
.venv/bin/python -m app.scripts.reindex
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The seed command adds example policies and evaluation cases without calling OpenAI. The
reindex command calls the OpenAI embeddings API for published policy text and reviewed
precedent excerpts.

### 3. Start the website

In another terminal:

```bash
cd client
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The API server runs the background agent worker by default. To run it as a separate
process, set `RUN_AGENT_WORKER=false` for the API process and start:

```bash
cd server
.venv/bin/python -m app.scripts.run_worker
```

## Important settings

All settings are listed in [`.env.example`](.env.example).

| Setting | Purpose |
| --- | --- |
| `OPENAI_WRITER_MODEL` | Generates first drafts and optional writing suggestions |
| `OPENAI_AGENT_MODEL` | Chooses the next allowed action in a full agent run |
| `OPENAI_CHECKER_MODEL` | Checks the posting against every applicable policy |
| `OPENAI_EMBEDDING_MODEL` | Turns text into numbers that Chroma uses for meaning-based search |
| `OPENAI_STORE_RESPONSES` | Controls whether Responses API requests ask OpenAI to store the response |
| `OPENAI_TIMEOUT_SECONDS` | Limits how long one OpenAI request can wait |
| `OPENAI_WRITER_MAX_OUTPUT_TOKENS` | Limits writing-model output |
| `OPENAI_AGENT_MAX_OUTPUT_TOKENS` | Limits router-model output |
| `OPENAI_CHECKER_MAX_OUTPUT_TOKENS` | Limits checker-model output |
| `OPENAI_CHECKER_REASONING_EFFORT` | Sets checker reasoning effort |
| `CHROMA_MODE` | Uses local Chroma, remote Chroma, or disables meaning-based search |
| `RUN_AGENT_WORKER` | Runs the background agent inside the API process |
| `AGENT_MAX_STEPS` | Limits the steps in one full agent run |
| `AGENT_STALE_AFTER_SECONDS` | Sets when interrupted work returns to the queue |

## Check the code

The normal test suite uses model replacements and does not call OpenAI:

```bash
make lint
make test
```

A fuller set of checks is:

```bash
cd server
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/python -m compileall -q app tests
.venv/bin/pip check
.venv/bin/pytest -q
.venv/bin/python -m app.evals.runner

cd ../client
npm run typecheck
npm run build
npm audit --audit-level=high
```

Live classifier evaluations call OpenAI and use API credit. Start with a small set:

```bash
cd server
.venv/bin/python -m app.evals.runner --live --limit 5
```

Read [the architecture guide](docs/architecture.md) and
[the evaluation guide](docs/evaluation.md) for more detail.

## Failure and retry behavior

- If writing assistance fails or returns the same text, the page keeps the recruiter's
  input and shows an error. The recruiter chooses whether to try again.
- The OpenAI client can retry a failed provider request up to two times.
- If a full agent run still fails, PolicyKit keeps the saved draft and marks the run as
  failed. The recruiter can select **Check latest draft** to start another run.
- If a policy reviewer rejects a posting, the same text cannot simply be checked again.
  The recruiter must edit and save a new version first.
- If the worker stops during a run, PolicyKit returns old in-progress work to the queue
  after `AGENT_STALE_AFTER_SECONDS`.
- A tool error is recorded for the agent. The agent can choose another allowed step until
  it reaches `AGENT_MAX_STEPS`, when the session is sent for human review.

## Prototype limits

This project is a working prototype, not legal advice or a production compliance system.
It does not have:

- Sign-in or role-based access.
- Customer-account separation.
- Rate limits or API spending budgets.
- Production key storage, monitoring, or alerts.
- A rule for how long saved data is kept.
- A connection that publishes to an external job board.

The included policies and evaluation cases are product demonstrations. A qualified person
must review real policies and final publication decisions.
