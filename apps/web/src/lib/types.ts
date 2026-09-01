/** TypeScript mirrors of the backend API contract (docs/reference/api.md). */

import type { ReplanningConfig } from "./benchmarkTypes";

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

export interface RandomWalkMotion {
  kind: "random_walk";
  origin: Point2D;
  speed: number;
  /** Seconds one heading is held before the next is drawn. */
  change_interval: number;
  /** A step that would leave this distance from `origin` is reflected
   *  back towards it instead, so the walk never wanders off the map. */
  max_radius: number;
  /** Picks *which* sequence of headings this walker gets — two walkers
   *  sharing a value walk the identical shape. Not the same number as
   *  `DynamicObstacle.seed_offset`, which shifts *when* an obstacle's
   *  clock starts; both exist because two obstacles can differ in either
   *  axis independently. */
  seed_offset?: number;
}

/** Constant velocity, then a permanent stop — declared one of two ways.
 *
 * **Exactly one of the two must be given, and the server enforces it.**
 * They are the same motion described from opposite ends: a direction
 * and a duration, or the place it ends up. Allowing both would be two
 * statements free to disagree — a heading pointing north beside a stop
 * point to the east — and there would be no way to say which one the
 * simulator should believe.
 *
 * - `heading` + `stop_time`: travel this way for this long. What the
 *   shipped profiles declare.
 * - `stop_point`: travel to here and park. The direction and the
 *   duration both follow from it, so neither is declared.
 */
export interface SuddenStopMotion {
  kind: "sudden_stop";
  start: Point2D;
  /** Radians. Absent when `stop_point` says where it is going. */
  heading?: number | null;
  speed: number;
  stop_time?: number | null;
  /** Where it comes to rest. Absent when a heading and a duration say
   *  the same thing. */
  stop_point?: Point2D | null;
}

export type Motion = WaypointMotion | PeriodicMotion | RandomWalkMotion | SuddenStopMotion;

export interface DynamicObstacle {
  name: string;
  radius: number;
  motion: Motion;
  /** Seconds of seed-derived head start on this obstacle's clock.
   *
   *  `waypoint`, `periodic` and `sudden_stop` are pure functions of time,
   *  so at zero they ignore the seed and every seed replays the identical
   *  traffic — a variance of zero that is an artefact. The server refuses
   *  that, and refuses a periodic offset below one full period. A
   *  `random_walk` draws its headings from the seed already, so it is
   *  exempt and may legitimately leave this at zero. */
  seed_time_offset?: number;
  /** Mixed into the clock hash, so two obstacles under one seed do not
   *  start their motions in step. Not the same number as
   *  `RandomWalkMotion.seed_offset`, which picks a heading sequence. */
  seed_offset?: number;
}

/** Measurement and actuation error, mirroring `planbench_schemas.sensor`.
 *
 * Optional here because every amplitude defaults to zero on the server,
 * and zero is the only off switch there is: an omitted block and a block
 * of zeroes normalise to the same world. */
export interface SensorNoise {
  lidar_range_sigma_m?: number;
  wheel_slip_fraction?: number;
  localization_drift_m?: number;
  localization_jump_probability?: number;
  lidar_dropout_probability?: number;
  odometry_bias_fraction?: number;
  command_latency_steps?: number;
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
  /** The scenario's physics, not a rule applied to it: two runs at one
   *  seed under different amplitudes are two different worlds. */
  sensor_noise?: SensorNoise;
  /** What a metre hugging the hard boundary costs a global planner
   *  against a metre in the open, minus one. Carried down from the
   *  deployment so it is one number for every candidate; the server
   *  defaults it to 4.0 rather than to zero, so omitting it is not the
   *  same as asking for pure distance. */
  clearance_preference?: number;
  /** The deployment's `stuck_threshold_s`. Omitting it leaves the
   *  simulator's own default, which judges the run by a number nobody
   *  declared. */
  stuck_time_window?: number;
  random_seed?: number;
  progress_time_window?: number;
}

/** Ask the backend where the traffic is at one instant.
 *
 * The browser never evaluates a motion law — every position it draws
 * comes back from `position_at`, the same function the simulator steps
 * with, so a preview cannot disagree with the episode it previews. */
export interface ScenarioPreviewRequest {
  map_id: string;
  scenario: Scenario;
  /** Seconds into the episode; 0 is the pose the robot starts in. */
  time?: number;
  /** Seeded traffic is timed off this, so a preview shows one seed
   *  rather than implying the scenario looks like this for all of them. */
  seed?: number;
  /** Seconds of motion to sample, from 0. Absent asks for the instant
   *  alone — the shape this had before playback existed. */
  duration?: number;
  /** Seconds between samples. Resolution, not frame rate: the client
   *  plays the track back at its own pace. */
  step?: number;
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
  dynamic_obstacles: {
    name: string;
    radius: number;
    position: Point2D;
    /** Where this obstacle goes, sampled every `step` seconds from 0.
     *  Empty on a reply that was asked for one instant, and on one from
     *  a server that predates playback. */
    track?: Point2D[];
  }[];
  /** What the tracks span. Read from here rather than from what was
   *  asked for: the two differ whenever a request was clamped, and a
   *  scrubber labelled longer than its track is the same lie as a canvas
   *  labelled t = 40 showing t = 0. */
  duration?: number;
  step?: number;
}

export interface SimulationResource {
  id: string;
  map_id: string;
  scenario_id: string;
  algorithm: string;
  state: "created" | "finished";
  created_at: string;
  /** The replanning rule this run executed under. Absent on payloads
   *  from a server that predates the field; those runs did not replan. */
  replanning?: ReplanningConfig;
}

/** Một vật cản động tại một thời điểm, để vẽ lại đúng khung hình. */
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
  /** Ground-truth dynamic-obstacle snapshot at this sample — recorded
   *  for replay only, never shown to a planner. Absent on payloads
   *  stored before it was recorded. */
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
  /** Σ|Δθ| chia độ dài quỹ đạo, rad/m — số duy nhất so sánh được giữa
   *  các episode dài ngắn khác nhau, và là số leaderboard chấm điểm.
   *  Tên trường giữ nguyên là ``smoothness`` để client cũ không vỡ;
   *  công thức spec Σ(Δθ)² nằm ở ``smoothness_squared``. */
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

/** One route the global planner returned, and when it took over.
 *
 * `from_time` rather than a step index: the events and the trajectory
 * are stamped by one engine clock, so a replan's moment lands on the
 * frames without arithmetic. */
export interface EpisodePlanRoute {
  attempt: number;
  from_time: number;
  points: Point2D[];
}

/** A library entry, built and drawn without being stored.
 *
 * Shaped so `trafficAt` and `playableSeconds` read it unchanged — the
 * same fields `ScenarioPreview` carries — because a second way to say
 * "where is the traffic at t" is a second answer. */
export interface LibraryPreview {
  library_name: string;
  map: MapData;
  scenario: Scenario;
  dynamic_obstacles: {
    name: string;
    radius: number;
    position: Point2D;
    track?: Point2D[];
  }[];
  duration?: number;
  step?: number;
}

export type WsMessage =
  | {
      type: "start";
      simulation_id: string;
      steps: number;
      plan_path: Point2D[];
      /** Every route, first included. Absent from a server that predates
       *  the field, and empty when the replans could not be placed —
       *  both mean "draw the opening plan and nothing else", never "this
       *  episode never replanned". */
      plans?: EpisodePlanRoute[];
    }
  | {
      type: "state";
      time: number;
      x: number;
      y: number;
      theta: number;
      linear_velocity: number;
      angular_velocity: number;
      /** Where the traffic was at this sample. Optional because a server
       *  older than this field simply omits it, and an absent list must
       *  not be drawn as "the aisle was clear". */
      obstacles?: ObstacleSnapshot[];
    }
  | { type: "result"; status: string; reason: string; elapsed_time: number; metrics: EpisodeMetrics }
  | { type: "error"; code: string; message: string };
