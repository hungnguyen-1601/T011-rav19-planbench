"use client";

/** Accounts, roles and the trail of who changed them.
 *
 * Every act here takes a reason, and the API requires it rather than
 * politely suggesting it. This is the table an auditor opens first, and
 * a grant with no reason is a grant nobody can review: "who gave this
 * person the reviewer package, and why" is the whole question, and half
 * an answer is not an answer.
 */

import { authFetch } from "./auth";

export interface Account {
  id: string;
  nickname: string;
  email: string;
  display_name: string;
  roles: string[];
  capabilities: string[];
  disabled: boolean;
  disabled_at: string | null;
  last_sign_in_at: string | null;
  created_at: string;
}

export interface AccountEvent {
  sequence: number;
  user_id: string;
  actor_user_id: string | null;
  actor_roles: string;
  authorized_capability: string;
  action: string;
  previous: string;
  new: string;
  reason: string;
  /** Whether somebody used a break-glass path — an act the ordinary
   * rules would have refused. Kept as its own field rather than left to
   * be spotted in the prose, because it is the first thing an auditor
   * filters on. */
  override: boolean;
  created_at: string;
}

export interface OpsJob {
  id: string;
  kind: string;
  state: string;
  created_by: string | null;
  purpose: string;
  run_id: string | null;
  message: string;
}

export function listAccounts(): Promise<Account[]> {
  return authFetch<Account[]>("/admin/users");
}

export function grantRole(userId: string, role: string, reason: string): Promise<Account> {
  return authFetch<Account>(`/admin/users/${userId}/roles`, {
    method: "POST",
    body: JSON.stringify({ role, reason }),
  });
}

export function revokeRole(userId: string, role: string, reason: string): Promise<Account> {
  // The reason travels as a query parameter because a DELETE body is not
  // reliably forwarded by every proxy between here and the API.
  return authFetch<Account>(
    `/admin/users/${userId}/roles/${role}?reason=${encodeURIComponent(reason)}`,
    { method: "DELETE" },
  );
}

export function disableAccount(userId: string, reason: string): Promise<Account> {
  return authFetch<Account>(`/admin/users/${userId}/disable`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function enableAccount(userId: string, reason: string): Promise<Account> {
  return authFetch<Account>(`/admin/users/${userId}/enable`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function fetchAccountAudit(): Promise<AccountEvent[]> {
  return authFetch<AccountEvent[]>("/admin/audit");
}

export function fetchOpsJobs(): Promise<OpsJob[]> {
  return authFetch<OpsJob[]>("/admin/ops/jobs");
}

export function cancelAnyJob(jobId: string, reason: string): Promise<OpsJob> {
  return authFetch<OpsJob>(`/admin/ops/jobs/${jobId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

/** The roles an administrator may hand out.
 *
 * `demo_owner` is deliberately absent. It is a deployment profile's
 * exception rather than a job somebody does, it is granted by the
 * launcher provisioning a demo machine, and offering it in a dropdown
 * would turn a one-machine concession into something anybody could
 * spread. Removing it is a runbook, not a click.
 */
export const GRANTABLE_ROLES = ["engineer", "reviewer", "admin"] as const;
