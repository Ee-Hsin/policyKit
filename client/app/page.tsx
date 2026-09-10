"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { JurisdictionSelect } from "@/components/JurisdictionSelect";
import { ApiError, createSession } from "@/lib/api";

const samplePosting = `Join Northstar Labs as a Senior Software Engineer and help build tools used by growing teams. You will design backend services, partner with product and design, and mentor engineers across the company.

We are looking for a recent college graduate with 5+ years of professional software development experience. The ideal candidate is young, energetic, and able to move quickly in a fast-paced environment.

This is a full-time role. We offer competitive compensation and comprehensive benefits.`;

export default function NewReviewPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [locations, setLocations] = useState<string[]>([]);
  const [employmentType, setEmploymentType] = useState("full_time");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!locations.length) {
      setError("Select at least one hiring location.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const session = await createSession({
        title,
        job_description: description,
        organization_name: organization || undefined,
        target_locations: locations,
        employment_type: employmentType,
        platform: "policykit",
      });
      router.push(`/sessions/${session.id}`);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Could not start the review.",
      );
      setSubmitting(false);
    }
  }

  function loadExample() {
    setTitle("Senior Software Engineer");
    setOrganization("Northstar Labs");
    setLocations(["US-NY", "US-CA"]);
    setEmploymentType("full_time");
    setDescription(samplePosting);
  }

  return (
    <div className="page-shell review-page">
      <header className="review-workspace__header">
        <div>
          <h1 id="review-heading">Job Post Review</h1>
          <p>
            We&apos;ll review the posting to ensure it&apos;s compliant with
            company policies and local laws.
          </p>
        </div>
        <div className="review-workspace__actions">
          <button
            className="button button--secondary"
            type="button"
            onClick={loadExample}
          >
            Load Example
          </button>
          <button
            className="button button--primary"
            type="submit"
            form="job-post-review"
            disabled={submitting}
          >
            {submitting ? "Checking Post…" : "Check Job Post"}
          </button>
        </div>
      </header>

      <section
        className="composer-card review-composer"
        id="review"
        aria-labelledby="review-heading"
      >
        <form
          className="review-workspace__form"
          id="job-post-review"
          onSubmit={handleSubmit}
        >
          <div className="review-document-editor">
            <label className="field review-document-editor__title">
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

            <label className="field field--editor review-document-editor__body">
              <span>Job description</span>
              <textarea
                required
                minLength={30}
                maxLength={100000}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Paste the full job posting here..."
              />
            </label>
          </div>

          <aside
            className="review-settings"
            aria-label="Additional information"
          >
            <div className="review-settings__heading">
              <h2>Additional Information</h2>
            </div>

            <label className="field">
              <span>
                Organization <em>Optional</em>
              </span>
              <input
                maxLength={240}
                value={organization}
                onChange={(event) => setOrganization(event.target.value)}
                placeholder="Acme, Inc."
              />
            </label>

            <JurisdictionSelect
              label="Hiring locations"
              value={locations}
              onChange={setLocations}
            />

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

            {error ? (
              <div className="alert alert--error" role="alert">
                {error}
              </div>
            ) : null}
          </aside>
        </form>
      </section>
    </div>
  );
}
