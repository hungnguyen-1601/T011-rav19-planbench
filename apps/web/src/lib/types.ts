/** TypeScript mirrors of the backend API contract (docs/API_CONTRACT.md). */

export interface Pose2D {
  x: number;
  y: number;
  theta: number;
}

export interface Point2D {
  x: number;
  y: number;
}

export interface MapData {
  name: string;
  width: number;
  height: number;
  resolution: number;
  origin: Pose2D;
  cells: number[]; // 0 free, 100 occupied, -1 unknown (row-major)
}

export interface MapSummary {
  id: string;
  version: number;
  name: string;
  width: number;
  height: number;
  resolution: number;
  checksum: string;
  created_at: string;
}

export interface MapResource {
  id: string;
  version: number;
  checksum: string;
  created_at: string;
  map_data: MapData;
}

export interface RobotConfig {
  radius: number;
  max_linear_velocity: number;
  max_angular_velocity: number;
  max_linear_acceleration: number;
  max_angular_acceleration: number;
}

export interface Scenario {
  name: string;
  description?: string;
  robot: RobotConfig;
  start_pose: Pose2D;
  goal_pose: Pose2D;
  goal_tolerance: number;
  timeout_seconds: number;
  simulation_dt: number;
  static_obstacles?: unknown[];
}

export interface ScenarioResource {
  id: string;
  version: number;
  map_id: string;
  created_at: string;
  scenario: Scenario;
}

export interface SimulationResource {
  id: string;
  map_id: string;
  scenario_id: string;
  algorithm: string;
  state: "created" | "finished";
  created_at: string;
}

export interface ObstacleSnapshot {
  name: string;
  x: number;
  y: number;
  radius: number;
}

export interface TrajectoryPoint {
  time: number;
  x: number;
  y: number;
  theta: number;
  linear_velocity: number;
  angular_velocity: number;
  obstacles?: ObstacleSnapshot[];
}

export interface EpisodeResult {
  status: string;
  reason: string;
  elapsed_time: number;
  steps: number;
  trajectory: TrajectoryPoint[];
  events: { time: number; type: string; message: string }[];
}

export interface EpisodeMetrics {
  status: string;
  success: boolean;
  collision: boolean;
  travel_time: number;
  steps: number;
  trajectory_length: number;
  average_speed: number;
  max_speed: number;
  /** Σ(Δθ_i)², unnormalized — the spec-literal formula. Not comparable
   * across episodes of different length; see smoothness_per_metre. */
  smoothness: number;
  /** Σ|Δθ_i)| / trajectory_length, rad/m — length-normalized. */
  smoothness_per_metre: number;
  planned_path_length: number | null;
  path_efficiency: number | null;
  min_clearance: number | null;
  mean_clearance: number | null;
  global_planning_time: number | null;
  expanded_nodes: number | null;
  mean_local_planning_latency: number | null;
  max_local_planning_latency: number | null;
  local_planning_latency_p50: number | null;
  local_planning_latency_p95: number | null;
  local_planning_latency_p99: number | null;
  stop_and_go_count: number;
}

export interface PlanResult {
  success: boolean;
  path: Point2D[];
  path_length: number;
  cost: number;
  planning_time_seconds: number;
  expanded_nodes: number;
  failure_reason: string;
}

export interface SimulationResultResponse {
  id: string;
  state: string;
  plan: PlanResult | null;
  result: EpisodeResult | null;
  metrics: EpisodeMetrics | null;
}

export type WsMessage =
  | { type: "start"; simulation_id: string; steps: number; plan_path: Point2D[] }
  | {
      type: "state";
      time: number;
      x: number;
      y: number;
      theta: number;
      linear_velocity: number;
      angular_velocity: number;
    }
  | { type: "result"; status: string; reason: string; elapsed_time: number; metrics: EpisodeMetrics }
  | { type: "error"; code: string; message: string };
