import type {
  ComplianceSession,
  DraftAssistanceInput,
  DraftAssistanceResult,
  HumanReviewInput,
  PolicyCreateInput,
  PolicyDetail,
  PolicyDraftInput,
  PolicySummary,
  PostingVersionInput,
  WritingSuggestionInput,
  WritingSuggestionResult,
} from "@/lib/types";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = "PolicyKit could not complete the request.";
    try {
      const payload = (await response.json()) as {
        detail?: string | Array<{ msg?: string }>;
      };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        const validationMessages = payload.detail.flatMap((item) => item.msg ?? []);
        if (validationMessages.length) message = validationMessages.join(" ");
      }
    } catch {
      // The fallback message is clear when the API does not return JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function createSession(input: {
  title: string;
  job_description: string;
  organization_name?: string;
  target_locations: string[];
  employment_type: string;
  platform: string;
}) {
  return request<ComplianceSession>("/compliance-sessions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createAssistedDraft(input: DraftAssistanceInput) {
  return request<DraftAssistanceResult>("/writing-assistance/drafts", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getSession(id: string) {
  return request<ComplianceSession>(`/compliance-sessions/${id}`);
}

export function savePostingVersion(id: string, input: PostingVersionInput) {
  return request<ComplianceSession>(`/compliance-sessions/${id}/posting-versions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function checkSession(id: string, baseVersionId: string) {
  return request<ComplianceSession>(`/compliance-sessions/${id}/check`, {
    method: "POST",
    body: JSON.stringify({ base_version_id: baseVersionId }),
  });
}

export function requestWritingSuggestion(id: string, input: WritingSuggestionInput) {
  return request<WritingSuggestionResult>(`/compliance-sessions/${id}/writing-suggestions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function answerSession(id: string, baseVersionId: string, message: string) {
  return request<ComplianceSession>(`/compliance-sessions/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ base_version_id: baseVersionId, message }),
  });
}

export function approveRevision(id: string, baseVersionId: string, approved: boolean, notes?: string) {
  return request<ComplianceSession>(`/compliance-sessions/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({
      base_version_id: baseVersionId,
      approved,
      reviewer_name: "Demo recruiter",
      notes: notes || null,
    }),
  });
}

export function publishSession(id: string, baseVersionId: string) {
  return request<ComplianceSession>(`/compliance-sessions/${id}/publish`, {
    method: "POST",
    body: JSON.stringify({
      base_version_id: baseVersionId,
      publisher_name: "Demo recruiter",
    }),
  });
}

export function resolveHumanReview(id: string, input: HumanReviewInput) {
  return request<ComplianceSession>(`/reviews/${id}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listPolicies() {
  return request<PolicySummary[]>("/policies");
}

export function getPolicy(id: string) {
  return request<PolicyDetail>(`/policies/${id}`);
}

export function createPolicy(input: PolicyCreateInput) {
  return request<PolicyDetail>("/policies", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updatePolicyDraft(policyId: string, versionId: string, input: PolicyDraftInput) {
  return request<PolicyDetail>(`/policies/${policyId}/versions/${versionId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function createPolicyVersion(policyId: string) {
  return request<PolicyDetail>(`/policies/${policyId}/versions`, { method: "POST" });
}

export function testPolicy(policyId: string, versionId: string, postingText: string) {
  return request<{
    policy_key: string;
    status: string;
    evidence_text: string | null;
    reason: string;
    confidence: number | null;
  }>(`/policies/${policyId}/versions/${versionId}/test`, {
    method: "POST",
    body: JSON.stringify({ posting_text: postingText }),
  });
}

export function publishPolicy(policyId: string, versionId: string) {
  return request<{
    policy: PolicyDetail;
    snapshot_version: number;
    index_status: string;
  }>(`/policies/${policyId}/versions/${versionId}/publish`, { method: "POST" });
}
