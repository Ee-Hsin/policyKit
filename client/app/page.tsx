"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, createAssistedDraft, createSession } from "@/lib/api";

type StartMode = "ideas" | "paste";

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20">
      <path d="M4 10h12m-5-5 5 5-5 5" />
    </svg>
  );
}

function IdeasIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M9.2 17.5h5.6M10 21h4M8.3 14.5A6.3 6.3 0 1 1 15.7 14.5c-.9.7-1.3 1.4-1.3 2H9.6c0-.6-.4-1.3-1.3-2Z" />
      <path d="M12 2V.8M4.9 4.9 4 4M19.1 4.9 20 4" />
    </svg>
  );
}

function PasteIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M9 5.5H6.8A1.8 1.8 0 0 0 5 7.3v12A1.8 1.8 0 0 0 6.8 21h10.4a1.8 1.8 0 0 0 1.8-1.8V7.3a1.8 1.8 0 0 0-1.8-1.8H15" />
      <path d="M9 3h6v5H9zM9 12h6M9 16h6" />
    </svg>
  );
}

export default function NewPostingPage() {
  const router = useRouter();
  const [mode, setMode] = useState<StartMode>("ideas");
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [locations, setLocations] = useState("");
  const [employmentType, setEmploymentType] = useState("full_time");
  const [roleIdeas, setRoleIdeas] = useState("");
  const [content, setContent] = useState("");
  const [draftReady, setDraftReady] = useState(false);
  const [generatedFrom, setGeneratedFrom] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"draft" | "workspace" | null>(null);

  const targetLocations = locations
    .split(",")
    .map((location) => location.trim())
    .filter(Boolean);
  const generationKey = JSON.stringify({
    title,
    organization,
    targetLocations,
    employmentType,
    roleIdeas,
  });
  const generationStale = mode === "ideas" && draftReady && generatedFrom !== generationKey;

  function chooseMode(nextMode: StartMode) {
    setMode(nextMode);
    setError("");
  }

  async function generateDraft() {
    setBusy("draft");
    setError("");
    try {
      const result = await createAssistedDraft({
        title,
        role_ideas: roleIdeas,
        organization_name: organization || undefined,
        target_locations: targetLocations,
        employment_type: employmentType,
      });
      setContent(result.suggested_content);
      setDraftReady(true);
      setGeneratedFrom(generationKey);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create a draft.");
    } finally {
      setBusy(null);
    }
  }

  async function openWorkspace() {
    setBusy("workspace");
    setError("");
    try {
      const session = await createSession({
        title,
        job_description: content,
        organization_name: organization || undefined,
        target_locations: targetLocations,
        employment_type: employmentType,
        platform: "policykit",
      });
      router.push(`/sessions/${session.id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not open the workspace.");
      setBusy(null);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "ideas" && (!draftReady || generationStale)) {
      void generateDraft();
      return;
    }
    void openWorkspace();
  }

  const editorVisible = mode === "paste" || draftReady;

  return (
    <div className="start-shell">
      <section className="start-intro motion-reveal" aria-labelledby="start-heading">
        <p className="signal-label signal-label--ink"><span /> Job posting workspace</p>
        <h1 id="start-heading">Create a clear job post. Check it before it goes live.</h1>
        <p>
          Start with a few ideas or bring a complete posting. You control every draft and decide
          when compliance checks run.
        </p>
      </section>

      <section className="start-card motion-reveal" aria-label="Create a job posting">
        <div className="start-methods" role="group" aria-label="Choose how to start">
          <button
            className={mode === "ideas" ? "start-method start-method--active" : "start-method"}
            type="button"
            disabled={busy !== null}
            aria-pressed={mode === "ideas"}
            onClick={() => chooseMode("ideas")}
          >
            <span className="start-method__icon"><IdeasIcon /></span>
            <span><strong>Start from ideas</strong><small>Use AI to turn role notes into an editable first draft.</small></span>
          </button>
          <button
            className={mode === "paste" ? "start-method start-method--active" : "start-method"}
            type="button"
            disabled={busy !== null}
            aria-pressed={mode === "paste"}
            onClick={() => chooseMode("paste")}
          >
            <span className="start-method__icon"><PasteIcon /></span>
            <span><strong>Paste a posting</strong><small>Open your draft without an AI call.</small></span>
          </button>
        </div>

        <form className="start-form" onSubmit={submit}>
          <div className="form-grid form-grid--two">
            <label className="field">
              <span>Job title</span>
              <input
                required
                disabled={busy !== null}
                minLength={2}
                maxLength={240}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Senior Product Designer"
              />
            </label>
            <label className="field">
              <span>Organization <em>Optional</em></span>
              <input
                maxLength={240}
                disabled={busy !== null}
                value={organization}
                onChange={(event) => setOrganization(event.target.value)}
                placeholder="Acme, Inc."
              />
            </label>
            <label className="field">
              <span>Hiring locations <em>Optional</em></span>
              <input
                disabled={busy !== null}
                value={locations}
                onChange={(event) => setLocations(event.target.value)}
                placeholder="New York, California"
                aria-describedby="location-help"
              />
              <small id="location-help">Separate locations with commas.</small>
            </label>
            <label className="field">
              <span>Employment type</span>
              <select disabled={busy !== null} value={employmentType} onChange={(event) => setEmploymentType(event.target.value)}>
                <option value="full_time">Full-time</option>
                <option value="part_time">Part-time</option>
                <option value="contract">Contract</option>
                <option value="temporary">Temporary</option>
                <option value="internship">Internship</option>
              </select>
            </label>
          </div>

          {mode === "ideas" ? (
            <label className="field start-form__main-field">
              <span>What should this person do?</span>
              <textarea
                required
                disabled={busy !== null}
                minLength={10}
                maxLength={5000}
                value={roleIdeas}
                onChange={(event) => setRoleIdeas(event.target.value)}
                placeholder="Describe the main responsibilities, skills, team, and outcomes. Notes and fragments are fine."
              />
              <small>{roleIdeas.length.toLocaleString()} of 5,000 characters</small>
            </label>
          ) : null}

          {editorVisible ? (
            <label className="field start-form__draft">
              <span>{mode === "ideas" ? "Generated draft" : "Job posting"}</span>
              <textarea
                required
                minLength={30}
                maxLength={100000}
                readOnly={busy !== null}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="Paste the full job posting here."
              />
              <small>Review and edit this text before opening the workspace.</small>
            </label>
          ) : null}

          {error ? <div className="alert alert--error" role="alert">{error}</div> : null}

          <div className="start-form__actions">
            <p>
              {editorVisible
                ? generationStale
                  ? "Your role details changed. Regenerate the draft, or keep the current text if that was intentional."
                  : "Opening a workspace saves this as version 1. No compliance check runs until you request one."
                : "The writing model creates a draft only. You can edit it before any policy check."}
            </p>
            <div className="button-row">
              {mode === "ideas" && draftReady ? (
                <button
                  className="button button--secondary"
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void (generationStale ? openWorkspace() : generateDraft())}
                >
                  {busy === "draft"
                    ? "Generating…"
                    : generationStale
                      ? "Keep current draft"
                      : "Regenerate draft"}
                </button>
              ) : null}
              <button className="button button--primary button--large" disabled={busy !== null}>
                {busy === "draft"
                  ? "Generating draft…"
                  : busy === "workspace"
                    ? "Opening workspace…"
                    : mode === "ideas" && (!draftReady || generationStale)
                      ? generationStale
                        ? "Regenerate with updates"
                        : "Generate draft"
                      : "Open workspace"}
                <ArrowIcon />
              </button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
