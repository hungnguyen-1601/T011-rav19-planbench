/** Benchmark contract mirrored from the backend. */

import type { ReviewRequestView } from "./reviews";
import type { EpisodeMetrics, TrajectoryPoint } from "./types";

export type BenchmarkState =
  | "draft"
  | "pending_approval"
  | "approved"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"
  | "pending_review"
  | "accepted"
  | "rejected";

export interface AlgorithmInfo {
  id: string;
  kind: string;
  description: string;
  benchmarkable: boolean;
  config_schema: Record<string, unknown>;
}

export interface AlgorithmSpec {
  id: string;
  config: Record<string, unknown>;
}

export interface BenchmarkSpec {
  name: string;
  description: string;
  algorithms: AlgorithmSpec[];
  seeds: number[];
  spec_version: string;
}

export interface ApprovalRecord {
  benchmark_id: string;
  /** Nickname at the time of the decision — display only. */
  user: string;
  /** The identity that acted. Empty on rows written before accounts. */
  user_id: string;
  role: string;
  action: string;
  previous_state: BenchmarkState;
  new_state: BenchmarkState;
  comment: string;
  timestamp: string;
  /** Set when the decision answered a review request. */
  review_request_id: string | null;
}

export interface BenchmarkResource {
  id: string;
  spec: BenchmarkSpec;
  map_id: string;
  scenario_id: string;
  state: BenchmarkState;
  created_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  approvals: ApprovalRecord[];
  report_artifact_uri: string | null;
  /** Ownership and pending reviews, resolved by the API for the caller.
   *  Used to decide what to show; the backend decides what to allow. */
  owner_user_id: string;
  is_owner: boolean;
  review_requests: ReviewRequestView[];
}

export interface FairnessRecord {
  map_name: string;
  map_checksum: string;
  scenario_name: string;
  scenario_checksum: string;
  seeds: number[];
  timeout_seconds: number;
  simulation_dt: number;
  robot_radius: number;
  max_linear_velocity: number;
  max_angular_velocity: number;
  lidar_num_rays: number;
  lidar_max_range: number;
  conditions_checksum: string;
}

export interface RunRecord {
  algorithm: string;
  seed: number;
  status: string;
  reason: string;
  metrics: EpisodeMetrics;
  trajectory_points: number;
  episode_index: number;
}

export interface AlgorithmAggregate {
  algorithm: string;
  episodes: number;
  success_rate: number;
  collision_rate: number;
  timeout_rate: number;
  stuck_rate: number;
  no_progress_rate: number;
  no_global_path_rate: number;
  mean_travel_time_successful: number | null;
  mean_trajectory_length_successful: number | null;
  mean_path_efficiency_successful: number | null;
  mean_smoothness_successful: number | null;
  mean_min_clearance: number | null;
  worst_min_clearance: number | null;
  mean_local_planning_latency: number | null;
  max_local_planning_latency: number | null;
  mean_global_planning_time: number | null;
}

export interface BenchmarkReport {
  spec: BenchmarkSpec;
  fairness: FairnessRecord;
  runs: RunRecord[];
  aggregates: AlgorithmAggregate[];
}

export interface BenchmarkResults {
  benchmark: BenchmarkResource;
  report: BenchmarkReport | null;
}

export interface EpisodeSummary {
  id: string;
  benchmark_id: string;
  algorithm: string;
  seed: number;
  created_at: string;
  record: RunRecord;
  artifact_uri: string;
  artifact_checksum: string;
  artifact_bytes: number;
}

export interface EpisodeReplay {
  id: string;
  algorithm: string;
  seed: number;
  plan_path: { x: number; y: number }[];
  trajectory: TrajectoryPoint[];
  events: { time: number; type: string; message: string }[];
  metrics: EpisodeMetrics;
}
