"use client";

import { FormEvent, useState } from "react";
import { JurisdictionSelect } from "@/components/JurisdictionSelect";
import type {
  PolicyCategory,
  PolicyCreateInput,
  PolicyDraftInput,
  PolicyVersionFields,
} from "@/lib/types";

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
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toDateInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function toApiDate(value: string) {
  return value ? new Date(`${value}T00:00:00`).toISOString() : null;
}

const employmentOptions = [
  ["full_time", "Full-time"],
  ["part_time", "Part-time"],
  ["contract", "Contract"],
  ["temporary", "Temporary"],
  ["internship", "Internship"],
] as const;

const policyCategories: PolicyCategory[] = [
  "Discrimination",
  "Compensation",
  "Employment status",
  "Transparency",
  "Content",
];

interface PolicyFormProps {
  initial?: Partial<PolicyVersionFields>;
  initialTitle?: string;
  initialCategory?: PolicyCategory | "";
  policyKey?: string;
  create?: boolean;
  submitting?: boolean;
  formId?: string;
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
  formId,
  submitLabel,
  onSubmit,
}: PolicyFormProps) {
  const values = { ...emptyFields, ...initial };
  const [key, setKey] = useState(policyKey);
  const [title, setTitle] = useState(initialTitle);
  const [category, setCategory] = useState<PolicyCategory | "">(initialCategory);
  const [ruleText, setRuleText] = useState(values.rule_text);
  const [rationale, setRationale] = useState(values.rationale ?? "");
  const [remediation, setRemediation] = useState(values.remediation ?? "");
  const [enforcement, setEnforcement] = useState(values.enforcement_level);
  const [jurisdictions, setJurisdictions] = useState(values.jurisdictions);
  const [employmentTypes, setEmploymentTypes] = useState(values.employment_types);
  const [violationExamples, setViolationExamples] = useState(
    listToText(values.violation_examples),
  );
  const [compliantExamples, setCompliantExamples] = useState(
    listToText(values.compliant_examples),
  );
  const [exceptions, setExceptions] = useState(listToText(values.exceptions));
  const [effectiveAt, setEffectiveAt] = useState(
    toDateInput(values.effective_at),
  );
  const [expiresAt, setExpiresAt] = useState(toDateInput(values.expires_at));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const fields: PolicyDraftInput = {
      title,
      category: category || undefined,
      rule_text: ruleText,
      rationale: rationale || null,
      remediation: remediation || null,
      enforcement_level: enforcement,
      jurisdictions,
      employment_types: employmentTypes,
      platforms: values.platforms,
      violation_examples: textToList(violationExamples),
      compliant_examples: textToList(compliantExamples),
      exceptions: textToList(exceptions),
      effective_at: toApiDate(effectiveAt),
      expires_at: toApiDate(expiresAt),
    };
    await onSubmit(create ? ({ ...fields, key } as PolicyCreateInput) : fields);
  }

  return (
    <form className="policy-form policy-form-surface" id={formId} onSubmit={submit}>
      <section className="policy-form-section">
        <h2>Policy details</h2>
        <div className={`form-grid ${create ? "form-grid--three" : "form-grid--two"}`}>
          {create ? (
            <label className="field">
              <span>Policy key</span>
              <input
                required
                minLength={3}
                maxLength={80}
                pattern="[A-Z0-9][A-Z0-9_-]{2,79}"
                value={key}
                onChange={(event) =>
                  setKey(event.target.value.toUpperCase().replaceAll(" ", "_"))
                }
                placeholder="NY-PAY-001"
              />
            </label>
          ) : null}
          <label className="field">
            <span>Title</span>
            <input
              required
              minLength={3}
              maxLength={240}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Salary range disclosure"
            />
          </label>
          <label className="field">
            <span>Category</span>
            <select
              required
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as PolicyCategory | "")
              }
            >
              <option disabled value="">
                Select category
              </option>
              {policyCategories.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="policy-form-section">
        <h2>Rule</h2>
        <label className="field">
          <span>Policy rule</span>
          <textarea
            className="textarea--rule"
            required
            minLength={10}
            value={ruleText}
            onChange={(event) => setRuleText(event.target.value)}
            placeholder="State the requirement in precise, testable language…"
          />
        </label>
      </section>

      <section className="policy-form-section">
        <h2>Applies to</h2>
        <div className="form-grid form-grid--two">
          <JurisdictionSelect
            includeGlobal
            label="Jurisdictions"
            value={jurisdictions}
            onChange={setJurisdictions}
          />
          <fieldset className="compact-check-field">
            <legend>Employment types <em>Optional</em></legend>
            <div>
              {employmentOptions.map(([value, label]) => (
                <label key={value}>
                  <input
                    checked={employmentTypes.includes(value)}
                    onChange={(event) => setEmploymentTypes((current) =>
                      event.target.checked
                        ? [...current, value]
                        : current.filter((item) => item !== value),
                    )}
                    type="checkbox"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            <small>No selection means all employment types.</small>
          </fieldset>
        </div>
      </section>

      <details className="policy-options">
        <summary>More options</summary>
        <div className="policy-options__content">
          <div className="form-grid form-grid--two">
            <label className="field">
              <span>Rationale <em>Optional</em></span>
              <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why this policy exists…" />
            </label>
            <label className="field">
              <span>Recommended remediation <em>Optional</em></span>
              <textarea value={remediation} onChange={(event) => setRemediation(event.target.value)} placeholder="How to resolve a violation…" />
            </label>
          </div>

          <div className="form-grid form-grid--three">
            <label className="field">
              <span>Enforcement level</span>
              <select value={enforcement} onChange={(event) => setEnforcement(event.target.value)}>
                <option value="standard">Standard</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
            <label className="field">
              <span>Effective date <em>Optional</em></span>
              <input type="date" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} />
            </label>
            <label className="field">
              <span>Expiry date <em>Optional</em></span>
              <input type="date" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} />
            </label>
          </div>

          <div className="form-grid form-grid--three">
          <label className="field">
            <span>Violation examples</span>
            <textarea
              value={violationExamples}
              onChange={(event) => setViolationExamples(event.target.value)}
              placeholder={"Competitive salary\nRecent graduates preferred"}
            />
            <small>One example per line.</small>
          </label>
          <label className="field">
            <span>Compliant examples</span>
            <textarea
              value={compliantExamples}
              onChange={(event) => setCompliantExamples(event.target.value)}
              placeholder="The annual salary range is $90,000–$110,000 USD."
            />
            <small>One example per line.</small>
          </label>
          <label className="field">
            <span>Exceptions</span>
            <textarea
              value={exceptions}
              onChange={(event) => setExceptions(event.target.value)}
              placeholder="Volunteer roles"
            />
            <small>One exception per line.</small>
          </label>
          </div>
        </div>
      </details>

      <button className="sr-only" disabled={submitting} type="submit">
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
