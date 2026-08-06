/** Types for the M5/M6/M8 surfaces: library, leaderboard, failures,
 *  background jobs and the agent. Mirrors docs/API_CONTRACT.md. */

import type { ObservationClass } from "./benchmarkTypes";

export type { ObservationClass };

export interface LibraryEntry {
  name: string;
  description: string;
  curriculum_index: number;
  dynamic_obstacles: number;
  map_size_m: [number, number];
  timeout_seconds: number;
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
  /** The class every row here shares; null when the group is mixed. */
  local_observation_class: ObservationClass | null;
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
