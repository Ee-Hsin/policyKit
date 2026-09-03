"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PolicyForm } from "@/components/PolicyForm";
import { ApiError, createPolicy } from "@/lib/api";
import type { PolicyCreateInput, PolicyDraftInput } from "@/lib/types";

export default function NewPolicyPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function submit(input: PolicyCreateInput | PolicyDraftInput) {
    setSubmitting(true);
    setError("");
    try {
      const policy = await createPolicy(input as PolicyCreateInput);
      router.push(`/admin/policies/${policy.id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create the policy.");
      setSubmitting(false);
    }
  }

  return (
    <div className="page-shell admin-shell admin-shell--editor">
      <div className="editor-header">
        <div>
          <Link className="back-link" href="/admin/policies">← All policies</Link>
          <p className="kicker">New policy</p>
          <h1>Create a policy draft</h1>
          <p>Define a versioned rule, its scope, and examples the agent can use during investigation.</p>
        </div>
        <span className="status-pill status-pill--warning">Draft</span>
      </div>
      {error ? <div className="alert alert--error" role="alert">{error}</div> : null}
      <PolicyForm create submitting={submitting} submitLabel="Create policy" onSubmit={submit} />
    </div>
  );
}
