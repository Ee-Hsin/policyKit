# How PolicyKit is tested

PolicyKit separates repeatable code tests from live model evaluations. The normal tests
do not call OpenAI or use API credit. Live evaluations are optional and must be requested
with `--live`.

## Repeatable tests without OpenAI

Most backend tests use a small model replacement that returns a known answer. This makes
the tests fast, repeatable, and free.

The tests cover:

- Starting a posting as an editable draft without fixing its policy set or starting
  background work.
- Generating a writing preview without saving a job posting.
- Saving direct recruiter edits as new versions that cannot later change.
- Rejecting an unchanged save or a save based on an older version.
- Keeping writing suggestions as previews until the recruiter saves the text.
- Returning a clear error when the writing model returns unchanged text.
- Limiting selected writing help to the selection and nearby context.
- Rechecking the saved base version after a writing-model request finishes.
- Starting the full agent only after an explicit compliance request.
- Saving a fixed policy set and review time at the first explicit check.
- Reporting whether a check is never run, running, current, or stale.
- Keeping old-version findings from approving a newer posting version.
- Preventing an old browser action from publishing or resuming work for a newer version.
- Preventing an old reviewer tab from deciding a newer posting version.
- Requiring an edit and new saved version after a policy reviewer rejects a posting.
- Sending every applicable policy to the checker.
- Rejecting missing, repeated, or unexpected policy results.
- Checking that quoted evidence matches the saved posting.
- Reusing a checker answer only for identical inputs.
- Restricting the router to actions allowed in the current state.
- Reconstructing agent-proposed text from declared changes.
- Requiring a person to approve model-proposed compliance text.
- Blocking publication until the current version passes every publication rule.
- Recovering interrupted background work.
- Keeping published policy versions and old fixed policy sets unchanged.

Run the backend tests:

```bash
cd server
.venv/bin/pytest -q
```

Run backend lint and formatting checks:

```bash
cd server
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/python -m compileall -q app tests
.venv/bin/pip check
```

Check the website:

```bash
cd client
npm run typecheck
npm run build
```

## Authored compliance examples

The repository contains 13 example job postings with expected policy results. They
include:

- Postings that should pass.
- Clear age and protected-group preferences.
- Missing New York or California pay ranges.
- Illegal work.
- Requests for sensitive personal data.
- Unpaid trial work.
- Worker classification that needs human judgment.
- Several problems in one posting.
- Text inside a posting that tries to instruct the model.

The local example-data check validates the example structure and policy names without
calling OpenAI:

```bash
cd server
.venv/bin/python -m app.evals.runner
```

## Live checker evaluations

The live evaluation sends each example posting and its applicable policy text to the
configured OpenAI checker. It compares every policy result with the authored expected
result.

Run a small set first because this uses API credit:

```bash
cd server
.venv/bin/python -m app.evals.runner --live --limit 5
```

Run all authored examples:

```bash
.venv/bin/python -m app.evals.runner --live
```

The report includes:

- **Exact cases:** postings where every policy result matched.
- **Assessment accuracy:** the share of individual policy results that matched.
- **Violation recall:** the share of expected problems that the checker found.
- **Violation precision:** the share of reported problems that were expected.
- **Tokens:** the total checker input and output tokens for the run.

On September 3, 2026, the checker matched all 13 authored cases. Assessment accuracy,
violation recall, and violation precision were 100%. This is a historical result, not a
promise about later runs. Model behavior can change.

On September 4, 2026, a smaller live check also passed all 3 selected cases. It used
7,317 input tokens and 5,501 output tokens. This was a final live check of the changes
described here. It used `gpt-5.4-mini` with medium reasoning and this command:

```bash
.venv/bin/python -m app.evals.runner --live --limit 3
```

The three cases were `age_preference_violation`, `california_complete_pay_range`, and
`compliant_software_engineer_new_york`.

Run the live checker evaluations again after changing:

- The checker model or reasoning setting.
- Checker instructions or required answer format.
- Policy text or where a policy applies.
- Location or employment-type matching.
- Evidence checks or the inputs used to decide whether an old answer can be reused.

A change should not be released if it causes the checker to miss an important problem
that the earlier version found.

## What the live checker evaluation does not test

The current live tests evaluate the compliance checker. They do not evaluate:

- Initial draft quality.
- Writing-suggestion quality.
- Whether a human recruiter accepts a suggestion.
- Router tool choice across a complete agent run.
- User satisfaction or publication outcomes.

The code tests still check the expected writing and router behavior with fixed model responses.
Before changing a writing or router prompt for production use, add a separate authored
evaluation set for that operation. Keep it opt-in, report its token use, and start with a
small limit.

## Cost and privacy during tests

Normal tests, lint, type checks, builds, fixture validation, typing, saving, viewing, and
discarding previews do not call OpenAI.

Commands with `--live` call OpenAI. Rebuilding Chroma data also asks OpenAI to turn text into numbers
with published policy text and reviewed precedent excerpts. Live testing can send example
posting and policy text to OpenAI, so do not put confidential data in evaluation cases.

The examples and results demonstrate the product. They are not legal advice.
