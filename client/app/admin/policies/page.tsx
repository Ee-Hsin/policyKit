"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ApiError, listPolicies } from "@/lib/api";
import { formatDate, labelize } from "@/lib/format";
import type { PolicySummary } from "@/lib/types";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void listPolicies()
      .then(setPolicies)
      .catch((cause) => setError(cause instanceof ApiError ? cause.message : "Could not load policies."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return policies;
    return policies.filter((policy) =>
      [policy.key, policy.title, policy.category, ...policy.jurisdictions].some((value) => value.toLowerCase().includes(needle)),
    );
  }, [policies, query]);

  const publishedCount = policies.filter((policy) => policy.status === "published").length;

  return (
    <div className="page-shell admin-shell">
      <section className="admin-hero">
        <div>
          <p className="kicker">Policy administration</p>
          <h1>Platform policies</h1>
          <p>Create, test, and publish the rules that guide every compliance review.</p>
        </div>
        <Link className="button button--primary button--large" href="/admin/policies/new">+ New policy</Link>
      </section>

      <section className="metrics-row" aria-label="Policy summary">
        <div><strong>{policies.length}</strong><span>Total policies</span></div>
        <div><strong>{publishedCount}</strong><span>Published</span></div>
        <div><strong>{policies.filter((policy) => policy.status === "draft").length}</strong><span>Drafts</span></div>
        <div><strong>{policies.filter((policy) => policy.index_status === "failed").length}</strong><span>Index issues</span></div>
      </section>

      <section className="policy-table-card">
        <div className="table-toolbar">
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <span className="sr-only">Search policies</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by policy, key, or jurisdiction" />
          </label>
          <span>{filtered.length} {filtered.length === 1 ? "policy" : "policies"}</span>
        </div>

        {error ? <div className="alert alert--error" role="alert">{error}</div> : null}
        {loading ? (
          <div className="empty-state"><span className="spinner spinner--small" /><p>Loading policies…</p></div>
        ) : filtered.length ? (
          <div className="policy-table-wrap">
            <table className="policy-table">
              <thead>
                <tr><th>Policy</th><th>Scope</th><th>Version</th><th>Status</th><th>Updated</th><th><span className="sr-only">Open</span></th></tr>
              </thead>
              <tbody>
                {filtered.map((policy) => (
                  <tr key={policy.id}>
                    <td>
                      <Link href={`/admin/policies/${policy.id}`}>
                        <strong>{policy.title}</strong>
                        <span>{policy.key} · {labelize(policy.category)}</span>
                      </Link>
                      <div className="policy-mobile-meta">
                        <span>{policy.jurisdictions.slice(0, 2).join(", ")}</span>
                        <span>v{policy.current_version}</span>
                        <span>{labelize(policy.status)}</span>
                      </div>
                    </td>
                    <td><div className="tag-row">{policy.jurisdictions.slice(0, 3).map((item) => <span className="tag" key={item}>{item}</span>)}</div></td>
                    <td>v{policy.current_version}</td>
                    <td>
                      <span className={`status-pill status-pill--${policy.status === "published" ? "success" : "warning"}`}>{labelize(policy.status)}</span>
                      <span className={`index-label index-label--${policy.index_status}`}>{labelize(policy.index_status)}</span>
                    </td>
                    <td>{formatDate(policy.updated_at)}</td>
                    <td><Link className="row-arrow" href={`/admin/policies/${policy.id}`} aria-label={`Open ${policy.title}`}>→</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-state__icon">§</div>
            <h2>{policies.length ? "No policies match your search" : "Create the first policy"}</h2>
            <p>{policies.length ? "Try a broader policy name or jurisdiction." : "The compliance agent needs at least one published policy before it can review a posting."}</p>
            {!policies.length ? <Link className="button button--primary" href="/admin/policies/new">Create policy</Link> : null}
          </div>
        )}
      </section>
    </div>
  );
}
