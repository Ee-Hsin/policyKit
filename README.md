# PolicyKit

PolicyKit helps a recruiter check a job post before it goes live.

It reads the post, checks the rules that apply, points to problem text, and suggests small
changes. A person must approve any suggested change. The software checks the changed post
again before it can be marked ready.

In this prototype, “publish” means recording inside PolicyKit that the post passed its
checks. PolicyKit does not send the post to LinkedIn, Indeed, or another job site.

If these terms are new:

- A **rule** is a requirement that a job post must follow. The code sometimes calls it a
  policy.
- A **review** is one complete check of one job post. The code sometimes calls it a
  session.
- A **model** is the OpenAI software that reads text and returns an answer.
- A **database** is where PolicyKit saves rules, job posts, and results.
- A **server** is the part of PolicyKit that receives requests from the website and does
  the work.
- An **API key** is a private password that lets PolicyKit use OpenAI. Never share it or
  commit it to Git.

![PolicyKit recruiter experience](docs/images/policykit-home.png)

## What happens when someone submits a job post?

1. The recruiter enters the job post, company name, job type, and hiring locations.
2. PolicyKit finds the rules for those locations and that job type.
3. PolicyKit saves the exact rule versions used for this review. Later rule changes cannot
   change the result of a review that already started.
4. An OpenAI model compares the job post with every required rule.
5. PolicyKit's server checks that no rule was skipped and that every quoted phrase exists
   in the post.
6. If information is missing, PolicyKit asks the recruiter a clear question.
7. If the post breaks a rule, PolicyKit can suggest a small text change.
8. The recruiter approves or rejects that change.
9. PolicyKit checks the approved text again.
10. The post is marked ready only when every required rule passes or a policy reviewer
    resolves the remaining question.

![A suggested change waiting for recruiter approval](docs/images/policykit-review.png)

## The most important safety rule

The OpenAI model can choose what to check next, but it cannot make changes by itself.

PolicyKit's server decides:

- Which rules must be checked
- Which actions the model may request
- Whether quoted evidence is correct
- Whether a suggested change follows the allowed edit limits
- Whether a person approved the change
- Whether the post is ready

OpenAI cannot connect directly to the database or publish a job post.

## How the parts fit together

```mermaid
flowchart LR
    person["Recruiter or policy manager"] --> website["PolicyKit website"]
    website --> server["Python server"]
    server --> database[("Main database")]
    server --> background["Background job reviewer"]
    background --> model["OpenAI model chooses the next allowed step"]
    background --> check["OpenAI model checks each required rule"]
    background --> database
    background <--> search[("Chroma search helper")]
```

The two OpenAI calls have different jobs:

- The **next-step model** chooses one allowed action, such as checking the post, asking a
  question, or suggesting a change.
- The **checking model** compares the post with a list of rules supplied by Python. It
  cannot choose which rules to skip.

## What each technology does

| Technology | Plain-English job |
| --- | --- |
| Python | Runs the review and checks that every step is allowed |
| FastAPI | Receives requests from the website |
| OpenAI | Chooses review steps, checks rules, and turns text into numbers used to compare meaning |
| PostgreSQL | Stores the official rules, job posts, results, changes, and approvals |
| ChromaDB | Helps find related rules and past reviewed examples |
| Next.js | Displays the website used by recruiters and policy managers |

PostgreSQL is the official record. ChromaDB is only a search helper. A Chroma search can
help the model understand a result, but it cannot decide which rules must be checked or
whether a post passes.

PolicyKit saves each step. This includes the text that was checked, the rules used, the
model's results, suggested changes, approvals, how long the check took, and which model
was used.

If the background reviewer stops unexpectedly, it can continue unfinished work later.

## Checks that must pass before publication

PolicyKit will not mark a post ready unless:

- Every hiring location is understood.
- Every required rule was checked.
- No open problem or unclear result remains.
- A person approved any text suggested by the model.
- The final result belongs to the current version of the job post.

The same checks run again when the recruiter records the post as published inside
PolicyKit. Sending a request directly to the server cannot skip them.

### Why the rule list does not change during a review

When a review begins, PolicyKit records the exact rule versions it will use.

For example:

1. A review starts with Pay Rule version 2.
2. A policy manager later publishes Pay Rule version 3.
3. The existing review continues with version 2.
4. New reviews use version 3.

This makes old results easier to understand and reproduce.

## Managing rules

A policy manager can create, test, update, and publish rules in the website.

![Published rules and their search status](docs/images/policykit-policy-library.png)

Each rule contains:

- A title and unique key
- The places and job types where it applies
- The rule itself
- An explanation of why it exists
- A recommended fix
- Examples that fail
- Examples that pass
- Any exceptions

A published rule cannot be edited. The policy manager creates a new version instead. Old
reviews keep the old version, while new reviews use the latest published version.

## Run PolicyKit on your computer

The rest of this page is for someone who wants to run or change the code. You can stop
here if you only want to understand the product.

These steps use Terminal, the text-based app for giving commands to your computer.

You need:

- Python 3.12 or newer
- Node.js 22 or newer
- PostgreSQL 14 or newer
- Docker Desktop if you want Docker to start PostgreSQL for you
- An OpenAI API key

Copy the example settings file:

```bash
cp .env.example .env
```

Add your OpenAI key to `.env`.

### 1. Start the database

With Docker:

```bash
docker compose up -d postgres
```

Then use this value in `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policykit
```

If PostgreSQL is installed directly on your computer, run `createdb policykit`. The
default address is `postgresql+asyncpg:///policykit`.

### 2. Prepare the Python server

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_data
```

The last command adds example rules and test cases. It does not use your OpenAI balance.

Build the Chroma search data:

```bash
.venv/bin/python -m app.scripts.reindex
```

This command uses the OpenAI API to turn the rule text into numbers that Chroma can
compare. It is the only reason Chroma can find text with a similar meaning.

Start the Python server:

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### 3. Start the website

Open another terminal:

```bash
cd client
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Important settings

All settings are listed in [`.env.example`](.env.example).

| Setting | What it controls |
| --- | --- |
| `OPENAI_AGENT_MODEL` | The model that chooses the next review step |
| `OPENAI_CHECKER_MODEL` | The model that checks the rules |
| `OPENAI_CHECKER_REASONING_EFFORT` | How much work the checking model uses before answering |
| `OPENAI_STORE_RESPONSES` | Whether OpenAI stores model responses |
| `CHROMA_MODE` | Whether Chroma runs on this computer, on another server, or is off |
| `RUN_AGENT_WORKER` | Whether the Python server also runs the background reviewer |
| `AGENT_MAX_STEPS` | The maximum number of steps in one review run |
| `AGENT_STALE_AFTER_SECONDS` | How long to wait before restarting interrupted work |

To run the background reviewer as its own program, set `RUN_AGENT_WORKER=false` for the
Python server and run:

```bash
cd server
.venv/bin/python -m app.scripts.run_worker
```

## Check that the code works

These Python checks do not call OpenAI:

```bash
cd server
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/python -m compileall -q app tests
.venv/bin/pip check
.venv/bin/pytest -q
.venv/bin/python -m app.evals.runner
```

Check the website code:

```bash
cd client
npm run typecheck
npm run build
npm audit --audit-level=high
```

The live checks call OpenAI and use a small amount of your OpenAI balance:

```bash
cd server
.venv/bin/python -m app.evals.runner --live --limit 5
.venv/bin/python -m app.evals.runner --live
```

On September 3, 2026, all 13 live examples produced the expected answers. A future model
run can differ, so run these checks again after changing a model, instruction, rule, or
answer format.

Read [how the system works](docs/architecture.md) or
[how the test examples work](docs/evaluation.md) for more detail.

## What is still needed before real production use?

This project is a working prototype. Before a real company uses it, it needs:

- Sign-in
- Different access rights for recruiters, reviewers, and policy managers
- Separation between customer accounts
- Secure online storage for keys and passwords
- Limits on repeated requests
- Alerts when the service has a problem
- Clear rules for how long data is kept

The example rules are product demonstrations. They are not legal advice.
