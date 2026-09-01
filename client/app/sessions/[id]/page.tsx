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
import { formatDate, formatDuration, labelize } from "@/lib/format";
import type { ComplianceSession, Finding, SessionStatus } from "@/lib/types";

const reviewStages = ["Draft", "Investigation", "Approval", "Ready"];

function stageForStatus(status: SessionStatus) {
  if (["draft", "queued", "investigating", "waiting_for_information", "needs_review", "failed"].includes(status)) return status === "draft" ? 0 : 1;
  if (["changes_proposed", "waiting_for_approval"].includes(status)) return 2;
  return 3;
}

function statusTone(status: SessionStatus) {
  if (status === "ready_to_publish" || status === "published") return "success";
  if (status === "failed") return "danger";
  if (status === "waiting_for_information" || status === "waiting_for_approval" || status === "needs_review") return "warning";
  return "active";
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

function AgentPanel({ session, onUpdate }: { session: ComplianceSession; onUpdate: (next: ComplianceSession) => void }) {
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<ComplianceSession>) {
    setBusy(true);
    setError("");
    try {
      onUpdate(await action());
      setMessage("");
      setNotes("");
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

  const activeChanges = session.proposed_changes.filter((change) => change.status === "proposed");
  const recentSteps = [...session.steps].sort((a, b) => b.sequence - a.sequence).slice(0, 5);

  return (
    <aside className="agent-panel" aria-label="Compliance agent">
      <div className="agent-panel__header">
        <div className="agent-avatar" aria-hidden="true">P</div>
        <div>
          <p className="kicker">Compliance agent</p>
          <h2>{session.status === "published" ? "Review complete" : "Working toward approval"}</h2>
        </div>
        {(["queued", "investigating"] as SessionStatus[]).includes(session.status) ? (
          <span className="live-indicator"><i /> Live</span>
        ) : null}
      </div>

      {session.status === "waiting_for_information" ? (
        <div className="agent-callout agent-callout--question">
          <p className="kicker">Information needed</p>
          <h3>{session.current_question}</h3>
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
        </div>
      ) : null}

      {session.status === "waiting_for_approval" ? (
        <div className="agent-callout">
          <p className="kicker">Your approval</p>
          <h3>{activeChanges.length} proposed {activeChanges.length === 1 ? "change" : "changes"}</h3>
          <div className="change-list">
            {activeChanges.map((change) => (
              <article className="change-card" key={change.id}>
                <div className="change-card__before">− {change.original_text}</div>
                <div className="change-card__after">+ {change.replacement_text}</div>
                <p>{change.reason}</p>
                <div className="tag-row">
                  {change.policy_keys.map((key) => <span className="tag" key={key}>{key}</span>)}
                </div>
              </article>
            ))}
          </div>
          <label className="field">
            <span>Review note <em>Optional</em></span>
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Add context for the agent…" />
          </label>
          <div className="button-row">
            <button className="button button--primary" disabled={busy} onClick={() => void run(() => approveRevision(session.id, true, notes))}>
              Approve changes
            </button>
            <button className="button button--secondary" disabled={busy} onClick={() => void run(() => approveRevision(session.id, false, notes))}>
              Request revision
            </button>
          </div>
        </div>
      ) : null}

      {session.status === "ready_to_publish" ? (
        <div className="agent-callout agent-callout--success">
          <span className="success-icon" aria-hidden="true">✓</span>
          <p className="kicker">All checks complete</p>
          <h3>This posting is ready to publish.</h3>
          <p>Every applicable policy was checked, and no unresolved findings remain.</p>
          <button className="button button--primary button--full" disabled={busy} onClick={() => void run(() => publishSession(session.id))}>
            {busy ? "Publishing…" : "Publish posting"}
          </button>
        </div>
      ) : null}

      {session.status === "published" ? (
        <div className="agent-callout agent-callout--success">
          <span className="success-icon" aria-hidden="true">✓</span>
          <p className="kicker">Published</p>
          <h3>The approved posting is live.</h3>
          <p>PolicyKit saved the policy snapshot, review activity, and final posting version.</p>
          <Link className="button button--secondary button--full" href="/">Review another posting</Link>
        </div>
      ) : null}

      {session.status === "needs_review" || session.status === "failed" ? (
        <div className="agent-callout agent-callout--warning">
          <p className="kicker">{session.status === "failed" ? "Review stopped" : "Human review required"}</p>
          <h3>{session.error_message ?? "The agent could not reach a safe decision."}</h3>
          <p>No posting was published. A reviewer can inspect the evidence and decide what happens next.</p>
        </div>
      ) : null}

      {(["queued", "investigating", "changes_proposed"] as SessionStatus[]).includes(session.status) ? (
        <div className="agent-thinking">
          <span className="agent-thinking__orb"><i /><i /><i /></span>
          <div>
            <strong>{session.status === "queued" ? "Preparing the next step" : "Investigating this posting"}</strong>
            <p>Updates appear here as the agent uses its compliance tools.</p>
          </div>
        </div>
      ) : null}

      {error ? <div className="alert alert--error" role="alert">{error}</div> : null}

      <div className="activity">
        <div className="activity__heading">
          <h3>Activity</h3>
          <span>{session.steps.length} events</span>
        </div>
        {recentSteps.length ? (
          <ol className="activity-list">
            {recentSteps.map((step) => (
              <li key={step.id}>
                <span className={`activity-list__icon activity-list__icon--${step.status}`} aria-hidden="true">
                  {step.status === "failed" ? "!" : "✓"}
                </span>
                <div>
                  <strong>{step.name}</strong>
                  <p>
                    {formatDate(step.created_at)}
                    {formatDuration(step.duration_ms) ? ` · ${formatDuration(step.duration_ms)}` : ""}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty-copy">The first activity will appear when the agent begins.</p>
        )}
      </div>
    </aside>
  );
}

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [session, setSession] = useState<ComplianceSession | null>(null);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let active = true;
    void getSession(id)
      .then((result) => active && setSession(result))
      .catch((cause) => active && setError(cause instanceof ApiError ? cause.message : "Could not load the compliance review."));

    const source = new EventSource(`${API_BASE_URL}/compliance-sessions/${id}/events`);
    source.addEventListener("session", (event) => {
      if (!active) return;
      setSession(JSON.parse((event as MessageEvent<string>).data) as ComplianceSession);
      setConnected(true);
      setError("");
    });
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

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

  const activeStage = stageForStatus(session.status);
  const activeFindings = sortedFindings.filter((finding) => finding.status !== "no_violation");

  return (
    <div className="workspace-shell">
      <div className="workspace-topbar">
        <div>
          <Link className="back-link" href="/">← New review</Link>
          <div className="title-line">
            <h1>{session.title}</h1>
            <span className={`status-pill status-pill--${statusTone(session.status)}`}>{labelize(session.status)}</span>
          </div>
          <p>
            {session.organization_name || "Organization not provided"}
            <span>·</span>
            {session.target_locations.join(", ") || "Location pending"}
            <span>·</span>
            Policy set v{session.policy_snapshot_version ?? "—"}
          </p>
        </div>
        <div className={`connection-state ${connected ? "connection-state--online" : ""}`}>
          <i /> {connected ? "Live updates" : "Reconnecting"}
        </div>
      </div>

      <ol className="progress-rail" aria-label="Compliance review progress">
        {reviewStages.map((stage, index) => (
          <li className={index < activeStage ? "complete" : index === activeStage ? "active" : ""} key={stage}>
            <span>{index < activeStage ? "✓" : index + 1}</span>
            <strong>{stage}</strong>
          </li>
        ))}
      </ol>

      <div className="workspace-grid">
        <section className="posting-panel">
          <div className="panel-heading">
            <div>
              <p className="kicker">Current posting</p>
              <h2>{session.title}</h2>
            </div>
            <div className="version-chip">
              Version {session.current_posting_version.version}
              {session.current_posting_version.source === "agent" ? " · Agent draft" : " · Original"}
            </div>
          </div>
          <div className="posting-meta">
            <span>{labelize(session.employment_type)}</span>
            {session.target_locations.map((location) => <span key={location}>{location}</span>)}
          </div>
          <AnnotatedPosting content={session.current_posting_version.content} findings={session.findings} />
        </section>

        <AgentPanel session={session} onUpdate={setSession} />
      </div>

      <section className="findings-section">
        <div className="section-heading">
          <div>
            <p className="kicker">Policy coverage</p>
            <h2>{activeFindings.length ? `${activeFindings.length} findings need attention` : "No active findings"}</h2>
          </div>
          <div className="coverage-summary">
            <strong>{session.findings.length}</strong> policies assessed
          </div>
        </div>
        {session.findings.length ? (
          <div className="findings-grid">
            {sortedFindings.map((finding) => (
              <article className={`finding-card finding-card--${finding.status}`} key={finding.id}>
                <div className="finding-card__top">
                  <span className={`finding-status finding-status--${finding.status}`}>{labelize(finding.status)}</span>
                  <span className="policy-key">{finding.policy_key}</span>
                </div>
                <h3>{finding.policy_title}</h3>
                <p>{finding.reason}</p>
                {finding.evidence_text ? <blockquote>“{finding.evidence_text}”</blockquote> : null}
                <div className="finding-card__footer">
                  <span>{labelize(finding.category)}</span>
                  {finding.confidence !== null ? <span>{Math.round(finding.confidence * 100)}% confidence</span> : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <span className="spinner spinner--small" />
            <p>Policy assessments will appear after the agent runs the full compliance check.</p>
          </div>
        )}
      </section>
    </div>
  );
}
