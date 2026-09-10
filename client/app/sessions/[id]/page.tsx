"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  API_BASE_URL,
  ApiError,
  answerSession,
  approveRevision,
  getSession,
  publishSession,
} from "@/lib/api";
import { labelize } from "@/lib/format";
import type { ComplianceSession, Finding, SessionStatus } from "@/lib/types";

type ChangeDecision = "accepted" | "rejected";

const runningStatuses = new Set<SessionStatus>([
  "draft",
  "queued",
  "investigating",
  "changes_proposed",
]);

const activityLabels: Record<string, string> = {
  "Agent selected its next action": "Selected the next review step",
  "Checked all applicable policies": "Compared the posting with every applicable policy",
  read_policy: "Read the full policy text",
  propose_revision: "Prepared focused changes for your review",
  "Recruiter reviewed proposed changes": "Applied your edit decisions",
  "Recruiter answered": "Added the recruiter information",
};

function activityLabel(name: string) {
  return activityLabels[name] ?? name.replaceAll("_", " ");
}

function formatElapsed(seconds: number) {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function AnnotatedPosting({ content, findings }: { content: string; findings: Finding[] }) {
  const annotations = findings
    .filter(
      (finding) =>
        finding.status !== "no_violation" &&
        finding.evidence_start !== null &&
        finding.evidence_end !== null &&
        finding.evidence_start >= 0 &&
        finding.evidence_end <= content.length &&
        finding.evidence_end > finding.evidence_start,
    )
    .sort((a, b) => (a.evidence_start ?? 0) - (b.evidence_start ?? 0));

  const nodes: ReactNode[] = [];
  let cursor = 0;
  annotations.forEach((finding) => {
    const start = finding.evidence_start ?? 0;
    const end = finding.evidence_end ?? 0;
    if (start < cursor) return;
    nodes.push(content.slice(cursor, start));
    nodes.push(
      <mark className={`posting-mark posting-mark--${finding.status}`} key={finding.id} title={finding.policy_title}>
        {content.slice(start, end)}
      </mark>,
    );
    cursor = end;
  });
  nodes.push(content.slice(cursor));

  return <div className="posting-content">{nodes}</div>;
}

function ProposedChanges({
  changes,
  decisions,
  onDecision,
}: {
  changes: ComplianceSession["proposed_changes"];
  decisions: Record<string, ChangeDecision>;
  onDecision: (changeId: string, decision: ChangeDecision) => void;
}) {
  return (
    <section className="revision-review" aria-labelledby="revision-review-heading">
      <div className="revision-review__heading">
        <h2 id="revision-review-heading">Proposed changes</h2>
        <span>{changes.length}</span>
      </div>
      <div className="revision-list">
        {changes.map((change) => (
          <article className={`revision-item${decisions[change.id] ? ` revision-item--${decisions[change.id]}` : ""}`} key={change.id}>
            <div className="revision-item__text">
              <div>
                <span>Original</span>
                <p>{change.original_text}</p>
              </div>
              <div>
                <span>Suggested</span>
                <p>{change.replacement_text || "Remove this text"}</p>
              </div>
            </div>
            <div className="revision-item__reason">
              <p>{change.reason}</p>
              <div className="revision-item__decision" aria-label="Choose whether to use this suggestion">
                <button
                  aria-pressed={decisions[change.id] === "accepted"}
                  className="decision-button decision-button--accept"
                  onClick={() => onDecision(change.id, "accepted")}
                  type="button"
                >
                  Approve
                </button>
                <button
                  aria-pressed={decisions[change.id] === "rejected"}
                  className="decision-button decision-button--reject"
                  onClick={() => onDecision(change.id, "rejected")}
                  type="button"
                >
                  Reject
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ReviewPanel({
  session,
  decisions,
  onUpdate,
}: {
  session: ComplianceSession;
  decisions: Record<string, ChangeDecision>;
  onUpdate: (next: ComplianceSession) => void;
}) {
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const reviewIsRunning = runningStatuses.has(session.status);
  const timerIsRunning = reviewIsRunning && session.status !== "draft";

  useEffect(() => {
    if (!timerIsRunning) return;
    const startedAt = Date.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [timerIsRunning]);

  async function run(action: () => Promise<ComplianceSession>) {
    setBusy(true);
    setError("");
    try {
      onUpdate(await action());
      setMessage("");
      setNotes("");
      setOverrideReason("");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The action could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  function submitAnswer(event: FormEvent) {
    event.preventDefault();
    void run(() => answerSession(session.id, message));
  }

  function submitOverride(event: FormEvent) {
    event.preventDefault();
    void run(() => publishSession(session.id, overrideReason));
  }

  const activeChanges = session.proposed_changes.filter((change) => change.status === "proposed");
  const reviewedChanges = activeChanges.filter((change) => decisions[change.id]);
  const rejectedChanges = activeChanges.filter((change) => decisions[change.id] === "rejected");
  const allChangesReviewed = reviewedChanges.length === activeChanges.length;
  const canOverridePublication = ([
    "waiting_for_information",
    "waiting_for_approval",
    "review_complete",
    "failed",
  ] as SessionStatus[]).includes(session.status);
  const reviewStarted = (["investigating", "changes_proposed"] as SessionStatus[])
    .includes(session.status);
  const policiesChecked = session.steps.some(
    (step) =>
      step.kind === "compliance_check" &&
      step.status === "completed" &&
      step.input_data.posting_version === session.current_posting_version.version,
  );
  const recentActivity = session.steps
    .filter((step) => step.status === "completed")
    .slice(-3)
    .reverse();
  const currentActivity = session.status === "queued"
    ? "Waiting for the review worker to begin."
    : policiesChecked
      ? "Reviewing the findings and preparing the next safe action."
      : "Comparing this posting with the complete applicable policy set.";
  const progressSteps = [
    {
      label: reviewStarted ? "Review started" : "Starting review",
      state: reviewStarted ? "complete" : "active",
    },
    {
      label: policiesChecked ? "Policies checked" : "Checking policies",
      state: policiesChecked ? "complete" : reviewStarted ? "active" : "pending",
    },
    {
      label: "Preparing results",
      state: policiesChecked ? "active" : "pending",
    },
  ];
  return (
    <section className="review-panel" aria-label="Review status">
      {session.status === "waiting_for_information" ? (
        <section className="review-action">
          <h2>Information needed</h2>
          <p>{session.current_question}</p>
          <form onSubmit={submitAnswer}>
            <label className="field">
              <span>Your answer</span>
              <textarea
                required
                minLength={1}
                maxLength={5000}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Give the agent the missing detail…"
              />
            </label>
            <button className="button button--primary button--full" disabled={busy}>
              {busy ? "Sending…" : "Send and continue"}
            </button>
          </form>
        </section>
      ) : null}

      {session.status === "waiting_for_approval" ? (
        <section className="review-action">
          <h2>Review changes</h2>
          <p>Approve or reject each suggestion.</p>
          <p className="review-progress">{reviewedChanges.length} of {activeChanges.length} reviewed</p>
          {rejectedChanges.length ? (
            <label className="field">
              <span>Note for rejected changes <em>Optional</em></span>
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Explain what should change…" />
            </label>
          ) : null}
          <button
            className="button button--primary button--full"
            disabled={busy || !allChangesReviewed}
            onClick={() => void run(() => approveRevision(
              session.id,
              activeChanges.map((change) => ({
                change_id: change.id,
                approved: decisions[change.id] === "accepted",
              })),
              notes,
            ))}
          >
            {busy ? "Saving…" : "Continue review"}
          </button>
        </section>
      ) : null}

      {session.status === "ready_to_publish" ? (
        <section className="review-action review-action--success">
          <h2>Ready to publish</h2>
          <p>No unresolved findings remain.</p>
          <button className="button button--primary button--full" disabled={busy} onClick={() => void run(() => publishSession(session.id))}>
            {busy ? "Publishing…" : "Publish posting"}
          </button>
        </section>
      ) : null}

      {session.status === "published" ? (
        <section className="review-action review-action--success">
          <h2>Review complete</h2>
          <p>The approved posting is published.</p>
          <Link className="button button--secondary button--full" href="/">Review another posting</Link>
        </section>
      ) : null}

      {session.status === "review_complete" || session.status === "failed" ? (
        <section className="review-action review-action--warning">
          <h2>{session.status === "failed" ? "Review stopped" : "Review complete"}</h2>
          <p>{session.error_message ?? (session.status === "failed" ? "The review could not finish." : "Unresolved findings remain. Review them below or publish with an explanation.")}</p>
        </section>
      ) : null}

      {canOverridePublication ? (
        <section className="review-action review-action--override">
          <h2>Publish without clearance</h2>
          <p>You can publish this draft without resolving the review. Explain why you are overriding the PolicyKit review.</p>
          <form onSubmit={submitOverride}>
            <label className="field">
              <span>Override explanation</span>
              <textarea
                required
                maxLength={2000}
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
                placeholder="Explain why this posting should be published…"
              />
            </label>
            <button
              className="button button--primary button--full"
              disabled={busy || !overrideReason.trim()}
            >
              {busy ? "Publishing…" : "Publish with override"}
            </button>
          </form>
        </section>
      ) : null}

      {(["draft", "queued", "investigating", "changes_proposed"] as SessionStatus[]).includes(session.status) ? (
        <section className="review-action review-action--pending" role="status">
          <h2>{session.status === "draft" ? "Review not started" : session.status === "queued" ? "Review queued" : "Review in progress"}</h2>
          {session.status !== "draft" ? (
            <>
              <ol className="review-steps">
                {progressSteps.map((step) => (
                  <li className={`review-step review-step--${step.state}`} key={step.label}>
                    {step.state === "active" ? (
                      <span className="spinner" aria-hidden="true" />
                    ) : (
                      <span className="review-step__indicator" aria-hidden="true">
                        {step.state === "complete" ? "✓" : ""}
                      </span>
                    )}
                    <span>{step.label}</span>
                  </li>
                ))}
              </ol>
              <div className="review-activity">
                <div className="review-activity__heading">
                  <span>Live activity</span>
                  <span aria-hidden="true">{formatElapsed(elapsedSeconds)}</span>
                </div>
                <p className="review-activity__current">{currentActivity}</p>
                <div className="review-activity__meta">
                  {session.policy_snapshot_version ? (
                    <span>Policy set v{session.policy_snapshot_version}</span>
                  ) : null}
                  <span>{session.steps.length} {session.steps.length === 1 ? "step" : "steps"} recorded</span>
                </div>
                {recentActivity.length ? (
                  <ul className="review-activity__history">
                    {recentActivity.map((step) => (
                      <li key={step.id}>
                        <span aria-hidden="true">✓</span>
                        {activityLabel(step.name)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="review-activity__waiting">Completed actions will appear here.</p>
                )}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {error ? <div className="alert alert--error" role="alert">{error}</div> : null}
    </section>
  );
}

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [session, setSession] = useState<ComplianceSession | null>(null);
  const [error, setError] = useState("");
  const [changeDecisions, setChangeDecisions] = useState<Record<string, ChangeDecision>>({});

  useEffect(() => {
    let active = true;
    void getSession(id)
      .then((result) => active && setSession(result))
      .catch((cause) => active && setError(cause instanceof ApiError ? cause.message : "Could not load the compliance review."));

    const source = new EventSource(`${API_BASE_URL}/compliance-sessions/${id}/events`);
    source.addEventListener("session", (event) => {
      if (!active) return;
      const next = JSON.parse((event as MessageEvent<string>).data) as ComplianceSession;
      setSession(next);
      setError("");
      if (next.status === "published" || next.status === "failed") {
        source.close();
      }
    });
    return () => {
      active = false;
      source.close();
    };
  }, [id]);

  const sortedFindings = useMemo(
    () =>
      session
        ? [...session.findings].sort((a, b) => {
            const weight = { violation: 0, uncertain: 1, no_violation: 2 };
            return weight[a.status] - weight[b.status];
          })
        : [],
    [session],
  );

  if (error && !session) {
    return (
      <div className="page-shell state-page">
        <div className="state-card">
          <span className="state-card__icon">!</span>
          <h1>We could not load this review.</h1>
          <p>{error}</p>
          <Link className="button button--primary" href="/">Start a new review</Link>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="page-shell loading-page" role="status">
        <span className="spinner" />
        <p>Opening the compliance workspace…</p>
      </div>
    );
  }

  const activeChanges = session.proposed_changes.filter((change) => change.status === "proposed");
  const reviewingChanges = session.status === "waiting_for_approval";
  const reviewIsRunning = runningStatuses.has(session.status);
  const sourcePostingVersionId = activeChanges[0]?.from_posting_version_id;
  const sourcePosting = session.posting_versions.find(
    (version) => version.id === sourcePostingVersionId,
  ) ?? [...session.posting_versions]
    .filter((version) => version.version < session.current_posting_version.version)
    .sort((a, b) => b.version - a.version)[0];
  const displayedPosting = reviewingChanges && sourcePosting
    ? sourcePosting
    : session.current_posting_version;
  const returnedActiveFindings = sortedFindings.filter((finding) => finding.status !== "no_violation");
  const findingsFromChanges = Array.from(
    new Map(
      activeChanges.flatMap((change) =>
        change.policy_keys.map((key) => [
          key,
          {
            id: `change-${key}`,
            policy_key: "",
            policy_title: "",
            category: "",
            status: "violation" as const,
            evidence_text: change.original_text,
            evidence_start: displayedPosting.content.includes(change.original_text)
              ? displayedPosting.content.indexOf(change.original_text)
              : null,
            evidence_end: displayedPosting.content.includes(change.original_text)
              ? displayedPosting.content.indexOf(change.original_text) + change.original_text.length
              : null,
            reason: change.reason,
            confidence: null,
          },
        ] as const),
      ),
    ).values(),
  );
  const activeFindings = returnedActiveFindings.length || !reviewingChanges
    ? returnedActiveFindings
    : findingsFromChanges;

  return (
    <div className="workspace-shell session-page">
      <header className="session-header">
        <div>
          <Link className="back-link" href="/">← New review</Link>
          <h1>{session.title}</h1>
          <p>
            {session.organization_name || "Organization not provided"}
            <span>·</span>
            {session.target_locations.join(", ") || "Location pending"}
            <span>·</span>
            {labelize(session.employment_type)}
          </p>
        </div>
      </header>

      <div className="session-grid">
        <div className="session-document">
          <section className="posting-panel">
            <h2 className="sr-only">{reviewingChanges ? "Flagged posting" : "Current posting"}</h2>
            <div className="posting-toolbar">
              <span className="posting-toolbar__label">
                {reviewingChanges ? "Flagged posting" : "Current posting"}
              </span>
              <div className="version-chip">
                {reviewingChanges || displayedPosting.source !== "agent" ? "Original" : "Draft"}
              </div>
            </div>
            <AnnotatedPosting content={displayedPosting.content} findings={activeFindings} />
          </section>

        </div>

        <aside className="session-sidebar">
          <ReviewPanel session={session} decisions={changeDecisions} onUpdate={setSession} />

          {!reviewIsRunning ? <section className="policy-results" aria-labelledby="policy-results-heading">
            <div className="policy-results__heading">
              <h2 id="policy-results-heading">
                {activeFindings.length ? "Issues found" : "Policy results"}
              </h2>
              {session.findings.length || activeFindings.length ? (
                <span>{reviewingChanges ? `${activeFindings.length} found` : `${session.findings.length} checked`}</span>
              ) : null}
            </div>

            {activeFindings.length ? (
              <div className="policy-result-list">
                {activeFindings.map((finding) => (
                  <article className={`policy-result policy-result--${finding.status}`} key={finding.id}>
                    {finding.policy_title ? <h3>{finding.policy_title}</h3> : null}
                    <p>{finding.reason}</p>
                    {finding.evidence_text ? (
                      <details>
                        <summary>View flagged text</summary>
                        <blockquote>“{finding.evidence_text}”</blockquote>
                      </details>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="policy-results__empty">
                {session.findings.length
                  ? `${session.findings.length} policies passed.`
                  : "Results will appear when the review is complete."}
              </p>
            )}
          </section> : null}

          {reviewingChanges && activeChanges.length ? (
            <ProposedChanges
              changes={activeChanges}
              decisions={changeDecisions}
              onDecision={(changeId, decision) => setChangeDecisions((current) => ({
                ...current,
                [changeId]: decision,
              }))}
            />
          ) : null}
        </aside>
      </div>
    </div>
  );
}
