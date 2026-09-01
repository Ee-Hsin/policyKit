# PolicyKit architecture

## System boundary

The recruiter-facing web application communicates only with FastAPI. OpenAI never has
direct access to PostgreSQL, ChromaDB, the filesystem, or publication. The Python runtime
validates every requested tool and decides whether the operation is permitted for the
current session state.

```text
Next.js -> FastAPI -> PostgreSQL
                    -> queued session -> Python agent runtime -> OpenAI Responses API
                                                       |       -> typed tool request
                                                       v
                         PostgreSQL <- validated Python tool -> ChromaDB
                                                       |
                                                       v
                                            constrained OpenAI checker
```

## Two model roles

The orchestrator receives the publication goal, current draft, known facts, recent tool
results, and tool schemas. It decides what investigation action to take next. It does not
receive the full policy catalog and cannot declare a posting compliant by itself.

The classifier runs inside `run_compliance_check`. Python supplies every policy applicable
to the session's immutable snapshot and requires one structured assessment per policy.
The classifier has no tools and cannot choose a smaller policy set.

## Durable state

PostgreSQL stores:

- Stable policy identities and immutable policy versions
- Policy snapshots used by historical sessions
- Original and agent-authored posting versions
- Agent status, steps, tool inputs, tool results, token counts, and latency
- Per-policy assessments and exact evidence offsets
- Proposed changes and recruiter approvals
- Human reviews and reviewed precedents
- Authored eval cases
- Exact classifier cache entries

The worker claims queued sessions with row locking on PostgreSQL. An interrupted session
is returned to the queue after the configured stale interval.

## Search

ChromaDB has two derived collections:

- `policy_chunks`
- `reviewed_precedents`

OpenAI embeddings are supplied explicitly. A result is accepted only when its source
record and version still exist in PostgreSQL. ChromaDB can be deleted and rebuilt without
losing business data.

Search supports an investigation. It does not narrow the required full-policy check and
does not short-circuit a final decision.

## Completion gate

`complete_session` succeeds only when:

- All hiring locations resolve to known jurisdictions.
- The latest posting version has one assessment for every applicable policy.
- Every assessment is `no_violation`.
- An agent-authored revision has recruiter approval.
- Evidence validation and all required tool calls completed successfully.

Missing or failed work cannot produce a compliant result. It produces a retry, a focused
question, a human-review request, or a failed session.

## Security and privacy

Job-posting content and tool output are marked as untrusted data in both model roles.
Secrets remain on the backend. The OpenAI key is never exposed to Next.js. Model response
storage can be disabled while PolicyKit retains the application audit record in
PostgreSQL.

The local demo uses a role-oriented interface without an external identity provider. A
production deployment must add authenticated recruiter, reviewer, and policy-admin roles
at the FastAPI boundary.
