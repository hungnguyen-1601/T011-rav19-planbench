"use client";

/** What the dashboard shows, assembled from endpoints that already exist.
 *
 * No `/dashboard/summary` endpoint was added. Every number here is a
 * count of something the API already returns, so a new endpoint would be
 * a second definition of "how many benchmarks are there" — and the two
 * would eventually disagree. If this ever needs figures the list
 * endpoints cannot give (per-day trends, totals across pages), that is
 * when a server-side summary earns its place.
 *
 * **Nothing is invented.** A section that fails to load is `null`, not
 * zero: "we could not find out" and "there are none" look identical on a
 * stat card and mean opposite things. `partial` says so out loud.
 */

import { authFetch, loadSession } from "./auth";
import { api } from "./api";
import type { BenchmarkResource } from "./benchmarkTypes";
import type { LibraryEntry } from "./platformTypes";
import type { SimulationResource } from "./types";
import type { ReviewRequestView } from "./reviews";

export interface AlgorithmInfo {
  id: string;
  benchmarkable: boolean;
}

export interface DashboardData {
  benchmarks: BenchmarkResource[] | null;
  simulations: SimulationResource[] | null;
  scenarios: LibraryEntry[] | null;
  algorithms: AlgorithmInfo[] | null;
  pendingReviews: ReviewRequestView[] | null;
  online: boolean;
  /** At least one section failed; the rest is still worth showing. */
  partial: boolean;
}

export interface DashboardStats {
  benchmarks: number | null;
  accepted: number | null;
  pendingReviews: number | null;
  scenarios: number | null;
  algorithms: number | null;
  simulations: number | null;
}

const RECENT_LIMIT = 5;

/** Newest first, by `created_at`. */
function byNewest<T extends { created_at: string }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export function summarise(data: DashboardData): DashboardStats {
  return {
    benchmarks: data.benchmarks?.length ?? null,
    accepted: data.benchmarks?.filter((item) => item.state === "accepted").length ?? null,
    pendingReviews: data.pendingReviews?.length ?? null,
    scenarios: data.scenarios?.length ?? null,
    // Reference-only stacks are excluded: the card says "stacks you can
    // benchmark", and counting one you may not benchmark would be a lie
    // that is only visible on the algorithms page.
    algorithms: data.algorithms?.filter((item) => item.benchmarkable).length ?? null,
    simulations: data.simulations?.length ?? null,
  };
}

export function recentBenchmarks(data: DashboardData, limit = RECENT_LIMIT): BenchmarkResource[] {
  return byNewest(data.benchmarks ?? []).slice(0, limit);
}

export function recentSimulations(data: DashboardData, limit = RECENT_LIMIT): SimulationResource[] {
  return byNewest(data.simulations ?? []).slice(0, limit);
}

export function pendingForMe(data: DashboardData, limit = RECENT_LIMIT): ReviewRequestView[] {
  return (data.pendingReviews ?? [])
    .filter((view) => view.request.status === "pending")
    .slice(0, limit);
}

/** Resolve, keeping `null` for whatever failed. */
async function attempt<T>(work: Promise<T>): Promise<T | null> {
  try {
    return await work;
  } catch {
    return null;
  }
}

/**
 * Fetch everything the dashboard needs, tolerating partial failure.
 *
 * Signed out, the account-scoped calls are skipped rather than attempted
 * and caught: a 401 in the console on every visit trains people to
 * ignore the console.
 */
export async function loadDashboard(): Promise<DashboardData> {
  const signedIn = loadSession() !== null;

  const [health, benchmarks, simulations, scenarios, algorithms, inbox] = await Promise.all([
    attempt(api.health()),
    signedIn ? attempt(authFetch<BenchmarkResource[]>("/benchmarks")) : Promise.resolve(null),
    attempt(api.listSimulations()),
    attempt(authFetch<LibraryEntry[]>("/scenario-library")),
    attempt(authFetch<AlgorithmInfo[]>("/algorithms")),
    signedIn
      ? attempt(authFetch<{ requests: ReviewRequestView[]; pending: number }>("/reviews/inbox?pending_only=true"))
      : Promise.resolve(null),
  ]);

  const sections = [benchmarks, simulations, scenarios, algorithms];
  return {
    benchmarks,
    simulations,
    scenarios,
    algorithms,
    pendingReviews: inbox?.requests ?? null,
    online: health !== null,
    partial: health === null || sections.some((section) => section === null),
  };
}
