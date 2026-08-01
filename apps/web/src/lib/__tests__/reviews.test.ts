/** The UI's view of when a member may act.
 *
 * These helpers only decide what to *show*. The backend decides what to
 * allow, and every case below has a matching API test that proves the
 * server refuses independently — hiding a button is never the control.
 * What these tests protect is that the UI does not offer an action the
 * server is going to refuse, which is how a user ends up staring at an
 * error they did nothing to cause.
 */

import { describe, expect, it } from "vitest";

import { canAcceptResult, canRun, pendingFor } from "../reviews";
import type { ReviewRequestView, ReviewStage, ReviewStatus } from "../reviews";

function view(
  stage: ReviewStage,
  status: ReviewStatus,
  reviewerId = "user-bob",
): ReviewRequestView {
  return {
    request: {
      id: `req-${stage}-${status}`,
      benchmark_id: "bench-1",
      stage,
      requested_by_user_id: "user-alice",
      reviewer_user_id: reviewerId,
      status,
      request_comment: "",
      review_comment: "",
      created_at: "2026-07-31T00:00:00+00:00",
      reviewed_at: null,
      cancelled_at: null,
    },
    benchmark_name: "bench",
    benchmark_state: "draft",
    requested_by: null,
    reviewer: null,
  };
}

describe("pendingFor", () => {
  it("finds the pending request for a stage", () => {
    const requests = [view("spec", "pending"), view("result", "approved")];
    expect(pendingFor(requests, "spec")?.request.stage).toBe("spec");
    expect(pendingFor(requests, "result")).toBeUndefined();
  });

  it("ignores answered, rejected and cancelled requests", () => {
    for (const status of ["approved", "rejected", "cancelled"] as ReviewStatus[]) {
      expect(pendingFor([view("spec", status)], "spec")).toBeUndefined();
    }
  });

  it("copes with a benchmark that has no requests at all", () => {
    expect(pendingFor(undefined, "spec")).toBeUndefined();
    expect(pendingFor([], "spec")).toBeUndefined();
  });
});

describe("canRun", () => {
  it("lets the owner run a fresh draft — the default path", () => {
    expect(canRun(true, "draft", [])).toBe(true);
  });

  it("lets the owner run an approved benchmark", () => {
    expect(canRun(true, "approved", [])).toBe(true);
  });

  it("lets the owner run again after their results were rejected", () => {
    expect(canRun(true, "rejected", [])).toBe(true);
  });

  it("refuses somebody who does not own it", () => {
    expect(canRun(false, "draft", [])).toBe(false);
  });

  it("refuses while a spec review is pending — the whole point of asking", () => {
    expect(canRun(true, "draft", [view("spec", "pending")])).toBe(false);
  });

  it("allows it again once the reviewer has approved", () => {
    expect(canRun(true, "approved", [view("spec", "approved")])).toBe(true);
  });

  it("allows it again once the request is cancelled", () => {
    expect(canRun(true, "draft", [view("spec", "cancelled")])).toBe(true);
  });

  it("is not blocked by a pending *result* review", () => {
    // Different gate, different question.
    expect(canRun(true, "draft", [view("result", "pending")])).toBe(true);
  });

  it("refuses a benchmark that already ran", () => {
    expect(canRun(true, "pending_review", [])).toBe(false);
    expect(canRun(true, "accepted", [])).toBe(false);
    expect(canRun(true, "running", [])).toBe(false);
  });
});

describe("canAcceptResult", () => {
  it("lets the owner accept their own results", () => {
    expect(canAcceptResult(true, "pending_review", [])).toBe(true);
  });

  it("refuses while a result review is pending", () => {
    expect(canAcceptResult(true, "pending_review", [view("result", "pending")])).toBe(false);
  });

  it("is not blocked by a pending spec review", () => {
    expect(canAcceptResult(true, "pending_review", [view("spec", "pending")])).toBe(true);
  });

  it("refuses somebody who does not own it", () => {
    expect(canAcceptResult(false, "pending_review", [])).toBe(false);
  });

  it("refuses before the run has finished", () => {
    for (const state of ["draft", "approved", "running", "accepted"]) {
      expect(canAcceptResult(true, state, [])).toBe(false);
    }
  });
});
