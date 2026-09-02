"use client";

import { FormEvent, useState } from "react";
import { PanelIcon } from "@/components/PanelIcon";
import type { PolicyCreateInput, PolicyDraftInput, PolicyVersionFields } from "@/lib/types";

const emptyFields: PolicyVersionFields = {
  rule_text: "",
  rationale: null,
  remediation: null,
  enforcement_level: "standard",
  jurisdictions: ["GLOBAL"],
  employment_types: [],
  platforms: [],
  violation_examples: [],
  compliant_examples: [],
  exceptions: [],
  effective_at: null,
  expires_at: null,
};

function listToText(items: string[]) {
  return items.join("\n");
}

function textToList(value: string) {
  return value.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
}

function toLocalDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toApiDate(value: string) {
  return value ? new Date(value).toISOString() : null;
}

interface PolicyFormProps {
  initial?: Partial<PolicyVersionFields>;
  initialTitle?: string;
  initialCategory?: string;
  policyKey?: string;
  create?: boolean;
  submitting?: boolean;
  submitLabel: string;
  onSubmit: (input: PolicyCreateInput | PolicyDraftInput) => Promise<void>;
}

export function PolicyForm({
  initial,
  initialTitle = "",
  initialCategory = "",
  policyKey = "",
  create = false,
  submitting = false,
  submitLabel,
  onSubmit,
}: PolicyFormProps) {
  const values = { ...emptyFields, ...initial };
  const [key, setKey] = useState(policyKey);
  const [title, setTitle] = useState(initialTitle);
  const [category, setCategory] = useState(initialCategory);
  const [ruleText, setRuleText] = useState(values.rule_text);
  const [rationale, setRationale] = useState(values.rationale ?? "");
  const [remediation, setRemediation] = useState(values.remediation ?? "");
  const [enforcement, setEnforcement] = useState(values.enforcement_level);
  const [jurisdictions, setJurisdictions] = useState(listToText(values.jurisdictions));
  const [employmentTypes, setEmploymentTypes] = useState(listToText(values.employment_types));
  const [platforms, setPlatforms] = useState(listToText(values.platforms));
  const [violationExamples, setViolationExamples] = useState(listToText(values.violation_examples));
  const [compliantExamples, setCompliantExamples] = useState(listToText(values.compliant_examples));
  const [exceptions, setExceptions] = useState(listToText(values.exceptions));
  const [effectiveAt, setEffectiveAt] = useState(toLocalDate(values.effective_at));
  const [expiresAt, setExpiresAt] = useState(toLocalDate(values.expires_at));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const fields: PolicyDraftInput = {
      title,
      category,
      rule_text: ruleText,
      rationale: rationale || null,
      remediation: remediation || null,
      enforcement_level: enforcement,
      jurisdictions: textToList(jurisdictions),
      employment_types: textToList(employmentTypes),
      platforms: textToList(platforms),
      violation_examples: textToList(violationExamples),
      compliant_examples: textToList(compliantExamples),
      exceptions: textToList(exceptions),
      effective_at: toApiDate(effectiveAt),
      expires_at: toApiDate(expiresAt),
    };
    await onSubmit(create ? { ...fields, key } as PolicyCreateInput : fields);
  }

  return (
    <form className="policy-form" onSubmit={submit}>
      <section className="admin-card">
        <div className="admin-card__heading">
          <PanelIcon kind="identity" />
          <div>
            <p className="kicker">Identity</p>
            <h2>Name this policy</h2>
          </div>
        </div>
        <div className="form-grid form-grid--three">
          <label className="field">
            <span>Policy key</span>
            <input
              required
              disabled={!create}
              minLength={3}
              maxLength={80}
              pattern="[A-Z0-9][A-Z0-9_-]{2,79}"
              value={key}
              onChange={(event) => setKey(event.target.value.toUpperCase().replaceAll(" ", "_"))}
              placeholder="NY-PAY-001"
            />
            <small>Stable across all versions.</small>
          </label>
          <label className="field">
            <span>Title</span>
            <input required minLength={3} maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Salary range disclosure" />
          </label>
          <label className="field">
            <span>Category</span>
            <input required minLength={2} maxLength={80} value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Compensation" />
          </label>
        </div>
      </section>

      <section className="admin-card">
        <div className="admin-card__heading">
          <PanelIcon kind="rule" />
          <div>
            <p className="kicker">Decision standard</p>
            <h2>Define the rule</h2>
          </div>
        </div>
        <label className="field">
          <span>Policy rule</span>
          <textarea className="textarea--rule" required minLength={10} value={ruleText} onChange={(event) => setRuleText(event.target.value)} placeholder="State the requirement in precise, testable language…" />
        </label>
        <div className="form-grid form-grid--two">
          <label className="field">
            <span>Rationale <em>Optional</em></span>
            <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why this policy exists…" />
          </label>
          <label className="field">
            <span>Recommended remediation <em>Optional</em></span>
            <textarea value={remediation} onChange={(event) => setRemediation(event.target.value)} placeholder="How the agent should resolve a violation…" />
          </label>
        </div>
      </section>

      <section className="admin-card">
        <div className="admin-card__heading">
          <PanelIcon kind="scope" />
          <div>
            <p className="kicker">Scope</p>
            <h2>Set where it applies</h2>
          </div>
        </div>
        <div className="form-grid form-grid--three">
          <label className="field">
            <span>Jurisdictions</span>
            <textarea value={jurisdictions} onChange={(event) => setJurisdictions(event.target.value)} placeholder="GLOBAL" />
            <small>One per line, for example US-NY.</small>
          </label>
          <label className="field">
            <span>Employment types <em>Optional</em></span>
            <textarea value={employmentTypes} onChange={(event) => setEmploymentTypes(event.target.value)} placeholder={"full_time\ncontract"} />
            <small>Empty means all employment types.</small>
          </label>
          <label className="field">
            <span>Platforms <em>Optional</em></span>
            <textarea value={platforms} onChange={(event) => setPlatforms(event.target.value)} placeholder="policykit" />
            <small>Empty means all platforms.</small>
          </label>
          <label className="field">
            <span>Enforcement level</span>
            <select value={enforcement} onChange={(event) => setEnforcement(event.target.value)}>
              <option value="standard">Standard</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <label className="field">
            <span>Effective at <em>Optional</em></span>
            <input type="datetime-local" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} />
          </label>
          <label className="field">
            <span>Expires at <em>Optional</em></span>
            <input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="admin-card">
        <div className="admin-card__heading">
          <PanelIcon kind="guidance" />
          <div>
            <p className="kicker">Guidance</p>
            <h2>Add examples and exceptions</h2>
          </div>
        </div>
        <div className="form-grid form-grid--three">
          <label className="field">
            <span>Violation examples</span>
            <textarea value={violationExamples} onChange={(event) => setViolationExamples(event.target.value)} placeholder={"Competitive salary\nRecent graduates preferred"} />
            <small>One example per line.</small>
          </label>
          <label className="field">
            <span>Compliant examples</span>
            <textarea value={compliantExamples} onChange={(event) => setCompliantExamples(event.target.value)} placeholder="The annual salary range is $90,000–$110,000 USD." />
            <small>One example per line.</small>
          </label>
          <label className="field">
            <span>Exceptions</span>
            <textarea value={exceptions} onChange={(event) => setExceptions(event.target.value)} placeholder="Volunteer roles" />
            <small>One exception per line.</small>
          </label>
        </div>
      </section>

      <div className="sticky-actions">
        <div>
          <strong>{create ? "Create as draft" : "Save draft changes"}</strong>
          <p>Published versions remain immutable.</p>
        </div>
        <button className="button button--primary button--large" disabled={submitting}>{submitting ? "Saving…" : submitLabel}</button>
      </div>
    </form>
  );
}
