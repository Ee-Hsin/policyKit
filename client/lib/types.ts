export type SessionStatus =
  | "draft"
  | "queued"
  | "investigating"
  | "waiting_for_information"
  | "changes_proposed"
  | "waiting_for_approval"
  | "ready_to_publish"
  | "needs_review"
  | "published"
  | "failed";

export interface AgentStep {
  id: string;
  sequence: number;
  kind: string;
  name: string;
  status: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
}

export interface Finding {
  id: string;
  policy_key: string;
  policy_title: string;
  category: string;
  status: "violation" | "no_violation" | "uncertain";
  evidence_text: string | null;
  evidence_start: number | null;
  evidence_end: number | null;
  reason: string;
  confidence: number | null;
  resolved: boolean;
}

export interface ProposedChange {
  id: string;
  original_text: string;
  replacement_text: string;
  reason: string;
  policy_keys: string[];
  status: "proposed" | "accepted" | "rejected";
  created_at: string;
}

export interface PostingVersion {
  id: string;
  version: number;
  content: string;
  source: string;
  approved_at: string | null;
  created_at: string;
}

export interface ComplianceSession {
  id: string;
  status: SessionStatus;
  goal: string;
  title: string;
  organization_name: string | null;
  target_locations: string[];
  employment_type: string;
  platform: string;
  current_question: string | null;
  error_message: string | null;
  policy_snapshot_version: number | null;
  current_posting_version: PostingVersion;
  posting_versions: PostingVersion[];
  findings: Finding[];
  proposed_changes: ProposedChange[];
  steps: AgentStep[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface PolicyVersionFields {
  rule_text: string;
  rationale: string | null;
  remediation: string | null;
  enforcement_level: string;
  jurisdictions: string[];
  employment_types: string[];
  platforms: string[];
  violation_examples: string[];
  compliant_examples: string[];
  exceptions: string[];
  effective_at: string | null;
  expires_at: string | null;
}

export interface PolicyVersion extends PolicyVersionFields {
  id: string;
  version: number;
  status: "draft" | "testing" | "published" | "retired";
  index_status: "pending" | "indexed" | "failed";
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PolicySummary {
  id: string;
  key: string;
  title: string;
  category: string;
  current_version: number;
  status: string;
  index_status: string;
  jurisdictions: string[];
  updated_at: string;
}

export interface PolicyDetail {
  id: string;
  key: string;
  title: string;
  category: string;
  versions: PolicyVersion[];
}

export interface PolicyDraftInput extends PolicyVersionFields {
  title?: string;
  category?: string;
}

export interface PolicyCreateInput extends PolicyVersionFields {
  key: string;
  title: string;
  category: string;
}
