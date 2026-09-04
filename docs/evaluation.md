# How PolicyKit is tested

PolicyKit uses two kinds of tests.

## Tests that do not call OpenAI

Most tests use a small replacement for the OpenAI model. The replacement returns a known
answer, so the test is fast, repeatable, and free.

These tests check that:

- Every required rule is included
- Missing, repeated, or unexpected rule answers are rejected
- Quoted problem text matches the job post
- Published rule versions cannot change
- Old reviews keep their original rule versions
- A saved answer is reused only for an identical post and rule list
- The model cannot request an action that is not currently allowed
- Suggested changes cannot alter unrelated text
- Recruiter approval is required
- A post cannot be published before all checks pass
- Interrupted work can continue
- Two people cannot overwrite each other's rule or review decisions

Run these tests with:

```bash
cd server
.venv/bin/pytest -q
```

## Tests that call OpenAI

The project also contains 13 example job posts with expected answers. These examples
include:

- Posts that should pass
- Clear age or protected-group preferences
- Missing New York or California pay ranges
- Illegal work
- Requests for sensitive personal data
- Unpaid trial work
- A case that should be sent to a person
- Several problems in one post
- Text inside a post that tries to give instructions to the model

The test compares the model's answer for every rule with the expected answer.

Run a small number first because these tests use a small amount of your OpenAI balance:

```bash
cd server
.venv/bin/python -m app.evals.runner --live --limit 5
```

Run all examples with:

```bash
.venv/bin/python -m app.evals.runner --live
```

## How the result numbers work

- **Assessment accuracy:** How often the model gave the expected answer for a rule.
- **Violation recall:** Of all problems marked in the test examples, how many the model
  found.
- **Violation precision:** Of all problems reported by the model, how many were marked as
  problems in the test examples.

On September 3, 2026, the model gave the expected answer for all 13 examples. Assessment
accuracy, violation recall, and violation precision were all 100%.

This result does not promise that every future run will be perfect. Model answers can
change. Run the live tests again after changing:

- The OpenAI model
- Instructions sent to the model
- Rule text
- Location or job-type matching
- The required answer format

A change should not be released if it causes the model to miss an important problem that
the earlier version found.

The test examples demonstrate the product. They are not legal advice.
