"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PanelIcon } from "@/components/PanelIcon";
import { PolicyForm } from "@/components/PolicyForm";
import {
  ApiError,
  createPolicyVersion,
  getPolicy,
  publishPolicy,
  testPolicy,
  updatePolicyDraft,
} from "@/lib/api";
import { formatDate, labelize } from "@/lib/format";
import type { PolicyDetail, PolicyDraftInput, PolicyVersion } from "@/lib/types";

function ReadOnlyVersion({ version }: { version: PolicyVersion }) {
  return (
    <div className="policy-readonly">
      <section className="admin-card">
        <div className="admin-card__heading">
          <PanelIcon kind="rule" />
          <div><p className="kicker">Decision standard</p><h2>Policy rule</h2></div>
        </div>
        <p className="rule-copy">{version.rule_text}</p>
        <div className="definition-grid">
          <div><span>Rationale</span><p>{version.rationale || "Not provided"}</p></div>
          <div><span>Recommended remediation</span><p>{version.remediation || "Not provided"}</p></div>
        </div>
      </section>
      <section className="admin-card">
        <div className="admin-card__heading">
          <PanelIcon kind="scope" />
          <div><p className="kicker">Scope and guidance</p><h2>Application details</h2></div>
        </div>
        <div className="definition-grid definition-grid--three">
          <div><span>Jurisdictions</span><div className="tag-row">{version.jurisdictions.map((item) => <span className="tag" key={item}>{item}</span>)}</div></div>
          <div><span>Employment types</span><p>{version.employment_types.map(labelize).join(", ") || "All types"}</p></div>
          <div><span>Platforms</span><p>{version.platforms.join(", ") || "All platforms"}</p></div>
          <div><span>Violation examples</span>{version.violation_examples.length ? <ul>{version.violation_examples.map((item) => <li key={item}>{item}</li>)}</ul> : <p>None</p>}</div>
          <div><span>Compliant examples</span>{version.compliant_examples.length ? <ul>{version.compliant_examples.map((item) => <li key={item}>{item}</li>)}</ul> : <p>None</p>}</div>
          <div><span>Exceptions</span>{version.exceptions.length ? <ul>{version.exceptions.map((item) => <li key={item}>{item}</li>)}</ul> : <p>None</p>}</div>
        </div>
      </section>
    </div>
  );
}

export default function PolicyDetailPage() {
  const params = useParams<{ id: string }>();
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [testText, setTestText] = useState("");
  const [testResult, setTestResult] = useState<Awaited<ReturnType<typeof testPolicy>> | null>(null);

  useEffect(() => {
    void getPolicy(params.id)
      .then((result) => {
        setPolicy(result);
        const draft = [...result.versions].reverse().find((version) => version.status === "draft");
        const latest = [...result.versions].sort((a, b) => b.version - a.version)[0];
        setSelectedVersionId((draft ?? latest).id);
      })
      .catch((cause) => setError(cause instanceof ApiError ? cause.message : "Could not load the policy."))
      .finally(() => setLoading(false));
  }, [params.id]);

  const versions = useMemo(() => policy ? [...policy.versions].sort((a, b) => b.version - a.version) : [], [policy]);
  const selected = versions.find((version) => version.id === selectedVersionId) ?? versions[0];
  const hasDraft = versions.some((version) => version.status === "draft");

  async function save(input: PolicyDraftInput) {
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await updatePolicyDraft(params.id, selected.id, input);
      setPolicy(result);
      setNotice("Draft saved.");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not save the draft.");
    } finally {
      setBusy(false);
    }
  }

  async function createDraft() {
    setBusy(true);
    setError("");
    try {
      const result = await createPolicyVersion(params.id);
      setPolicy(result);
      const draft = result.versions.find((version) => version.status === "draft");
      if (draft) setSelectedVersionId(draft.id);
      setNotice("New draft created from the current policy.");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create a draft.");
    } finally {
      setBusy(false);
    }
  }

  async function runTest(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    setTestResult(null);
    try {
      setTestResult(await testPolicy(params.id, selected.id, testText));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not test the policy.");
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!selected || !window.confirm(`Publish ${policy?.key} version ${selected.version}? Published versions cannot be edited.`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await publishPolicy(params.id, selected.id);
      setPolicy(result.policy);
      setNotice(`Version ${selected.version} published in policy snapshot ${result.snapshot_version}. Chroma index: ${result.index_status}.`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not publish the policy.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="page-shell loading-page"><span className="spinner" /><p>Loading policy…</p></div>;
  if (!policy || !selected) {
    return <div className="page-shell state-page"><div className="state-card"><span className="state-card__icon">!</span><h1>Policy unavailable</h1><p>{error || "This policy could not be found."}</p><Link className="button button--primary" href="/admin/policies">Back to policies</Link></div></div>;
  }

  return (
    <div className="page-shell admin-shell admin-shell--editor">
      <div className="editor-header">
        <div>
          <Link className="back-link" href="/admin/policies">← All policies</Link>
          <p className="kicker">{policy.key} · {labelize(policy.category)}</p>
          <h1>{policy.title}</h1>
          <p>Inspect prior versions, test a draft, and publish a new immutable policy snapshot.</p>
        </div>
        <div className="editor-header__actions">
          {!hasDraft ? <button className="button button--secondary" disabled={busy} onClick={() => void createDraft()}>+ Create new version</button> : null}
          {selected.status === "draft" ? <button className="button button--primary" disabled={busy} onClick={() => void publish()}>Publish version</button> : null}
        </div>
      </div>

      <div className="version-bar">
        <div>
          <label htmlFor="policy-version">Viewing</label>
          <select id="policy-version" value={selected.id} onChange={(event) => { setSelectedVersionId(event.target.value); setTestResult(null); setNotice(""); }}>
            {versions.map((version) => <option value={version.id} key={version.id}>Version {version.version} · {labelize(version.status)}</option>)}
          </select>
        </div>
        <div className="version-bar__meta">
          <span className={`status-pill status-pill--${selected.status === "published" ? "success" : "warning"}`}>{labelize(selected.status)}</span>
          <span className={`index-label index-label--${selected.index_status}`}>Chroma: {labelize(selected.index_status)}</span>
          <span>Updated {formatDate(selected.updated_at)}</span>
        </div>
      </div>

      {error ? <div className="alert alert--error" role="alert">{error}</div> : null}
      {notice ? <div className="alert alert--success" role="status">{notice}</div> : null}

      {selected.status === "draft" ? (
        <PolicyForm
          key={selected.id}
          initial={selected}
          initialTitle={policy.title}
          initialCategory={policy.category}
          policyKey={policy.key}
          submitting={busy}
          submitLabel="Save draft"
          onSubmit={(input) => save(input as PolicyDraftInput)}
        />
      ) : <ReadOnlyVersion version={selected} />}

      <section className="admin-card test-card">
        <div className="admin-card__heading">
          <PanelIcon kind="test" />
          <div><p className="kicker">Model check</p><h2>Test this policy version</h2></div>
        </div>
        <p>Try a sample job-posting excerpt before publication. Testing does not modify the policy.</p>
        <form onSubmit={runTest}>
          <label className="field">
            <span>Job-posting excerpt</span>
            <textarea required minLength={20} value={testText} onChange={(event) => setTestText(event.target.value)} placeholder="Paste at least 20 characters to see how the policy is assessed…" />
          </label>
          <button className="button button--secondary" disabled={busy || testText.length < 20}>{busy ? "Running…" : "Run policy test"}</button>
        </form>
        {testResult ? (
          <div className={`test-result test-result--${testResult.status}`}>
            <div><span className={`finding-status finding-status--${testResult.status}`}>{labelize(testResult.status)}</span>{testResult.confidence !== null ? <strong>{Math.round(testResult.confidence * 100)}% confidence</strong> : null}</div>
            <p>{testResult.reason}</p>
            {testResult.evidence_text ? <blockquote>“{testResult.evidence_text}”</blockquote> : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
