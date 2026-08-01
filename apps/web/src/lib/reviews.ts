"use client";

/** Review requests: sending them, answering them, and the inbox.
 *
 * Everything here is addressed by *nickname* when a human types it and
 * by id everywhere else. The backend re-checks who the caller is on
 * every call, so nothing in this file is a permission decision — it
 * only decides what to show.
 */

import { authFetch } from "./auth";

export type ReviewStage = "spec" | "result";
export type ReviewStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface ReviewRequest {
  id: string;
  benchmark_id: string;
  stage: ReviewStage;
  requested_by_user_id: string;
  reviewer_user_id: string;
  status: ReviewStatus;
  request_comment: string;
  review_comment: string;
  created_at: string;
  reviewed_at: string | null;
  cancelled_at: string | null;
}

export interface UserSummary {
  id: string;
  nickname: string;
  display_name: string;
  avatar_url: string;
}

export interface ReviewRequestView {
  request: ReviewRequest;
  benchmark_name: string;
  benchmark_state: string;
  requested_by: UserSummary | null;
  reviewer: UserSummary | null;
}

export interface Inbox {
  requests: ReviewRequestView[];
  pending: number;
}

export function searchMembers(nickname: string): Promise<UserSummary[]> {
  if (!nickname.trim()) return Promise.resolve([]);
  return authFetch<UserSummary[]>(`/users/search?nickname=${encodeURIComponent(nickname)}`);
}

export function fetchInbox(pendingOnly = false): Promise<Inbox> {
  return authFetch<Inbox>(`/reviews/inbox?pending_only=${pendingOnly}`);
}

export function fetchSent(): Promise<ReviewRequestView[]> {
  return authFetch<ReviewRequestView[]>("/reviews/sent");
}

export function sendForReview(
  benchmarkId: string,
  reviewerNickname: string,
  stage: ReviewStage,
  comment: string,
): Promise<ReviewRequest> {
  return authFetch<ReviewRequest>(`/benchmarks/${benchmarkId}/review-requests`, {
    method: "POST",
    body: JSON.stringify({ reviewer_nickname: reviewerNickname, stage, comment }),
  });
}

export function answerReview(
  requestId: string,
  decision: "approve" | "reject",
  comment: string,
): Promise<ReviewRequestView> {
  return authFetch<ReviewRequestView>(`/reviews/${requestId}/${decision}`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function commentOnReview(requestId: string, comment: string): Promise<ReviewRequestView> {
  return authFetch<ReviewRequestView>(`/reviews/${requestId}/comment`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function cancelReview(requestId: string): Promise<ReviewRequestView> {
  return authFetch<ReviewRequestView>(`/reviews/${requestId}/cancel`, { method: "POST" });
}

/** The pending request that gates a stage, if there is one. */
export function pendingFor(
  requests: readonly ReviewRequestView[] | undefined,
  stage: ReviewStage,
): ReviewRequestView | undefined {
  return (requests ?? []).find(
    (view) => view.request.stage === stage && view.request.status === "pending",
  );
}

/**
 * Whether the signed-in member may press Run.
 *
 * A hint for the UI, never a decision: the backend checks ownership and
 * approval state itself on every request, and this function existing
 * does not make hiding the button a security measure.
 *
 * Only "approved" qualifies — an Approver's decision (or an admin
 * override), never the owner's own submission. Earlier states used to
 * be included here because the owner could clear the gate themselves
 * on the way to running; that self-approval path no longer exists, so
 * showing Run as available from draft/pending_approval would invite a
 * click that the backend now refuses.
 */
export function canRun(
  isOwner: boolean,
  state: string,
  requests: readonly ReviewRequestView[] | undefined,
): boolean {
  if (!isOwner) return false;
  if (pendingFor(requests, "spec")) return false;
  return state === "approved";
}

/** Whether the signed-in member may accept their own results. */
export function canAcceptResult(
  isOwner: boolean,
  state: string,
  requests: readonly ReviewRequestView[] | undefined,
): boolean {
  return isOwner && state === "pending_review" && !pendingFor(requests, "result");
}
