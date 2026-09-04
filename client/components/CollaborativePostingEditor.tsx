"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";
import {
  ApiError,
  checkSession,
  requestWritingSuggestion,
  savePostingVersion,
} from "@/lib/api";
import { formatDate } from "@/lib/format";
import type {
  ComplianceSession,
  Finding,
  PostingVersion,
  WritingSuggestionResult,
} from "@/lib/types";

type EditorMode = "edit" | "evidence";

function sourceLabel(version: PostingVersion) {
  if (version.source === "agent") return "Agent draft";
  if (version.source === "recruiter" || version.version > 1) return "Recruiter edit";
  return "Original draft";
}

function AnnotatedPosting({ content, findings }: { content: string; findings: Finding[] }) {
  const characters = Array.from(content);
  const annotations = findings
    .filter(
      (finding) =>
        finding.status !== "no_violation" &&
        finding.evidence_start !== null &&
        finding.evidence_end !== null &&
        finding.evidence_start >= 0 &&
        finding.evidence_end <= characters.length &&
        finding.evidence_end > finding.evidence_start,
    )
    .sort((a, b) => (a.evidence_start ?? 0) - (b.evidence_start ?? 0));

  const nodes: ReactNode[] = [];
  let cursor = 0;
  annotations.forEach((finding) => {
    const start = finding.evidence_start ?? 0;
    const end = finding.evidence_end ?? 0;
    if (start < cursor) return;
    nodes.push(characters.slice(cursor, start).join(""));
    nodes.push(
      <mark className={`posting-mark posting-mark--${finding.status}`} key={finding.id} title={finding.policy_title}>
        {characters.slice(start, end).join("")}
      </mark>,
    );
    cursor = end;
  });
  nodes.push(characters.slice(cursor).join(""));

  return <div className="posting-content editor-evidence__content">{nodes}</div>;
}

interface CollaborativePostingEditorProps {
  session: ComplianceSession;
  onUpdate: (session: ComplianceSession) => void;
  onDirtyChange: (dirty: boolean) => void;
}

export function CollaborativePostingEditor({
  session,
  onUpdate,
  onDirtyChange,
}: CollaborativePostingEditorProps) {
  const currentVersion = session.current_posting_version;
  const [mode, setMode] = useState<EditorMode>("edit");
  const [draft, setDraft] = useState(currentVersion.content);
  const [baseContent, setBaseContent] = useState(currentVersion.content);
  const [baseVersionId, setBaseVersionId] = useState(currentVersion.id);
  const [dirty, setDirty] = useState(false);
  const [remoteVersion, setRemoteVersion] = useState<PostingVersion | null>(null);
  const [historyVersionId, setHistoryVersionId] = useState("");
  const [instruction, setInstruction] = useState("");
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const [suggestion, setSuggestion] = useState<WritingSuggestionResult | null>(null);
  const [busy, setBusy] = useState<"save" | "check" | "suggest" | null>(null);
  const [error, setError] = useState("");

  const locked = session.status === "queued" || session.status === "investigating";
  const published = session.status === "published";
  const editable = !locked && !published;
  const canCheck = ["draft", "failed"].includes(session.status) && !dirty && !remoteVersion;
  const selectedCharacters = Array.from(draft.slice(selection.start, selection.end)).length;
  const draftCharacters = Array.from(draft).length;
  const selectionRequired = draftCharacters > 12_000 && selectedCharacters === 0;
  const orderedVersions = [...session.posting_versions].sort((a, b) => b.version - a.version);

  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);

  useEffect(() => {
    if (currentVersion.id === baseVersionId) return;
    if (dirty) {
      setRemoteVersion(currentVersion);
      return;
    }
    setDraft(currentVersion.content);
    setBaseContent(currentVersion.content);
    setBaseVersionId(currentVersion.id);
    setRemoteVersion(null);
    setSuggestion(null);
    setSelection({ start: 0, end: 0 });
  }, [baseVersionId, currentVersion, dirty]);

  useEffect(() => {
    if (!dirty) return;

    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    function warnBeforeLink(event: MouseEvent) {
      const target = event.target as Element | null;
      const link = target?.closest("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target === "_blank" || link.href === window.location.href) return;
      if (!window.confirm("Leave this page? Your latest edits have not been saved.")) {
        event.preventDefault();
        event.stopPropagation();
      }
    }

    window.addEventListener("beforeunload", warnBeforeUnload);
    document.addEventListener("click", warnBeforeLink, true);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      document.removeEventListener("click", warnBeforeLink, true);
    };
  }, [dirty]);

  useEffect(() => {
    function saveWithKeyboard(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (editable && dirty && !remoteVersion && busy === null) void saveDraft();
      }
    }
    window.addEventListener("keydown", saveWithKeyboard);
    return () => window.removeEventListener("keydown", saveWithKeyboard);
  });

  function syncToVersion(version: PostingVersion) {
    setDraft(version.content);
    setBaseContent(version.content);
    setBaseVersionId(version.id);
    setDirty(false);
    setRemoteVersion(null);
    setSuggestion(null);
    setSelection({ start: 0, end: 0 });
  }

  function updateDraft(value: string) {
    setDraft(value);
    setDirty(value !== baseContent);
    setSuggestion(null);
  }

  async function saveDraft() {
    if (!editable || !dirty || remoteVersion || draft.trim().length < 30) return;
    setBusy("save");
    setError("");
    try {
      const next = await savePostingVersion(session.id, {
        base_version_id: baseVersionId,
        content: draft,
      });
      syncToVersion(next.current_posting_version);
      onUpdate(next);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not save this draft.");
    } finally {
      setBusy(null);
    }
  }

  async function runCheck() {
    if (!canCheck) return;
    setBusy("check");
    setError("");
    try {
      onUpdate(await checkSession(session.id, baseVersionId));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not start the compliance check.");
    } finally {
      setBusy(null);
    }
  }

  async function getSuggestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !editable ||
      remoteVersion ||
      draftCharacters < 30 ||
      draftCharacters > 20_000 ||
      selectionRequired
    ) return;
    setBusy("suggest");
    setError("");
    setSuggestion(null);
    try {
      const hasSelection = selection.end > selection.start;
      const selectionStart = Array.from(draft.slice(0, selection.start)).length;
      const selectionEnd = Array.from(draft.slice(0, selection.end)).length;
      const result = await requestWritingSuggestion(session.id, {
        base_version_id: baseVersionId,
        draft_text: draft,
        instruction,
        ...(hasSelection
          ? { selection_start: selectionStart, selection_end: selectionEnd }
          : {}),
      });
      if (result.base_version_id !== baseVersionId) {
        setError("The saved draft changed while the suggestion was running. Try again.");
      } else {
        setSuggestion(result);
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create a writing suggestion.");
    } finally {
      setBusy(null);
    }
  }

  function loadRemoteVersion() {
    if (!remoteVersion) return;
    syncToVersion(remoteVersion);
  }

  function keepLocalDraft() {
    if (!remoteVersion) return;
    setBaseContent(remoteVersion.content);
    setBaseVersionId(remoteVersion.id);
    setDirty(draft !== remoteVersion.content);
    setRemoteVersion(null);
    setSuggestion(null);
  }

  function loadHistoryVersion() {
    const historicalVersion = session.posting_versions.find((version) => version.id === historyVersionId);
    if (!historicalVersion || historicalVersion.id === currentVersion.id || !editable) return;
    if (dirty && !window.confirm("Replace your unsaved edits with this older version?")) return;
    setDraft(historicalVersion.content);
    setBaseContent(currentVersion.content);
    setBaseVersionId(currentVersion.id);
    setDirty(historicalVersion.content !== currentVersion.content);
    setRemoteVersion(null);
    setSuggestion(null);
    setSelection({ start: 0, end: 0 });
    setMode("edit");
    setHistoryVersionId("");
  }

  function acceptSuggestion() {
    if (!suggestion) return;
    updateDraft(suggestion.suggested_text);
    setSelection({ start: 0, end: 0 });
    setSuggestion(null);
  }

  function discardDraft() {
    if (!dirty || !window.confirm("Discard your unsaved changes?")) return;
    syncToVersion(currentVersion);
    setError("");
  }

  const saveHelp = published
    ? "Published postings are read-only."
      : locked
      ? "Editing is paused while the compliance agent is running."
      : session.status === "failed"
        ? "The last check stopped. You can retry this saved draft."
      : remoteVersion
        ? "Resolve the newer server version before saving."
        : dirty
          ? "Save this version before you run a compliance check."
          : session.check_state === "stale"
            ? "This draft changed after the last check. Run compliance again when ready."
            : session.status === "draft"
              ? "This draft is saved and ready for a compliance check."
            : "Save an edit to return this review to draft before running a new check.";

  return (
    <section className="posting-panel collaborative-editor" aria-label="Job posting editor">
      <div className="panel-heading editor-heading">
        <div>
          <p className="kicker">Current posting</p>
          <h2>{session.title}</h2>
        </div>
        <div className="editor-heading__tools">
          <span className={dirty ? "save-state save-state--dirty" : "save-state"} aria-live="polite">
            <i /> {dirty ? "Unsaved changes" : "Saved"}
          </span>
          <span className="version-chip">
            Version {currentVersion.version} · {sourceLabel(currentVersion)}
          </span>
        </div>
      </div>

      <div className="editor-toolbar">
        <div className="mode-switch" role="group" aria-label="Posting view">
          <button className={mode === "edit" ? "active" : ""} type="button" aria-pressed={mode === "edit"} onClick={() => setMode("edit")}>Edit</button>
          <button className={mode === "evidence" ? "active" : ""} type="button" aria-pressed={mode === "evidence"} onClick={() => setMode("evidence")}>Evidence</button>
        </div>
        <div className="history-control">
          <label htmlFor="posting-history">Version history</label>
          <select id="posting-history" value={historyVersionId} onChange={(event) => setHistoryVersionId(event.target.value)}>
            <option value="">Choose a version</option>
            {orderedVersions.map((version) => (
              <option value={version.id} key={version.id}>
                v{version.version} · {sourceLabel(version)} · {formatDate(version.created_at)}
              </option>
            ))}
          </select>
          <button
            className="button button--quiet button--compact"
            type="button"
            disabled={!editable || !historyVersionId || historyVersionId === currentVersion.id}
            onClick={loadHistoryVersion}
          >
            Load as draft
          </button>
        </div>
      </div>

      <div className="posting-meta">
        <span>{session.employment_type.replaceAll("_", " ")}</span>
        {session.target_locations.map((location) => <span key={location}>{location}</span>)}
      </div>

      {remoteVersion ? (
        <div className="editor-conflict" role="alert">
          <div>
            <strong>A newer version arrived.</strong>
            <p>Your unsaved text is still here. Choose which text to continue with.</p>
          </div>
          <div className="button-row">
            <button className="button button--secondary" type="button" onClick={loadRemoteVersion}>Load newer</button>
            <button className="button button--primary" type="button" onClick={keepLocalDraft}>Keep mine</button>
          </div>
        </div>
      ) : null}

      {mode === "edit" ? (
        <div className="editor-surface">
          <label className="field editor-textarea">
            <span className="sr-only">Job posting text</span>
            <textarea
              required
              minLength={30}
              maxLength={100000}
              value={draft}
              readOnly={!editable || busy === "suggest"}
              aria-describedby="editor-status"
              onChange={(event) => updateDraft(event.target.value)}
              onSelect={(event) => setSelection({
                start: event.currentTarget.selectionStart,
                end: event.currentTarget.selectionEnd,
              })}
            />
          </label>
          <div className="editor-textarea__footer" id="editor-status">
            <span>{draft.length.toLocaleString()} characters</span>
            <span>{selectedCharacters ? `${selectedCharacters.toLocaleString()} selected` : "No text selected"}</span>
          </div>

          {editable ? (
            <form className="writing-assistant" onSubmit={getSuggestion}>
              <div className="writing-assistant__heading">
                <div>
                  <p className="kicker">Writing assistant</p>
                  <h3>Ask for one focused change</h3>
                </div>
                <span>{selectedCharacters ? "Uses selected text" : "Uses full draft"}</span>
              </div>
              <div className="writing-assistant__request">
                <label className="field">
                  <span className="sr-only">Writing instruction</span>
                  <input
                    required
                    minLength={3}
                    maxLength={2000}
                    value={instruction}
                    onChange={(event) => setInstruction(event.target.value)}
                    placeholder="Make the responsibilities clearer and more direct."
                  />
                </label>
                <button
                  className="button button--secondary"
                  disabled={
                    busy !== null ||
                    draftCharacters < 30 ||
                    draftCharacters > 20_000 ||
                    selectionRequired
                  }
                >
                  {busy === "suggest" ? "Working…" : "Preview suggestion"}
                </button>
              </div>
              {selectedCharacters ? (
                <p className="writing-assistant__selection">
                  “{draft.slice(selection.start, selection.end).slice(0, 220)}{selectedCharacters > 220 ? "…" : ""}”
                </p>
              ) : null}
              {draftCharacters < 30 ? <p className="field-note field-note--warning">Add at least 30 characters before asking for a suggestion.</p> : null}
              {draftCharacters > 20_000 ? <p className="field-note field-note--warning">Writing suggestions support drafts up to 20,000 characters.</p> : null}
              {selectionRequired ? <p className="field-note field-note--warning">Select a passage when the full draft is longer than 12,000 characters.</p> : null}
            </form>
          ) : null}

          {suggestion ? (
            <div className="suggestion-preview" aria-live="polite">
              <div className="suggestion-preview__heading">
                <div>
                  <p className="kicker">Suggestion preview</p>
                  <h3>{suggestion.summary}</h3>
                </div>
                <span>{suggestion.suggested_text.length.toLocaleString()} characters</span>
              </div>
              <div className="suggestion-preview__text">{suggestion.suggested_text}</div>
              <div className="button-row">
                <button className="button button--primary" type="button" onClick={acceptSuggestion}>Accept suggestion</button>
                <button className="button button--secondary" type="button" onClick={() => setSuggestion(null)}>Reject</button>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="editor-evidence">
          {dirty ? <p className="editor-evidence__notice">Evidence applies to the latest saved draft, not your unsaved edits.</p> : null}
          <AnnotatedPosting content={currentVersion.content} findings={session.findings} />
        </div>
      )}

      {error ? <div className="alert alert--error" role="alert">{error}</div> : null}

      <div className="editor-actions">
        <div>
          <strong>{saveHelp}</strong>
          <p>{dirty ? "Cmd/Ctrl+S also saves this draft." : `Version ${currentVersion.version} is the latest server version.`}</p>
        </div>
        <div className="button-row">
          <button
            className="button button--quiet"
            type="button"
            disabled={!editable || !dirty || busy !== null}
            onClick={discardDraft}
          >
            Discard
          </button>
          <button
            className="button button--secondary"
            type="button"
            disabled={!editable || !dirty || Boolean(remoteVersion) || busy !== null || draft.trim().length < 30}
            onClick={() => void saveDraft()}
          >
            {busy === "save" ? "Saving…" : "Save draft"}
          </button>
          <button
            className="button button--primary"
            type="button"
            disabled={!canCheck || busy !== null}
            onClick={() => void runCheck()}
          >
            {busy === "check" ? "Starting check…" : session.status === "failed" ? "Retry check" : "Check latest draft"}
          </button>
        </div>
      </div>
    </section>
  );
}
