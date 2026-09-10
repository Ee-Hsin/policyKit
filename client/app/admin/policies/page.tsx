"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ApiError, listPolicies } from "@/lib/api";
import { formatDate, labelize } from "@/lib/format";
import type { PolicySummary } from "@/lib/types";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPolicyCatalog = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setPolicies(await listPolicies());
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : "Could not load policies.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPolicyCatalog();
  }, [loadPolicyCatalog]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return policies;
    return policies.filter((policy) =>
      [policy.title, policy.category, ...policy.jurisdictions].some((value) =>
        value.toLowerCase().includes(needle),
      ),
    );
  }, [policies, query]);

  return (
    <div className="page-shell admin-shell">
      <section className="admin-hero">
        <h1>Platform Policies</h1>
        <Link className="button button--primary" href="/admin/policies/new">
          + Add New Policy
        </Link>
      </section>

      {error ? (
        <section className="load-error-card" role="alert">
          <p className="kicker">Policy catalog unavailable</p>
          <h2>We could not load the policy library.</h2>
          <p>{error}</p>
          <button
            className="button button--primary"
            type="button"
            onClick={() => void loadPolicyCatalog()}
          >
            Try again
          </button>
        </section>
      ) : (
        <section className="policy-table-card">
          <div className="table-toolbar">
            <label className="search-field">
              <span aria-hidden="true">⌕</span>
              <span className="sr-only">Search policies</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by policy, category, or jurisdiction"
              />
            </label>
            <span>
              {filtered.length} {filtered.length === 1 ? "policy" : "policies"}
            </span>
          </div>

          {loading ? (
            <div className="empty-state">
              <span className="spinner spinner--small" />
              <p>Loading policies…</p>
            </div>
          ) : filtered.length ? (
            <>
              <div className="policy-table-wrap policy-table-wrap--desktop">
                <table className="policy-table">
                  <thead>
                    <tr>
                      <th>Policy</th>
                      <th>Category</th>
                      <th>Scope</th>
                      <th>Version</th>
                      <th>Status</th>
                      <th>Updated</th>
                      <th>
                        <span className="sr-only">Open</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((policy) => (
                      <tr key={policy.id}>
                        <td>
                          <Link href={`/admin/policies/${policy.id}`}>
                            <strong>{policy.title}</strong>
                          </Link>
                        </td>
                        <td>{labelize(policy.category)}</td>
                        <td>
                          <div className="tag-row">
                            {policy.jurisdictions.slice(0, 3).map((item) => (
                              <span className="tag" key={item}>
                                {item}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td>v{policy.current_version}</td>
                        <td>
                          <span
                            className={`policy-status${policy.status === "draft" ? " policy-status--draft" : ""}`}
                          >
                            {labelize(policy.status)}
                          </span>
                        </td>
                        <td>{formatDate(policy.updated_at)}</td>
                        <td>
                          <Link
                            className="row-arrow"
                            href={`/admin/policies/${policy.id}`}
                            aria-label={`Open ${policy.title}`}
                          >
                            →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul className="policy-mobile-list">
                {filtered.map((policy) => (
                  <li key={policy.id}>
                    <Link href={`/admin/policies/${policy.id}`}>
                      <span className="policy-mobile-list__heading">
                        <strong>{policy.title}</strong>
                        <span aria-hidden="true">→</span>
                      </span>
                      <span className="policy-mobile-list__meta">
                        <span>Category: {labelize(policy.category)}</span>
                        <span>
                          Scope: {policy.jurisdictions.join(", ") || "All"}
                        </span>
                        <span>Version: {policy.current_version}</span>
                        <span>Status: {labelize(policy.status)}</span>
                        <span>Updated: {formatDate(policy.updated_at)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-state__icon">§</div>
              <h2>
                {policies.length
                  ? "No policies match your search"
                  : "Create the first policy"}
              </h2>
              <p>
                {policies.length
                  ? "Try a broader policy name or jurisdiction."
                  : "The compliance agent needs at least one published policy before it can review a posting."}
              </p>
              {!policies.length ? (
                <Link
                  className="button button--primary"
                  href="/admin/policies/new"
                >
                  Create policy
                </Link>
              ) : null}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
