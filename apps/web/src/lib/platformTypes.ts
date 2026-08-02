/** Types for the M5/M6/M8 surfaces: library, leaderboard, failures,
 *  background jobs and the agent. Mirrors docs/API_CONTRACT.md. */

export interface LibraryEntry {
  name: string;
  description: string;
  curriculum_index: number;
  dynamic_obstacles: number;
  map_size_m: [number, number];
  timeout_seconds: number;
  /** "dev" (free to tune against) or "holdout" (report-only, P05). */
  split: "dev" | "holdout";
  /** 1 - success_rate of the reference stack over 30 seeds (P03). Null
   *  until scripts/calibrate_difficulty.py has been run. */
  difficulty: number | null;
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

/** What a stack was allowed to see (P02) — declared per algorithm in
 *  the registry, not per run. */
export type ObservationClass =
  | "full_map"
  | "human_states"
  | "lidar_only"
  | "lidar+human_states";

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
  observation_class: ObservationClass | null;
}

/** Entries are grouped by conditions_checksum: rows in different groups
 *  ran under different conditions and are not comparable. */
export interface LeaderboardGroup {
  conditions_checksum: string;
  map_name: string;
  scenario_name: string;
  seeds: number[];
  entries: LeaderboardEntry[];
  /** True when entries here do not all share one observation_class
   *  (P02) — cross-class comparison is still shown, just flagged. */
  mixed_observation_classes: boolean;
}

export interface Leaderboard {
  weights: ScoreWeights;
  score_formula: string;
  groups: LeaderboardGroup[];
  /** Average rank per algorithm across every group it appears in (P04). */
  algorithm_ranks: Record<string, number> | null;
  /** mean(success_rate dev) - mean(success_rate holdout), per algorithm
   *  (P05) — only for algorithms accepted in both splits. */
  generalization_gap: Record<string, number> | null;
  /** (difficulty, success_rate) points per algorithm, sorted by
   *  difficulty (P03) — only for calibrated scenarios. */
  difficulty_curve: Record<string, [number, number][]> | null;
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
  knowledge_documents: number;
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
