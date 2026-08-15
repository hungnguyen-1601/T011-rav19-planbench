/** What the dashboard counts, and what it refuses to guess.
 *
 * The rule these tests exist for: a section that failed to load is
 * `null`, never `0`. "We could not find out" and "there are none" look
 * identical on a stat card and mean opposite things, and a dashboard
 * that quietly reports zero for a failed request is worse than one that
 * admits it does not know.
 */

import { describe, expect, it } from "vitest";

import {
  pendingForMe,
  recentBenchmarks,
  recentSimulations,
  summarise,
  type DashboardData,
} from "@/lib/dashboard";
import type { BenchmarkResource } from "@/lib/benchmarkTypes";
import type { ReviewRequestView } from "@/lib/reviews";
import type { SimulationResource } from "@/lib/types";

function benchmark(id: string, state: string, createdAt: string): BenchmarkResource {
  return {
    id,
    spec: { spec_version: "1", name: `bench ${id}`, description: "", algorithms: [], seeds: [] },
    map_id: "m",
    scenario_id: "s",
    state: state as BenchmarkResource["state"],
    created_by: "alice",
    created_at: createdAt,
    started_at: null,
    finished_at: null,
    approvals: [],
    report_artifact_uri: null,
    owner_user_id: "u1",
    is_owner: true,
    review_requests: [],
  };
}

function simulation(id: string, createdAt: string): SimulationResource {
  return {
    id,
    map_id: "m",
    scenario_id: "s",
    algorithm: "astar+dwa",
    state: "finished",
    created_at: createdAt,
  } as SimulationResource;
}

function review(id: string, status: string): ReviewRequestView {
  return {
    request: {
      id,
      benchmark_id: "b1",
      stage: "spec",
      requested_by_user_id: "u2",
      reviewer_user_id: "u1",
      status: status as ReviewRequestView["request"]["status"],
      request_comment: "",
      review_comment: "",
      created_at: "2026-08-01T00:00:00Z",
      reviewed_at: null,
      cancelled_at: null,
    },
    benchmark_name: "bench",
    benchmark_state: "draft",
    requested_by: null,
    reviewer: null,
  };
}

/** One comparison, as the dashboard reads it.
 *
 * `ranked` and `config_state` are the two the cards count, and they are
 * independent: a run can rank and never be approved, and a run that
 * ranks nobody can still have been read. */
function decision(id: string, ranked: boolean, configState: string, created: string) {
  return {
    id,
    task_profile_id: "open_hall_v2",
    ranked,
    config_state: configState,
    created_at: created,
  } as unknown as DashboardData["decisions"] extends (infer T)[] | null ? T : never;
}

const EMPTY: DashboardData = {
  benchmarks: null,
  decisions: null,
  simulations: null,
  scenarios: null,
  algorithms: null,
  pendingReviews: null,
  online: false,
  partial: true,
};

const LOADED: DashboardData = {
  benchmarks: [
    benchmark("b1", "accepted", "2026-08-01T10:00:00Z"),
    benchmark("b2", "draft", "2026-08-01T12:00:00Z"),
    benchmark("b3", "accepted", "2026-08-01T11:00:00Z"),
  ],
  decisions: [
    decision("d1", true, "approved", "2026-08-01T10:00:00Z"),
    decision("d2", false, "not_applicable", "2026-08-01T12:00:00Z"),
    decision("d3", true, "pending", "2026-08-01T11:00:00Z"),
  ],
  simulations: [simulation("s1", "2026-08-01T09:00:00Z"), simulation("s2", "2026-08-01T13:00:00Z")],
  scenarios: [{ name: "open_space" }, { name: "doorway" }] as DashboardData["scenarios"],
  algorithms: [
    { id: "astar+dwa", benchmarkable: true },
    { id: "astar+pure_pursuit", benchmarkable: false },
  ],
  pendingReviews: [review("r1", "pending")],
  online: true,
  partial: false,
};

describe("summarise", () => {
  it("counts what loaded", () => {
    const stats = summarise(LOADED);
    expect(stats.benchmarks).toBe(3);
    expect(stats.simulations).toBe(2);
    expect(stats.scenarios).toBe(2);
    expect(stats.pendingReviews).toBe(1);
  });

  it("counts ranked runs beside the total, not instead of it", () => {
    /* Most runs produce no card: fewer than two candidates through the
       gates means no ΔU (HĐ-7). A dashboard showing only "ranked" would
       make the ordinary outcome look like a failure rate, which is the
       pressure that once produced a card bounding a collision
       probability off a single episode. */
    const stats = summarise(LOADED);
    expect(stats.decisions).toBe(3);
    expect(stats.ranked).toBe(2);
  });

  it("counts only approved configurations as accepted", () => {
    /* Reading a run and approving its configuration are separate acts
       (HĐ-14), so "accepted" counts the second one alone. */
    expect(summarise(LOADED).accepted).toBe(1);
  });

  it("excludes reference-only stacks from the algorithm count", () => {
    // The card says "stacks you can benchmark". Counting one that may
    // not be benchmarked is a lie only visible on another page.
    expect(summarise(LOADED).algorithms).toBe(1);
  });

  it("reports null — not zero — for anything that failed to load", () => {
    const stats = summarise(EMPTY);
    expect(stats.benchmarks).toBeNull();
    expect(stats.decisions).toBeNull();
    expect(stats.ranked).toBeNull();
    expect(stats.accepted).toBeNull();
    expect(stats.pendingReviews).toBeNull();
    expect(stats.scenarios).toBeNull();
    expect(stats.algorithms).toBeNull();
    expect(stats.simulations).toBeNull();
  });

  it("reports a real zero as zero", () => {
    // The other half of the rule: an empty list is a fact, and must not
    // be shown as unknown.
    const stats = summarise({ ...EMPTY, decisions: [], partial: false });
    expect(stats.decisions).toBe(0);
    expect(stats.ranked).toBe(0);
    expect(stats.accepted).toBe(0);
  });
});

describe("recent activity", () => {
  it("puts the newest benchmark first", () => {
    expect(recentBenchmarks(LOADED).map((item) => item.id)).toEqual(["b2", "b3", "b1"]);
  });

  it("puts the newest simulation first", () => {
    expect(recentSimulations(LOADED).map((item) => item.id)).toEqual(["s2", "s1"]);
  });

  it("caps the list so the panel stays a summary", () => {
    const many = Array.from({ length: 20 }, (_, index) =>
      benchmark(`b${index}`, "draft", `2026-08-01T${String(index).padStart(2, "0")}:00:00Z`),
    );
    expect(recentBenchmarks({ ...LOADED, benchmarks: many })).toHaveLength(5);
    expect(recentBenchmarks({ ...LOADED, benchmarks: many }, 2)).toHaveLength(2);
  });

  it("is an empty list, not a crash, when nothing loaded", () => {
    expect(recentBenchmarks(EMPTY)).toEqual([]);
    expect(recentSimulations(EMPTY)).toEqual([]);
    expect(pendingForMe(EMPTY)).toEqual([]);
  });
});

describe("pending reviews", () => {
  it("shows only requests still waiting on me", () => {
    const data = {
      ...LOADED,
      pendingReviews: [review("r1", "pending"), review("r2", "approved"), review("r3", "pending")],
    };
    expect(pendingForMe(data).map((view) => view.request.id)).toEqual(["r1", "r3"]);
  });
});
