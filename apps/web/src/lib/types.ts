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

export interface CircleObstacle {
  type: "circle";
  center: Point2D;
  radius: number;
}

export interface RectangleObstacle {
  type: "rectangle";
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
}

export type StaticObstacle = CircleObstacle | RectangleObstacle;

/** Motion laws, mirroring `planbench_schemas.dynamic`. The UI authors
 *  these and sends them to the backend; it never evaluates them — see
 *  `ObstacleMarker` in MapCanvas. */
export interface WaypointMotion {
  kind: "waypoint";
  waypoints: Point2D[];
  speed: number;
  loop?: boolean;
  ping_pong?: boolean;
}

export interface PeriodicMotion {
  kind: "periodic";
  start: Point2D;
  end: Point2D;
  period: number;
  phase?: number;
}

export type Motion = WaypointMotion | PeriodicMotion;

export interface DynamicObstacle {
  name: string;
  radius: number;
  motion: Motion;
  /** Seconds of seed-derived head start. Zero means every seed replays
   *  the identical traffic, which reports a variance of zero that is not
   *  real — the editor defaults it above zero for that reason. */
  seed_time_offset?: number;
  seed_offset?: number;
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
  static_obstacles?: StaticObstacle[];
  dynamic_obstacles?: DynamicObstacle[];
  random_seed?: number;
  progress_time_window?: number;
}

export interface ScenarioResource {
  id: string;
  version: number;
  map_id: string;
  created_at: string;
  scenario: Scenario;
  /** Evaluation split (P05), resolved server-side. Anything authored in
   *  the app is `unassigned` and cannot be changed from here. */
  split: "dev" | "holdout" | "unassigned";
}

export interface ValidationReport {
  valid: boolean;
  errors: string[];
}

/** Obstacle positions at one instant, computed by the backend. */
export interface ScenarioPreview {
  time: number;
  seed: number;
  valid: boolean;
  errors: string[];
  dynamic_obstacles: { name: string; radius: number; position: Point2D }[];
}

export interface SimulationResource {
  id: string;
  map_id: string;
  scenario_id: string;
  algorithm: string;
  state: "created" | "finished";
  created_at: string;
}

export interface TrajectoryPoint {
  time: number;
  x: number;
  y: number;
  theta: number;
  linear_velocity: number;
  angular_velocity: number;
  /** Ground-truth dynamic-obstacle snapshot at this sample — recorded
   *  for replay only, never shown to a planner. Absent on payloads
   *  stored before it was recorded. */
  obstacles?: { name: string; x: number; y: number; radius: number }[];
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
  smoothness: number;
  planned_path_length: number | null;
  path_efficiency: number | null;
  min_clearance: number | null;
  mean_clearance: number | null;
  global_planning_time: number | null;
  expanded_nodes: number | null;
  // F05 additions — absent (undefined) on payloads stored before them,
  // null when not computed. Never coalesce to 0.
  mean_local_planning_latency?: number | null;
  max_local_planning_latency?: number | null;
  smoothness_squared?: number | null;
  local_planning_latency_p50?: number | null;
  local_planning_latency_p95?: number | null;
  local_planning_latency_p99?: number | null;
  stop_and_go_count?: number | null;
  near_miss_count?: number | null;
  time_to_first_collision?: number | null;
  metric_config?: MetricConfig | null;
  // How many extra global paths the stack asked for. 0 whenever
  // replanning was off, which is every run before the feature existed.
  replan_count?: number | null;
}

export interface MetricConfig {
  version: string;
  stop_speed_threshold: number;
  resume_speed_threshold: number;
  near_miss_clearance_threshold: number;
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
