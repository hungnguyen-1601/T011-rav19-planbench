/** Types for the M5/M6/M8 surfaces: library, leaderboard, failures,
 *  background jobs and the agent. Mirrors docs/API_CONTRACT.md. */

import type { ObservationClass } from "./benchmarkTypes";

export type { ObservationClass };

/** Evaluation-protocol status of a scenario (P05).
 *
 *  `unassigned` is a real answer, not a missing one: a scenario nobody
 *  has classified — anything created in the app — supports no claim
 *  about generalization, and must never be shown as `dev`. */
export type ScenarioSplit = "dev" | "holdout" | "unassigned";

export interface ScenarioProtocolMetadata {
  scenario_name: string;
  split: ScenarioSplit;
  protocol_version: string;
  /** Why the scenario sits where it does. */
  notes: string | null;
}

export interface LibraryEntry {
  name: string;
  description: string;
  curriculum_index: number;
  dynamic_obstacles: number;
  map_size_m: [number, number];
  timeout_seconds: number;
  /** Protocol status; see `ScenarioSplit`. */
  split: ScenarioSplit;
  protocol_version: string | null;
  split_notes: string | null;
  /** Measured difficulty (P03). Null means uncalibrated — never render
   *  `curriculum_index` in its place; the two disagreeing is the finding. */
  difficulty: DifficultyLabel | null;
}

/** Coarse difficulty band. `unsolved` is kept apart from `hard`: the
 *  baseline never solved it, so it cannot be ordered against anything. */
export type DifficultyBand = "easy" | "moderate" | "hard" | "unsolved";

/** One scenario's measured difficulty against the pinned baseline. */
export interface DifficultyLabel {
  scenario_name: string;
  /** `1 - success_rate(baseline)`, in [0, 1]. */
  value: number;
  ci95: [number, number];
  band: DifficultyBand;
  calibration_version: string;
  baseline_algorithm: string;
  seed_count: number;
  /** False when measured over fewer seeds than the calibration minimum. */
  adequate: boolean;
  /** True when the scenario has changed since it was measured. */
  stale: boolean;
}

/** Whether the calibrated scenarios span a useful range of difficulty. */
export interface DifficultyCoverage {
  calibration_version: string | null;
  scenario_count: number;
  min_difficulty: number | null;
  max_difficulty: number | null;
  spread: number | null;
  band_counts: Record<string, number>;
  /** Scenarios in the interior of the scale — the only ones that can
   *  separate two stacks that are both competent. */
  midrange_count: number;
  uncalibrated: string[];
  warnings: string[];
}

/** What the baseline was pinned to when the scale was measured. */
export interface DifficultyBaseline {
  algorithm: string;
  algorithm_config: Record<string, unknown>;
  replanning_enabled: boolean;
  seeds: number[];
  robot_profile: Record<string, unknown>;
  benchmark_spec_version: string;
  protocol_version: string | null;
  git_sha: string;
}

export interface DifficultyCalibrationSummary {
  calibration_version: string | null;
  baseline: DifficultyBaseline | null;
  scenarios: DifficultyLabel[];
  coverage: DifficultyCoverage;
  notes: string | null;
}

/** One metric the dev/held-out gap is computed on. */
export interface GapMetric {
  name: string;
  /** The gap is always `dev - holdout`; this says which sign is bad. */
  higher_is_better: boolean;
}

export interface SplitSummary {
  split: ScenarioSplit;
  scenarios: string[];
  report_count: number;
  episodes: number;
  metrics: Record<string, number>;
  metric_scenario_counts: Record<string, number>;
  statistically_adequate: boolean;
}

export interface GeneralizationEntry {
  algorithm: string;
  dev: SplitSummary | null;
  holdout: SplitSummary | null;
  /** `dev - holdout` per metric; null when either side is missing. */
  gap: Record<string, number> | null;
  warnings: string[];
}

export interface HoldoutUse {
  benchmark_id: string | null;
  benchmark_name: string;
  scenario_name: string;
  algorithms: string[];
  seed_count: number;
  finished_at: string | null;
}

export interface GeneralizationSummary {
  entries: GeneralizationEntry[];
  metrics: GapMetric[];
  protocol_versions: string[];
  dev_scenarios: string[];
  holdout_scenarios: string[];
  unassigned_report_count: number;
  /** Every recorded look at a held-out scenario. */
  holdout_usage: HoldoutUse[];
  warnings: string[];
}

export interface ImportedScenario {
  library_name: string;
  map_id: string;
  scenario_id: string;
}

export interface ScoreWeights {
  success: number;
  safety: number;
  efficiency: number;
  smoothness: number;
}

export interface LeaderboardEntry {
  algorithm: string;
  benchmark_id: string;
  benchmark_name: string;
  conditions_checksum: string;
  map_name: string;
  scenario_name: string;
  episodes: number;
  success_rate: number;
  collision_rate: number;
  mean_travel_time: number | null;
  mean_path_efficiency: number | null;
  mean_smoothness: number | null;
  worst_min_clearance: number | null;
  mean_local_planning_latency: number | null;
  overall_score: number | null;
  /** What the stack was declared to see when it ran (P02). Null on rows
   *  stored before the declaration existed — unknown, not "the same". */
  global_observation_class: ObservationClass | null;
  local_observation_class: ObservationClass | null;
  requires_global_path: boolean | null;
}

/** Entries are grouped by conditions_checksum *and* observation class:
 *  rows in different groups either ran under different conditions or
 *  were shown different things, and are not comparable. */
export interface LeaderboardGroup {
  conditions_checksum: string;
  map_name: string;
  scenario_name: string;
  seeds: number[];
  entries: LeaderboardEntry[];
  /** The classes every row here shares; null when the group is mixed on
   *  that layer. Both layers are part of the grouping key: replanning
   *  upgrades the global class only, and a stack allowed to replan saw
   *  strictly more than one that was not. */
  local_observation_class: ObservationClass | null;
  global_observation_class: ObservationClass | null;
  /** True when the rows were not shown the same thing. */
  cross_observation_class_warning: boolean;
}

export interface Leaderboard {
  weights: ScoreWeights;
  score_formula: string;
  groups: LeaderboardGroup[];
}

export type Confidence = "high" | "medium" | "low";

export interface Evidence {
  kind: string;
  detail: string;
  time: number | null;
  value: number | null;
}

export interface Finding {
  category: string;
  confidence: Confidence;
  summary: string;
  evidence: Evidence[];
}

export interface FailureReport {
  status: string;
  primary: Finding;
  contributing: Finding[];
}

export type JobState = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface JobStatus {
  id: string;
  state: JobState;
  progress: number;
  total: number;
  message: string;
  error: string | null;
}

// -- agent (M8) ---------------------------------------------------------

export interface ProviderInfo {
  name: string;
  ready: boolean;
  api_key_env: string;
  missing: string;
}

export interface AgentCapabilities {
  provider: string;
  model: string;
  /** True means the answer was keyword-matched offline, not model-written. */
  deterministic: boolean;
  tools: string[];
  forbidden: string[];
  providers: ProviderInfo[];
}

export interface ChatTurn {
  text: string;
  tools_used: string[];
  tool_errors: string[];
  iterations: number;
  truncated: boolean;
}

export interface ChatResponse {
  provider: string;
  model: string;
  deterministic: boolean;
  turn: ChatTurn;
}

export interface MissionDraft {
  name: string;
  description: string;
  scenario: string;
  algorithms: string[];
  seeds: number[];
}

export interface MissionRefusal {
  reason: string;
  errors: string[];
}

export interface AgentEvent {
  timestamp: string;
  state: string;
  action: string;
  detail: string;
}

export interface AgentSession {
  id: string;
  provider: string;
  model: string;
  deterministic: boolean;
  state: string;
  mission: string;
  benchmark_id: string | null;
  events: AgentEvent[];
}

export interface AgentBenchmarkSummary {
  id: string;
  name: string;
  state: string;
  map_id: string;
  scenario_id: string;
  scenario_name: string | null;
  algorithms: string[];
  seeds: number[];
  created_by: string;
  conditions_checksum: string | null;
}

export interface MissionResponse {
  session: AgentSession;
  draft: MissionDraft | null;
  refusal: MissionRefusal | null;
  benchmark: AgentBenchmarkSummary | null;
  next_step: string;
}

export interface Citation {
  kind: string;
  locator: string;
  title: string;
  uri: string | null;
}

export interface EvidenceItem {
  citation: Citation;
  statement: string;
  value: number | null;
}

export interface EvidenceBundle {
  question: string;
  items: EvidenceItem[];
}

export interface GeneratedReport {
  text: string;
  /** Ids verified against the evidence bundle before the text is returned. */
  citations: string[];
  refused: boolean;
  refusal_reason: string;
  provisional: boolean;
  provider: string;
  model: string;
  deterministic: boolean;
  evidence_count: number;
}
