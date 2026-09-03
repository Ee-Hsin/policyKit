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

There are 13 authored cases. Each case fixes the expected status for every applicable
policy, so a run can measure both missed violations and unsupported findings.

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

The September 3, 2026 full run passed 13 of 13 exact cases with 100% assessment accuracy,
violation recall, and violation precision. This is a recorded verification result, not a
guarantee of future model behavior. Repeat the live suite after changes to models, prompts,
structured schemas, policy text, or policy scope logic.
