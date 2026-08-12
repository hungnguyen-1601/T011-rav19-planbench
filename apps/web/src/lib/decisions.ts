"use client";

/** Selection runs: the evidence, and the recommendation when there is one.
 *
 * **A run is the record; a card is something a run sometimes produces.**
 * Four of the first five comparisons this platform ran produced no
 * Decision Card, because a card needs two candidates through all six
 * gates and only one got there. Each of those runs still answered "who
 * was eliminated where, after how many runs" — the question HĐ-12 puts
 * on a card in the first place.
 *
 * That shapes every type here. `card` is nullable, `report` is not, and
 * nothing in this module treats a missing card as an error state. A UI
 * that could only render a Decision Card would recreate the pressure to
 * make every run rankable, and that pressure is what produced a card
 * bounding a collision probability off a single episode.
 */

import { API_BASE } from "./api";
import { authFetch } from "./auth";

/** Which artifact a run produced. `comparison` covers both a comparison
 *  that could be ranked and one that could not — the card's presence is
 *  the distinction. */
export type ArtifactKind = "decision_card" | "comparison" | "measurement";

/** Has a human read this run's evidence? Applies to every run. */
export type ReviewState = "unreviewed" | "reviewed";

/** Is this run's recommendation the configuration we deploy?
 *
 * `not_applicable` where there is no card — not a missing value but a
 * statement: this run recommends nobody, so there is nothing to approve.
 */
export type ConfigState = "not_applicable" | "pending" | "approved" | "rejected";

/** One gate's verdict.
 *
 * The wire shape is deliberately mixed: a gate with nothing to explain
 * serialises as the bare string `"pass"`, while one carrying evidence
 * serialises as an object. Both are rendered as the same badge, because
 * a table where G1 is plain text and G2 is a coloured chip reads as if
 * they were different kinds of judgement — they are not.
 */
export type GateVerdict = { result: "pass" | "fail"; [field: string]: unknown } | "pass" | "fail";

/** The verdict, whichever shape it arrived in. */
export function gateResult(verdict: GateVerdict | undefined): "pass" | "fail" | undefined {
  if (verdict === undefined) return undefined;
  return typeof verdict === "string" ? verdict : verdict.result;
}

/** Everything the gate said beyond pass/fail, as label → value.
 *
 * Empty for a bare-string verdict, which is the honest answer: that gate
 * had nothing to add. Never invented, because "G3: fail" with fabricated
 * numbers beside it is worse than "G3: fail" alone.
 */
export function gateEvidence(verdict: GateVerdict | undefined): [string, string][] {
  if (verdict === undefined || typeof verdict === "string") return [];
  return Object.entries(verdict)
    .filter(([key, value]) => key !== "result" && value !== null && value !== undefined)
    .map(([key, value]) => [key, String(value)]);
}

/** Why a candidate stopped before the others (early stop).
 *
 * Its presence means this candidate's row rests on fewer episodes than
 * the rest of the table, which qualifies every number in that row.
 */
export interface StoppedEarly {
  episodes_run: number;
  episodes_planned: number;
  gate: string;
  rule: string;
  evidence?: Record<string, unknown>;
}

export interface RunCandidate {
  candidate_id: string;
  stack_label: string;
  local_controller_config: string;
  gates: Record<string, GateVerdict>;
  cleared_gates: boolean;
  blocking_gates: string[];
  n_episodes?: number;
  n_distinct_episodes: number;
  /** Non-null when this candidate was retired before the sweep ended. */
  stopped_early?: StoppedEarly | null;
  success_rate: number;
  pooled_p99_latency_ms: number;
}

export interface RunSample {
  n_episodes: number;
  /** What was asked for, beside what was measured. Without it an
   *  interrupted run reads as a deliberate short one. */
  n_episodes_requested?: number;
  interrupted?: boolean;
  n_min_required: number;
  episode_context_ids: string[];
}

export interface ComparisonReport {
  artifact: string;
  identity: {
    task_profile_id: string;
    experiment_scope: string;
    sensor_noise: { lidar_range_sigma_m: number; wheel_slip_fraction: number };
    git_sha: string;
    anchor_config_version: string;
    created_at: string;
  };
  sample: RunSample;
  candidates: RunCandidate[];
  measurement_environment: {
    benchmark_host: Record<string, unknown>;
    warning: string | null;
  };
  /** Present and null on a ranked run, so a reader never has to know
   *  which branch produced the report. */
  decision_card: unknown | null;
  /** Why no card — and it says which of two situations this is. */
  why_no_card?: string;
  /** Non-null when the deployment itself cannot rank (HĐ-8.4). Distinct
   *  from "nobody survived": no candidate would ever change this one. */
  gate_only_deployment?: string | null;
  checks?: string[];
  early_stop?: {
    enabled: boolean;
    min_episodes_before_stop: number;
    stopped: { candidate_id: string; gate: string; episodes_run: number }[];
  } | null;
  run_uri?: string | null;
  run_checksum?: string | null;
}

export interface DecisionCard {
  contracts_version: string;
  recommendation_scope?: string;
  experiment_scope: string;
  decision_mode: string;
  decision_mode_label?: string;
  status: string;
  recommended: { candidate_id: string; stack: string; params_ref: string | null };
  alternative: { candidate_id: string; stack: string } | null;
  decision_utility: number;
  pareto_label: string;
  evidence: {
    delta_u_vs_second: number;
    delta_u_mean?: number;
    ci95: [number, number];
    n_episodes: number;
    effect_size: number;
    weight_stability_margin: number | null;
    anchor_stability: string | null;
    robustness_margin: number | null;
  };
  declared_assumptions?: string[];
  manifest_ref: string;
}

export interface DecisionRun {
  id: string;
  task_profile_id: string;
  artifact_kind: ArtifactKind;
  experiment_scope: string | null;
  contracts_version: string;
  created_at: string;
  created_by: string | null;
  /** `false` means the field could not be ranked. Not an error — the
   *  gate table still says who was eliminated where. */
  ranked: boolean;
  recommended_candidate_id: string | null;
  status: string | null;
  report: ComparisonReport;
  card: DecisionCard | null;
  review_state: ReviewState;
  reviewed_by: string | null;
  reviewed_at: string | null;
  config_state: ConfigState;
  config_decided_by: string | null;
  config_decided_at: string | null;
}

export interface ReviewEvent {
  sequence: number;
  action: "review" | "approve_config" | "reject_config";
  actor_user_id: string | null;
  username: string;
  previous_state: string;
  new_state: string;
  comment: string;
  created_at: string;
}

export interface TaskProfileSummary {
  id: string;
  environment: string;
  owner_user_id: string | null;
  created_at: string;
  profile: Record<string, unknown>;
}

export function listDecisions(filters?: {
  taskProfileId?: string;
  ranked?: boolean;
}): Promise<DecisionRun[]> {
  const query = new URLSearchParams();
  if (filters?.taskProfileId) query.set("task_profile_id", filters.taskProfileId);
  if (filters?.ranked !== undefined) query.set("ranked", String(filters.ranked));
  const suffix = query.toString() ? `?${query}` : "";
  return authFetch<DecisionRun[]>(`/decisions${suffix}`);
}

export function getDecision(runId: string): Promise<DecisionRun> {
  return authFetch<DecisionRun>(`/decisions/${runId}`);
}

export function listDecisionEvents(runId: string): Promise<ReviewEvent[]> {
  return authFetch<ReviewEvent[]>(`/decisions/${runId}/audit`);
}

export function listTaskProfiles(): Promise<TaskProfileSummary[]> {
  return authFetch<TaskProfileSummary[]>("/task-profiles");
}

export function getTaskProfile(profileId: string): Promise<TaskProfileSummary> {
  return authFetch<TaskProfileSummary>(`/task-profiles/${profileId}`);
}

/** File a deployment. The server validates it against HĐ-2 and refuses
 *  to redefine an existing id with different content — so this can 409,
 *  and that 409 is the guard that keeps stored runs describing the world
 *  they were actually measured in. */
export function createTaskProfile(profile: unknown): Promise<TaskProfileSummary> {
  return authFetch<TaskProfileSummary>("/task-profiles", {
    method: "POST",
    body: JSON.stringify(profile),
  });
}

/** Record that somebody read this run's evidence.
 *
 * Allowed on every run, including the ones that recommend nobody — which
 * is the whole reason it is a separate act from approving a config.
 */
export function reviewRun(runId: string, comment: string): Promise<DecisionRun> {
  return authFetch<DecisionRun>(`/decisions/${runId}/review`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

/** Approve or reject this run's recommendation as the deployed config.
 *
 * 409 when the run has no card, when it was already decided, or when the
 * caller started it (HĐ-14, separation of duties). The UI does not
 * pre-empt any of those: the server owns the rule, and a second copy
 * here would be free to disagree with it.
 */
export function decideConfig(
  runId: string,
  decision: "approve" | "reject",
  comment: string,
): Promise<DecisionRun> {
  return authFetch<DecisionRun>(`/decisions/${runId}/config-approval`, {
    method: "POST",
    body: JSON.stringify({ decision, comment }),
  });
}

/** Where the approved configuration is served from.
 *
 * A URL rather than a fetch: it is a file somebody saves, the endpoint
 * returns text/plain, and letting the browser do the download keeps the
 * filename the server chose.
 */
export function approvedConfigUrl(runId: string): string {
  return `${API_BASE}/api/v1/decisions/${runId}/approved_config.yaml`;
}

/** The six gates, in contract order. Rendered in this order always, so
 *  a reader comparing two runs is comparing the same rows. */
export const GATES = ["G1", "G2", "G3", "G4", "G5", "G6"] as const;

/** Why this run produced no card — reduced to the one thing a reader
 *  has to do about it.
 *
 * Three outcomes, three different next actions, and collapsing them into
 * "no card" is what makes a gate table read like a failure:
 *
 * - `interrupted` — the run stopped early; what it did measure is valid
 *   and smaller. Run the rest.
 * - `gate_only` — this *deployment* cannot rank at all. No candidate
 *   would ever change that; use one whose threshold leaves room above it.
 * - `no_survivors` — fewer than two candidates cleared the gates.
 *   Register a better candidate. Never a softer deployment.
 */
export type NoCardReason = "interrupted" | "gate_only" | "no_survivors" | null;

export function noCardReason(run: DecisionRun): NoCardReason {
  if (run.ranked) return null;
  if (run.report?.sample?.interrupted) return "interrupted";
  if (run.report?.gate_only_deployment) return "gate_only";
  return "no_survivors";
}

/** How many of the requested episodes a run actually covers.
 *
 * `undefined` when the report predates the field, which is different
 * from "covered everything" and must not render as 100%.
 */
export function coverage(run: DecisionRun): number | undefined {
  const requested = run.report?.sample?.n_episodes_requested;
  const measured = run.report?.sample?.n_episodes;
  if (!requested || measured === undefined) return undefined;
  return measured / requested;
}

/** Did this candidate clear every gate? Reads the stored verdict rather
 *  than re-deriving it from `blocking_gates`, so the badge and the table
 *  cannot disagree. */
export function cleared(candidate: RunCandidate): boolean {
  return candidate.cleared_gates;
}
