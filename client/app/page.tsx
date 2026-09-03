"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, createSession } from "@/lib/api";

const samplePosting = `Join Northstar Labs as a Senior Software Engineer and help build tools used by growing teams. You will design backend services, partner with product and design, and mentor engineers across the company.

We are looking for a recent college graduate with 5+ years of professional software development experience. The ideal candidate is young, energetic, and able to move quickly in a fast-paced environment.

This is a full-time role. We offer competitive compensation and comprehensive benefits.`;

const reviewPrinciples = [
  {
    title: "The evidence stays visible.",
    copy: "Every finding points back to exact language in the draft and the policy that governs it.",
    detail: "Traceable by design",
  },
  {
    title: "The recruiter stays in control.",
    copy: "PolicyKit can propose precise edits, but it cannot accept a revision or publish without approval.",
    detail: "Human approval required",
  },
  {
    title: "The policy set stays fixed.",
    copy: "Each review keeps an immutable policy snapshot, so its decision can be reproduced later.",
    detail: "Auditable decisions",
  },
];

const revealStatement =
  "A strong review does more than flag words. It preserves the evidence, explains the rule, and gives the final decision to a person.";

function ArrowIcon({ direction = "right" }: { direction?: "left" | "right" }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20">
      <path d={direction === "right" ? "M4 10h12m-5-5 5 5-5 5" : "M16 10H4m5-5-5 5 5 5"} />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 3.2 19 6v5.4c0 4.4-2.8 7.8-7 9.6-4.2-1.8-7-5.2-7-9.6V6l7-2.8Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

export default function NewReviewPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [locations, setLocations] = useState("");
  const [employmentType, setEmploymentType] = useState("full_time");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [principleIndex, setPrincipleIndex] = useState(0);

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
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelector("#review")?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }

  function movePrinciple(direction: -1 | 1) {
    setPrincipleIndex(
      (current) => (current + direction + reviewPrinciples.length) % reviewPrinciples.length,
    );
  }

  const principle = reviewPrinciples[principleIndex];

  return (
    <div className="home-page">
      <section className="home-hero" aria-labelledby="home-heading">
        <div className="home-hero__copy motion-reveal">
          <p className="signal-label"><span /> Pre-publication compliance</p>
          <h1 id="home-heading">
            Clear the risk <span className="hero-inline-image image-reveal" aria-hidden="true" /> before
            the role goes live.
          </h1>
          <p className="home-hero__lede">
            PolicyKit investigates every applicable rule, marks the exact evidence, and proposes
            controlled edits while you keep the final say.
          </p>
          <div className="home-hero__actions">
            <a className="button button--light button--large" href="#review">
              Review a job post <ArrowIcon />
            </a>
            <Link className="button button--ghost-dark button--large" href="/admin/policies">
              Explore policy controls
            </Link>
          </div>
          <p className="home-hero__note">
            <ShieldIcon /> Drafts stay private until you approve publication.
          </p>
        </div>

        <div className="review-visual image-reveal" aria-label="Example compliance review">
          <div className="review-visual__image" aria-hidden="true" />
          <div className="review-document">
            <div className="review-document__top">
              <span>Senior product designer</span>
              <i>Draft</i>
            </div>
            <div className="review-document__line review-document__line--wide" />
            <div className="review-document__line" />
            <p>
              The ideal candidate is <mark>young and energetic</mark> with a strong portfolio.
            </p>
            <div className="review-document__line review-document__line--short" />
            <div className="review-evidence">
              <span>Evidence attached</span>
              <strong>Age preference</strong>
            </div>
          </div>
          <div className="review-agent-card">
            <span className="review-agent-card__mark"><ShieldIcon /></span>
            <div>
              <p>PolicyKit found one revision</p>
              <strong>Waiting for your approval</strong>
            </div>
            <span className="review-agent-card__pulse" aria-hidden="true" />
          </div>
        </div>
      </section>

      <section className="assurance-marquee" aria-label="PolicyKit safeguards">
        <div className="assurance-marquee__track">
          {[0, 1].map((group) => (
            <div className="assurance-marquee__group" aria-hidden={group === 1} key={group}>
              <span>Exact evidence</span><i />
              <span>Immutable policy snapshots</span><i />
              <span>Controlled revisions</span><i />
              <span>Human approval</span><i />
              <span>Publication gate</span><i />
            </div>
          ))}
        </div>
      </section>

      <section className="workflow-story" aria-labelledby="workflow-heading">
        <div className="workflow-story__heading motion-reveal">
          <p className="signal-label signal-label--ink"><span /> One review, complete context</p>
          <h2 id="workflow-heading">Compliance that can show its work.</h2>
        </div>
        <p className="scrub-copy" aria-label={revealStatement}>
          {revealStatement.split(" ").map((word, index) => (
            <span className="scrub-word" aria-hidden="true" key={`${word}-${index}`}>{word} </span>
          ))}
        </p>

        <div className="workflow-bento">
          <article className="bento-card bento-card--wide motion-reveal">
            <div className="bento-card__number">All</div>
            <div>
              <h3>Every applicable policy, not a sample.</h3>
              <p>The checker receives the full scoped policy set from a fixed PostgreSQL snapshot.</p>
            </div>
            <div className="policy-stack" aria-hidden="true">
              <span>Equal opportunity</span>
              <span>Pay transparency</span>
              <span>Platform language</span>
            </div>
          </article>

          <article className="bento-card bento-card--evidence motion-reveal">
            <span className="bento-icon"><ShieldIcon /></span>
            <div>
              <h3>Evidence before verdict.</h3>
              <p>Offsets are verified against the original post before a finding is accepted.</p>
            </div>
            <blockquote>“young and energetic”</blockquote>
          </article>

          <article className="bento-card bento-card--compact motion-reveal">
            <span className="bento-knot" aria-hidden="true" />
            <h3>Scoped retrieval</h3>
            <p>Chroma finds useful context. PostgreSQL remains the source of truth.</p>
          </article>

          <article className="bento-card bento-card--dark motion-reveal">
            <div className="approval-orbit" aria-hidden="true"><span /><i /></div>
            <h3>No silent rewrites.</h3>
            <p>Every suggested change is declared, reconstructed, and held for approval.</p>
          </article>

          <article className="bento-card bento-card--compact motion-reveal">
            <div className="gate-lines" aria-hidden="true"><i /><i /><i /></div>
            <h3>A real publication gate</h3>
            <p>The latest approved version must pass a fresh, complete policy check.</p>
          </article>
        </div>
      </section>

      <section className="principles-panel image-reveal" aria-labelledby="principle-title">
        <div className="principles-panel__visual" aria-hidden="true">
          <span className="principles-panel__ring principles-panel__ring--outer" />
          <span className="principles-panel__ring principles-panel__ring--inner" />
          <span className="principles-panel__core"><ShieldIcon /></span>
        </div>
        <div className="principles-panel__content" aria-live="polite">
          <p className="signal-label signal-label--light"><span /> {principle.detail}</p>
          <h2 id="principle-title">{principle.title}</h2>
          <p>{principle.copy}</p>
          <div className="principles-panel__controls">
            <span>{principleIndex + 1} of {reviewPrinciples.length}</span>
            <div>
              <button type="button" onClick={() => movePrinciple(-1)} aria-label="Previous principle"><ArrowIcon direction="left" /></button>
              <button type="button" onClick={() => movePrinciple(1)} aria-label="Next principle"><ArrowIcon /></button>
            </div>
          </div>
        </div>
      </section>

      <section className="review-section" id="review" aria-labelledby="review-heading">
        <div className="review-section__intro motion-reveal">
          <p className="signal-label signal-label--ink"><span /> Start with the draft</p>
          <h2 id="review-heading">Put the posting through a complete review.</h2>
          <p>
            Add the role and hiring locations. The agent resolves the correct policy scope before
            it makes a decision.
          </p>
          <button className="text-action" type="button" onClick={loadExample}>
            Load a realistic example <ArrowIcon />
          </button>
          <div className="review-section__assurance">
            <ShieldIcon />
            <p><strong>You approve the changes.</strong><span>The agent cannot publish on its own.</span></p>
          </div>
        </div>

        <div className="composer-card motion-reveal">
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
              <p>A fixed policy snapshot and full audit trail are saved with the review.</p>
              <button className="button button--primary button--large" disabled={submitting}>
                {submitting ? "Starting review…" : "Run compliance review"}
                <ArrowIcon />
              </button>
            </div>
          </form>
        </div>
      </section>

      <footer className="home-footer">
        <Link className="brand brand--footer" href="/" aria-label="PolicyKit home">
          <span className="brand__mark" aria-hidden="true"><ShieldIcon /></span>
          <span>PolicyKit</span>
        </Link>
        <p>Make policy decisions clear before a job post goes live.</p>
        <Link href="/admin/policies">Manage policies <ArrowIcon /></Link>
      </footer>
    </div>
  );
}
