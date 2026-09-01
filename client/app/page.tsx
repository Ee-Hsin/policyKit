"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, createSession } from "@/lib/api";

const samplePosting = `Join Northstar Labs as a Senior Software Engineer and help build tools used by growing teams. You will design backend services, partner with product and design, and mentor engineers across the company.

We are looking for a recent college graduate with 5+ years of professional software development experience. The ideal candidate is young, energetic, and able to move quickly in a fast-paced environment.

This is a full-time role. We offer competitive compensation and comprehensive benefits.`;

export default function NewReviewPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [locations, setLocations] = useState("");
  const [employmentType, setEmploymentType] = useState("full_time");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const session = await createSession({
        title,
        job_description: description,
        organization_name: organization || undefined,
        target_locations: locations
          .split(",")
          .map((location) => location.trim())
          .filter(Boolean),
        employment_type: employmentType,
        platform: "policykit",
      });
      router.push(`/sessions/${session.id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not start the review.");
      setSubmitting(false);
    }
  }

  function loadExample() {
    setTitle("Senior Software Engineer");
    setOrganization("Northstar Labs");
    setLocations("New York, California");
    setDescription(samplePosting);
  }

  return (
    <div className="page-shell landing">
      <section className="hero">
        <div className="eyebrow">
          <span className="eyebrow__dot" /> Pre-publication compliance
        </div>
        <h1>Move every job post from draft to ready.</h1>
        <p>
          PolicyKit investigates platform requirements, highlights risky language, and proposes
          clear edits before a listing goes live.
        </p>
        <div className="hero__proof" aria-label="Review process">
          <span>01&nbsp; Analyze</span>
          <i aria-hidden="true" />
          <span>02&nbsp; Resolve</span>
          <i aria-hidden="true" />
          <span>03&nbsp; Approve</span>
        </div>
      </section>

      <section className="composer-card" aria-labelledby="review-heading">
        <div className="section-heading">
          <div>
            <p className="kicker">New compliance review</p>
            <h2 id="review-heading">Tell us about the role</h2>
          </div>
          <button className="button button--quiet" type="button" onClick={loadExample}>
            Use an example
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-grid form-grid--two">
            <label className="field">
              <span>Job title</span>
              <input
                required
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
                value={organization}
                onChange={(event) => setOrganization(event.target.value)}
                placeholder="Acme, Inc."
              />
            </label>
            <label className="field">
              <span>Hiring locations</span>
              <input
                required
                value={locations}
                onChange={(event) => setLocations(event.target.value)}
                placeholder="New York, California"
                aria-describedby="location-help"
              />
              <small id="location-help">Separate locations with commas.</small>
            </label>
            <label className="field">
              <span>Employment type</span>
              <select
                value={employmentType}
                onChange={(event) => setEmploymentType(event.target.value)}
              >
                <option value="full_time">Full-time</option>
                <option value="part_time">Part-time</option>
                <option value="contract">Contract</option>
                <option value="temporary">Temporary</option>
                <option value="internship">Internship</option>
              </select>
            </label>
          </div>

          <label className="field field--editor">
            <span>Job description</span>
            <textarea
              required
              minLength={30}
              maxLength={100000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Paste the full job posting here..."
            />
            <small>{description.length.toLocaleString()} characters</small>
          </label>

          {error ? <div className="alert alert--error" role="alert">{error}</div> : null}

          <div className="form-actions">
            <p>
              The agent will inspect the draft only. You approve every proposed change before
              publication.
            </p>
            <button className="button button--primary button--large" disabled={submitting}>
              {submitting ? "Starting review…" : "Run compliance review"}
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
