# Evaluation strategy

PolicyKit separates deterministic tests from live model evals.

## Deterministic tests

The regular test suite uses fake model and vector-index boundaries. It verifies:

- Full applicable-policy coverage
- Duplicate, missing, and unexpected policy rejection
- Exact evidence text and offset validation
- Immutable published policy versions and historical snapshots
- Exact-cache keys and reuse
- Agent step and completion limits
- Recruiter question, approval, review, and publication state gates
- API contracts without network calls or API credit

## Model eval cases

The seeded eval set includes compliant controls, clear violations, subtle language,
multiple violations, negation, missing compensation details, and prompt-injection text
embedded inside a job posting.

Primary metrics are:

- Violation recall and false-negative rate
- Per-policy precision, recall, and F1
- Evidence citation accuracy
- Complete policy coverage
- Uncertainty and escalation rate
- Repeatability
- Latency, tokens, and estimated cost

## Running live evals

Live evals are opt-in:

```bash
cd server
.venv/bin/python -m app.evals.runner --live --limit 5
```

Start with a small limit. Review failures before running the complete suite. A model or
prompt change should not ship when it increases the critical false-negative count.
