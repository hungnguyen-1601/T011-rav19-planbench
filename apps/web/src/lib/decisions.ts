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
import { FieldError, authFetch } from "./auth";

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

/** How one episode ended, for one candidate.
 *
 * The four failure reasons are HĐ-6's buckets and they are not
 * interchangeable: thirty collisions and thirty timeouts give the same
 * `success_rate` and ask for completely different work. `success_rate`
 * alone was the whole story until now, and it says how much went wrong
 * without saying which part or how.
 */
export interface EpisodeOutcome {
  episode_context_id: string;
  success: boolean;
  /** Null on success — never "no reason recorded". */
  failure_reason: "no_path" | "collision" | "timeout" | "stuck" | null;
  collision_count: number;
  min_clearance: number;
  travel_time_s: number;
  p99_latency_ms: number;
  /** How many times the stack replanned in this episode.
   *
   * Evidence, never a score: the cost of replanning is time and latency,
   * and both are already charged. Absent on runs recorded before
   * replanning was priced — and 0 would be the true answer for them, but
   * `undefined` says "not recorded" instead of asserting it. */
  replan_count?: number;
}

export interface RunCandidate {
  candidate_id: string;
  stack_label: string;
  local_controller_config: string;
  /** What this candidate was allowed to see.
   *
   * Null means the registry has never heard of the stack, so nobody
   * declared its inputs — rendered as "not declared" rather than as a
   * plausible class, because inventing one would fabricate the single
   * fact a reader checking fairness came for.
   */
  global_observation_class?: string | null;
  local_observation_class?: string | null;
  gates: Record<string, GateVerdict>;
  cleared_gates: boolean;
  blocking_gates: string[];
  n_episodes?: number;
  n_distinct_episodes: number;
  /** Non-null when this candidate was retired before the sweep ended. */
  stopped_early?: StoppedEarly | null;
  success_rate: number;
  pooled_p99_latency_ms: number;
  /** Replans across every episode this candidate ran. See
   *  `EpisodeOutcome.replan_count` — evidence, not a score. */
  replan_count?: number;
  /** Per-episode outcomes, in the order the sweep ran them.
   *
   * **Absent is "not recorded", never "all passed".** Runs stored before
   * this field existed carry no episode rows, and rendering their
   * absence as a clean table would turn a report that measured nothing
   * per-episode into one that measured everything. The list endpoint
   * also strips this — ten warehouse runs of 600 rows each is close to a
   * megabyte on a page that draws none of them — so a component holding
   * a run from `listDecisions` must expect it missing.
   */
  episodes?: EpisodeOutcome[];
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

/** Which two candidates the paired comparison was about.
 *
 * Written by the scoring run from the recommendation itself. The card
 * cannot answer this: `alternative` is a Pareto claim, not the
 * statistical runner-up, and it is null whenever that analysis did not
 * run. Absent on runs scored before the field existed.
 */
export interface ComparisonPair {
  recommended_candidate_id: string;
  runner_up_candidate_id: string;
}

export interface ComparisonReport {
  artifact: string;
  comparison_pair?: ComparisonPair | null;
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

/** File a deployment that is another one with a different map.
 *
 * **Not an edit, and the server enforces that.** A map is the world, and
 * `episode_context_id` does not hash it (HĐ-3.1) — repointing an
 * existing deployment would give two worlds' episodes identical context
 * ids, and trace reuse would then serve episodes recorded on walls that
 * no longer exist. So this takes a `new_id` and refuses the base's.
 *
 * `missions` is optional and usually needed: a start and goal that fit
 * the old map are rarely on free floor in a new one. The server checks
 * before storing, so an unreachable goal is a refusal here rather than a
 * comparison in which every candidate returns no_path and the columns
 * all read a plausible 0.00.
 */
export function deriveTaskProfile(request: {
  base_task_profile_id: string;
  new_id: string;
  map_id: string;
  missions?: { id: string; start: number[]; goal: number[]; probability?: number }[];
}): Promise<TaskProfileSummary> {
  return authFetch<TaskProfileSummary>("/task-profiles/derive", {
    method: "POST",
    body: JSON.stringify(request),
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
/** One episode's trajectory and the map it was driven on.
 *
 * Column-oriented, matching the Parquet file it came from: rewriting a
 * few hundred rows into a few hundred objects would triple the payload
 * to say the same thing.
 */
/** One dynamic obstacle's position at each of the trace's timestamps.
 *
 * **Sampled server-side.** `position_at` is the one implementation of
 * these motion models — seed shift included — and a second copy in
 * TypeScript would drift from it the first time either was fixed. The
 * page receives coordinates and draws circles.
 *
 * Indexed in lockstep with `t`/`x`/`y`, so the obstacle and the robot on
 * one canvas are always the same instant.
 */
export interface ObstacleTrack {
  name: string;
  radius_m: number;
  x: number[];
  y: number[];
}

/** One route the global planner returned, and the step it took over on.
 *
 * `from_index` is a row of this trace, placed server-side from the
 * trace's own replan events — the sidecar counts simulation ticks and
 * the trace counts control steps, and converting between them in the
 * browser would be a third opinion about the episode's timeline.
 *
 * `points` is empty for an attempt that found nothing. That is a real
 * state and not a gap: at that step the robot had no plan, and leaving
 * the previous one on screen would show a route nobody was following.
 */
export interface PlannedRoute {
  attempt: number;
  from_index: number;
  points: { x: number; y: number }[];
}

export interface TracePayload {
  candidate_id: string;
  episode_context_id: string;
  task_profile_id: string;
  metadata: Record<string, unknown>;
  map: {
    name: string;
    width: number;
    height: number;
    resolution: number;
    origin: { x: number; y: number };
    /** One bit per cell, base64. Row-major, row 0 at the map origin. */
    occupied_bits: string;
  };
  robot_radius_m: number;
  /** G4's own budget. The latency chart draws its threshold from this
   *  rather than from a constant, so a deployment that declares a
   *  different control rate gets a different line. */
  control_period_s: number;
  missions: { id: string; start: { x: number; y: number }; goal: { x: number; y: number } }[];
  t: number[];
  x: number[];
  y: number[];
  theta: number[];
  /** From the robot's *surface* (HĐ-8.2), so 0 is the collision
   *  boundary rather than a distance with a radius still to subtract. */
  clearance_m: number[];
  planner_latency_ms: number[];
  /** Sparse — only the steps that carry one. A collision and an arrival
   *  are the same shape of curve; the event is what tells them apart. */
  events: { index: number; event: string }[];
  /** What moved while the robot drove. Empty for a deployment with no
   *  traffic, and empty when the episode context could not be rebuilt —
   *  obstacles drawn at another seed's positions look like evidence. */
  dynamic_obstacles: ObstacleTrack[];
  /** Every route the global planner returned, in order. Empty for a run
   *  recorded before the planning-input sidecar existed — such a run
   *  kept its plans' lengths and threw the polylines away. */
  planned_routes: PlannedRoute[];
}

/** Which line arc length was measured along — and how honest it is.
 *
 * The platform has no planned route to project onto yet (the global
 * plan is written to the episode JSON and older runs have none), so in
 * practice this is a `degraded_*` value today. It is rendered rather
 * than hidden: a progress-synced panel that cannot say what it measured
 * progress against is asking to be believed.
 */
export type ProjectionQuality =
  | "reference_plan"
  | "degraded_candidate_path"
  | "degraded_straight_line";

export interface ProgressSyncRow {
  progress_m: number;
  /** Null where that run never got this far — draw nothing, not a guess. */
  time_a: number | null;
  time_b: number | null;
  cross_track_a: number | null;
  cross_track_b: number | null;
}

export interface DivergencePoint {
  kind: "sustained_cross_track" | "event";
  progress_m: number;
  time_a: number | null;
  time_b: number | null;
  separation_m: number | null;
  event: string | null;
  side: "a" | "b" | null;
}

export interface ReplaySyncView {
  episode_context_id: string;
  candidate_a: string;
  candidate_b: string;
  plan: {
    reference: { points: [number, number][]; quality: ProjectionQuality };
    rows: ProgressSyncRow[];
    backward_samples_a: number;
    backward_samples_b: number;
    /** Fixed server-side text. Rendered verbatim: a caveat the client
     *  can reword is a caveat the client can water down. */
    warning: string;
  };
  divergence: { sustained: DivergencePoint | null; anchors: DivergencePoint[] };
  /** Whose driven path became the ruler, when one did. That candidate's
   *  cross-track offset is zero everywhere by construction. */
  reference_source_candidate_id: string | null;
  /** The E4.3 numbers — E4.3.
   *
   *  `null`, never an empty structure, when they could not be made: the
   *  composite is the deployment's own objective curves, and a run whose
   *  anchors will not resolve has none. Empty would render as a panel
   *  with no differences in it, which reads as "the two are identical" —
   *  the opposite of "this could not be computed".
   */
  running: RunningBlock | null;
}

/** The same computation in the two shapes the page reads it in.
 *
 * Both come from one server-side pass over the same reference line, so
 * a tile under a canvas and the table above it cannot disagree. The
 * browser deriving the tiles from the trace columns it already holds
 * would have been less code and a second implementation of "the running
 * minimum clearance" — free to drift, and the drift invisible, because
 * both would render as clearances.
 */
export interface RunningBlock {
  /** Both candidates paired at each rung of the progress scale. */
  ladder: RunningPoint[];
  /** Each candidate's own series, one entry per row of its trace, so a
   *  tile and the pose drawn beside it are the same instant. */
  by_step: { a: RunningSample[]; b: RunningSample[] };
}

/** One candidate's standing at one rung of the ladder.
 *
 * Mirrors `planbench_explanation.running_metrics.RunningSample`. Every
 * field is dimensionless or normalised to something the deployment
 * declared, so the same row reads the same way in every episode and for
 * every algorithm — and nothing here is a planner-specific counter,
 * because A*, RRT*, and a learned policy share none.
 */
export interface RunningSample {
  progress_fraction: number;
  progress_rate: number;
  elapsed_s: number;
  safety_margin: number;
  exposure_s: number;
  compute_budget: number;
  path_efficiency: number;
  replans: number;
}

export interface RunningPoint {
  progress_m: number;
  a: RunningSample;
  b: RunningSample;
  /** The deployment's safety-versus-efficiency trade-off over the part
   *  of the episode that has happened, as `A − B`. **Not ΔU**: `U_R` is
   *  "did it reach the goal", which has no value halfway through. */
  partial_advantage: number;
  /** Which objectives went into `partial_advantage`, so a reader is
   *  never left to assume it was all four. */
  partial_objectives: string[];
}

export type ExemplarRole =
  | "typical"
  | "strongest_for_winner"
  | "strongest_for_runnerup"
  | "safety_critical";

export interface Exemplar {
  role: ExemplarRole;
  episode_context_id: string;
  delta_utility: number;
  /** The number that chose it: metres of clearance for the safety role,
   *  ΔU for the rest. */
  criterion: number;
  /** Episodes that tied with it, resolved by id. "Worst by a wide
   *  margin" and "worst by a coin flip the recipe made for you" are
   *  different pieces of evidence. */
  tie_break_over: string[];
}

export interface ExemplarSet {
  candidate_a: string;
  candidate_b: string;
  n_episodes: number;
  exemplars: Exemplar[];
}

/** Which four episodes to open with, by a recipe fixed in advance.
 *
 * Rejects with 4xx for a run scored before per-episode utility was
 * stored — three of the four roles are defined on ΔU and nothing left
 * in the report can stand in for it. The page shows the plain episode
 * list in that case rather than a set chosen some other way under a
 * label that says it was preregistered.
 */
/** One detector's summary across the episodes it was looked for in (E3).
 *
 * `episodes_seen` over `episodes_total` is the part that stops one vivid
 * episode reading as a pattern: 1/30 is an anecdote, 27/30 is a property
 * of the pairing. The page renders the fraction rather than a rate for
 * the same reason.
 */
export interface PacketObservation {
  type: string;
  candidate_id: string;
  episodes_seen: number;
  episodes_total: number;
  typical: Record<string, number>;
  worst_episode_context_id: string | null;
}

/** What the contrast lattice concluded about one detection type (E3).
 *
 * Three of the four verdicts are refusals, and they do not mean the same
 * thing — `rules_out_component_specific_attribution` is a *finding*
 * (both stacks do this, so the component is not what differs), while
 * `insufficient_contrast` is a shrug. A page that rendered them alike
 * would turn evidence into silence.
 */
export interface PacketLatticeFinding {
  detection_type: string;
  verdict: string;
  subject: string | null;
  pairs: [string, string][];
  reason: string;
}

/** A gap the platform declares about itself, and what it forbids.
 *
 * Shown rather than hidden: an explanation that lists what it cannot
 * know is worth more than one that quietly stops short.
 */
export interface PacketKnownUnknown {
  id: string;
  blocks_claim_types: string[];
  source: string;
}

export interface PacketWaterfallBar {
  objective: string;
  weight: number;
  delta_objective_mean: number;
  contribution: number;
  ci95: [number, number];
}

export interface PacketWaterfall {
  candidate_a: string;
  candidate_b: string;
  n_episodes: number;
  delta_utility_mean: number;
  delta_utility_median: number;
  total_ci95: [number, number];
  bars: PacketWaterfallBar[];
}

export interface CasePacket {
  run_id: string;
  task: {
    task_profile_id: string;
    robot: { radius_m: number; required_passage_width_m: number | null };
  };
  candidates: { candidate_id: string }[];
  decision: {
    status: string;
    /** `null` on a run that ranked nobody — no pair, so nothing to
     * decompose. Not a failure, and the page must not draw an empty
     * chart for it. */
    waterfall: PacketWaterfall | null;
  };
  lattice: PacketLatticeFinding[];
  observations: PacketObservation[];
  known_unknowns: PacketKnownUnknown[];
  evidence_class: string;
}

/** The case packet, plus an account of what could not be built.
 *
 * `omissions` is not diagnostics: it is what turns a thin explanation
 * from "there was nothing to say" into "this part could not be built,
 * and here is why". The page shows it.
 */
export interface ExplanationView {
  packet: CasePacket;
  omissions: string[];
  skipped_episodes: string[];
}

/** The evidence behind a decision (E4.1/E4.2).
 *
 * Built while the run was scored, so a run recorded before that answers
 * 409 — a state, not a fault, and the caller is expected to render it as
 * one.
 */
export function getExplanation(runId: string): Promise<ExplanationView> {
  return authFetch<ExplanationView>(`/decisions/${runId}/explanation`);
}

export function getExemplars(runId: string): Promise<ExemplarSet> {
  return authFetch<ExemplarSet>(`/decisions/${runId}/exemplars`);
}

/** Both candidates of one episode, placed on arc length (E2).
 *
 * Computed server-side on purpose: projecting in the browser would put
 * a second copy of the arc-length rules in TypeScript, and the copies
 * would disagree the first time either was fixed.
 */
export function getReplaySync(
  runId: string,
  episodeContextId: string,
  candidateA: string,
  candidateB: string,
): Promise<ReplaySyncView> {
  const query = new URLSearchParams({ candidate_a: candidateA, candidate_b: candidateB });
  return authFetch<ReplaySyncView>(
    `/decisions/${runId}/replay-sync/${episodeContextId}?${query.toString()}`,
  );
}

export function getTrace(
  runId: string,
  candidateId: string,
  episodeContextId: string,
): Promise<TracePayload> {
  return authFetch<TracePayload>(
    `/decisions/${runId}/traces/${candidateId}/${episodeContextId}`,
  );
}

export type JobState = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface DecisionJob {
  id: string;
  state: JobState;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  /** Episode *runs*, one per (candidate, episode) pair — thirty
   *  episodes across two candidates is sixty. `total` is 0 until the
   *  sweep reports its first pair. */
  progress: number;
  total: number;
  /** While running, the stack being simulated. On success, the run id. */
  message: string;
  error: string | null;
  /** Only once the sweep finished — before that there is no run. */
  run_id: string | null;
}

export interface CandidateChoice {
  stack: string;
  local_config: string;
}

/** Queue a sweep instead of holding the request open for hours.
 *
 * 202: nothing exists yet. The run appears in `/decisions` when the
 * sweep finishes, and the job carries its id at that point.
 *
 * The queue holds one job — HĐ-7.4 forbids two evaluation runs on one
 * machine at once, because they pin the same cores and each becomes the
 * other's background load. A second request waits.
 */
export function queueDecision(request: {
  task_profile_id: string;
  candidates: CandidateChoice[];
  scope?: string;
  episodes?: number | null;
  reuse_traces?: boolean;
}): Promise<DecisionJob> {
  return authFetch<DecisionJob>("/decisions/jobs", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function listDecisionJobs(): Promise<DecisionJob[]> {
  return authFetch<DecisionJob[]>("/decisions/jobs");
}

export function cancelDecisionJob(jobId: string): Promise<DecisionJob> {
  return authFetch<DecisionJob>(`/decisions/jobs/${jobId}`, { method: "DELETE" });
}

/** Is this job still going? Used to decide whether to keep polling. */
export function jobIsLive(job: DecisionJob): boolean {
  return job.state === "queued" || job.state === "running";
}

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

/** One candidate's episode outcomes, keyed by episode.
 *
 * A map rather than the array because the two candidates in a run do not
 * share an index: early stopping retires one of them mid-sweep, so row
 * seven of one array and row seven of the other can be different
 * episodes. Only the episode id lines them up.
 */
export function outcomesByEpisode(candidate: RunCandidate): Map<string, EpisodeOutcome> {
  return new Map((candidate.episodes ?? []).map((episode) => [episode.episode_context_id, episode]));
}

/** Did any candidate in this run report per-episode outcomes?
 *
 * Used to tell "this run passed every episode" from "this run predates
 * the field", which look identical if you only count failures.
 */
export function hasEpisodeOutcomes(run: DecisionRun): boolean {
  return (run.report?.candidates ?? []).some((candidate) => candidate.episodes !== undefined);
}

/** What a run concluded, as something a person reads at a glance.
 *
 * The list used to print `recommended_candidate_id` — a hex hash. It is
 * the right identity for a trace path and the wrong thing to show
 * somebody scanning ten rows for the run that chose something.
 *
 * `cleared`/`total` travels with the winner because a recommendation out
 * of two survivors and one out of five are different claims, and the
 * gates are what separate them (HĐ-7): a candidate that failed a gate
 * was never ranked at all.
 */
export interface RunOutcome {
  winner: string | null;
  cleared: number;
  total: number;
}

export function runOutcome(run: DecisionRun): RunOutcome {
  const candidates = run.report?.candidates ?? [];
  const recommended = candidates.find(
    (candidate) => candidate.candidate_id === run.recommended_candidate_id,
  );
  return {
    winner: recommended
      ? `${recommended.stack_label} · ${recommended.local_controller_config}`
      : // The hash, only when the report cannot name the winner — better
        // than an em dash on a run that did recommend somebody.
        run.recommended_candidate_id,
    cleared: candidates.filter((candidate) => candidate.cleared_gates).length,
    total: candidates.length,
  };
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

/** A named local-controller configuration, served rather than copied.
 *
 * The parameters travel with the name because the name alone says
 * nothing: `dwa_coarse` and `dwa_default` differ by 7×15 samples against
 * 20×40, which is the entire reason a sampling choice is a *candidate*
 * rather than a constant inside whichever script ran (HĐ-1.3).
 */
export interface LocalControllerConfig {
  /** Which controller this configures. A configuration only means
   *  something for its own controller — `velocity_samples` is a DWA
   *  idea, and offering it beside a PPO policy would be a knob with
   *  nothing behind it. */
  controller: string;
  name: string;
  params: Record<string, number>;
}

export function listLocalControllers(): Promise<LocalControllerConfig[]> {
  return authFetch<LocalControllerConfig[]>("/local-controllers");
}

/** A configuration under test, identified by the hash of what it is.
 *
 * `candidate_id` is **computed by the server** (HĐ-1.3): a hash over the
 * stack, its parameters and its code version. Letting a caller name one
 * would allow two different configurations to share an identity that
 * every trace, pairing and ΔU keys on.
 */
export interface RegisteredCandidate {
  candidate_id: string;
  type: string;
  stack_label: string;
  registered_by: string | null;
  created_at: string;
  spec: Record<string, unknown>;
  /** HĐ-1.6's declaration. **Null is not zero** — the objectives layer
   *  charges an undeclared candidate for the silence rather than
   *  substituting nothing, so the distinction has to survive to the
   *  screen. */
  tuning: Record<string, unknown> | null;
}

export function listCandidates(): Promise<RegisteredCandidate[]> {
  return authFetch<RegisteredCandidate[]>("/candidates");
}

export function registerCandidate(request: {
  stack: string;
  local_config: string;
}): Promise<RegisteredCandidate> {
  return authFetch<RegisteredCandidate>("/candidates", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

/** The local-controller config a registered candidate was built with.
 *
 * Read back out of `spec.params`, which is keyed by controller name —
 * the registration request is not stored, so this is where the choice
 * survives.
 */
export function localConfigOf(
  candidate: RegisteredCandidate,
  configs: LocalControllerConfig[],
): string | null {
  const params = (candidate.spec?.params ?? {}) as Record<string, Record<string, unknown>>;
  const declared = Object.values(params)[0];
  if (!declared) return null;
  const match = configs.find((config) =>
    Object.entries(config.params).every(([key, value]) => declared[key] === value),
  );
  return match?.name ?? null;
}

/** One episode of a deployment, assembled so it can be watched.
 *
 * `episode_context_id` is the real HĐ-3.1 hash of the conditions, not a
 * preview-only label — which is the honest answer to "is this the same
 * episode the comparison will run". It is.
 */
export interface StagedEpisode {
  simulation_id: string;
  scenario_id: string;
  map_id: string;
  episode_context_id: string;
  scenario: Record<string, unknown>;
}

/** Stage one episode of a deployment for the test bench.
 *
 * **What comes back is a simulation, not a measurement.** The conditions
 * are the deployment's own — same `scenario_for` the contract runner
 * calls, same registry entry, same episode seed — so what you watch is
 * what a comparison will run. What is *not* produced is an HĐ-5 trace:
 * nothing here reaches the Metrics Engine, no gate sees it, no card
 * counts it. That is what lets it run beside a live evaluation.
 *
 * The seed is named rather than drawn, because "watch that one again,
 * slower" is the whole point and a server-picked seed would make the one
 * episode worth re-watching the one you cannot get back.
 */
export function stageTestBenchEpisode(
  taskProfileId: string,
  request: { mission_id: string; seed: number; stack: string; local_config: string },
): Promise<StagedEpisode> {
  return authFetch<StagedEpisode>(
    `/task-profiles/${encodeURIComponent(taskProfileId)}/test-bench`,
    { method: "POST", body: JSON.stringify(request) },
  );
}

/** The distinct observation classes a comparison put side by side.
 *
 * **More than one is a finding, not a formatting problem.** A controller
 * reading the static map and one reading only its LiDAR are answering
 * different questions; the gap between their numbers is then mostly the
 * gap between their inputs, and ΔU would be measuring the privilege
 * rather than the planner. Every registry entry declares the same pair
 * today, so this returns one class — which is exactly why it is worth
 * computing now, before the first entry that does not match makes an
 * unlike comparison look like a like one.
 *
 * Undeclared is its own entry rather than being dropped: a stack whose
 * inputs nobody wrote down cannot be shown to match the others.
 */
export function observationClasses(candidates: RunCandidate[]): (string | null)[] {
  const seen: (string | null)[] = [];
  for (const candidate of candidates) {
    const declared = candidate.local_observation_class ?? null;
    if (!seen.includes(declared)) seen.push(declared);
  }
  return seen;
}

/** What deleting a deployment would destroy, as the server counted it. */
export interface DeletionBlocked {
  runs: number;
  ranked?: number;
  reviewed?: number;
  approved: number;
  /** Present only on the refusal no confirmation can answer.
   *
   * A deployment with plain runs asks a question ("delete 7 runs?"). One
   * with an approved run does not: the approval and its review trail are
   * what HĐ-14 exists to keep, so the way through is to withdraw the
   * approval, not to press harder. The ids are here so the dialog can
   * link to the runs instead of leaving somebody to find them. */
  approved_ids?: string[];
}

/** Delete a deployment.
 *
 * **Two outcomes, and the difference is whether anything was measured.**
 * A deployment nobody ran deletes straight away. One with stored runs is
 * refused with a 409 whose body carries the counts — because every run
 * is a statement *about* this deployment, and removing it turns
 * measurements into records of nothing.
 *
 * Resolves to `null` when it deleted, or to the counts when it was
 * refused. The counts are the server's, not a second tally made here:
 * a number the browser worked out for itself would be free to disagree
 * with the one the refusal was based on.
 */
export async function deleteTaskProfile(
  profileId: string,
  options: { deleteRuns?: boolean } = {},
): Promise<DeletionBlocked | null> {
  const query = options.deleteRuns ? "?delete_runs=true" : "";
  try {
    await authFetch<{ id: string; deleted_runs: number }>(
      `/task-profiles/${encodeURIComponent(profileId)}${query}`,
      { method: "DELETE" },
    );
    return null;
  } catch (caught) {
    const blocked = blockedBy(caught);
    if (blocked) return blocked;
    throw caught;
  }
}

/** The counts inside a 409, or null if this was some other failure.
 *
 * Narrow on purpose: an error that is not the "it has runs" refusal must
 * keep travelling, or a network fault would open a confirmation dialog
 * offering to delete measurements that are still there.
 */
function blockedBy(error: unknown): DeletionBlocked | null {
  const first = error instanceof FieldError ? error.raw[0] : undefined;
  if (first && typeof first === "object" && typeof (first as DeletionBlocked).runs === "number") {
    return first as DeletionBlocked;
  }
  return null;
}

/** Take an approval back. The approval stays in the journal.
 *
 * Not an erasure: the approve event remains and a withdraw event lands
 * beside it with the name of whoever took it back. An approval that
 * could vanish silently would be an approval nobody could rely on.
 *
 * Returns to `pending`, not `rejected` — "undecided again" rather than
 * "decided against".
 */
export function withdrawConfig(runId: string, comment: string): Promise<DecisionRun> {
  return authFetch<DecisionRun>(`/decisions/${encodeURIComponent(runId)}/config-approval/withdraw`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}
