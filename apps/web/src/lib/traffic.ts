/** Authoring moving traffic on a deployment, as plain data.
 *
 * **Everything here builds or reshapes a document; nothing here judges
 * one.** The deployment form decides nothing — `TaskProfile` on the
 * server is the single statement of HĐ-2 — and that rule does not get
 * softer for being moved into a helper module. So there is no function
 * below that answers "is this legal": the verdict comes from
 * `POST /task-profiles/validate`, which runs the same check filing runs.
 *
 * What is here instead are the two things a form legitimately owns.
 * *Shapes*: what a `periodic` motion looks like when somebody picks it
 * out of a dropdown. And *defaults*: a starting value that does not walk
 * the author into a refusal on their first click. `withNoiseDefaults`
 * and `posesFor` already do exactly this, and for the same reason —
 * offering a blank field where a sensible number exists is not
 * neutrality, it is just a worse first draft.
 *
 * It lives apart from the component because the web tests run on Node
 * with no DOM: a reducer can be tested directly, a click cannot.
 */

import { type PlayableTraffic, trafficAt } from "@/lib/previewPlayback";
import type { ProfileDraft } from "./deployments";
import type {
  DynamicObstacle,
  Motion,
  ObstacleSnapshot,
  Point2D,
  Pose2D,
  Scenario,
  ScenarioPreview,
  ScenarioPreviewRequest,
} from "./types";

/** What the next click on the map does to the traffic being authored.
 *
 * Named per *field* rather than per obstacle: the author places the end
 * of a patrol, not "the obstacle". The mode lives on the form beside the
 * mission's own two, because a canvas with two components each believing
 * the next click is theirs drops a goal where a waypoint belonged.
 */
export type TrafficPlacement =
  | "waypoint"
  | "periodic-start"
  | "periodic-end"
  | "random-walk-origin"
  | "sudden-stop-start"
  | "sudden-stop-heading"
  | "sudden-stop-point";

export const MOTION_KINDS = ["waypoint", "periodic", "random_walk", "sudden_stop"] as const;

export type MotionKind = (typeof MOTION_KINDS)[number];

/** How a `sudden_stop` says where it comes to rest.
 *
 * Two descriptions of one motion, from opposite ends: a direction and
 * a duration, or the place it ends up. The server accepts exactly one
 * — both together would be two statements free to disagree, with
 * nothing to say which the simulator should believe.
 */
export type StopMode = "time" | "point";

/** Where a sudden stop comes to rest, whichever way it was declared.
 *
 * **The stored form never carries `stop_point`, and that is deliberate.**
 * The server resolves it to `heading` and `stop_time` while validating
 * and drops it, because `_scenario_checksum` dumps without
 * `exclude_none` — so a stored optional field would add `stop_point:
 * null` to every scenario with a sudden stop, change its checksum, and
 * orphan every benchmark report and golden trajectory recorded against
 * it.
 *
 * The consequence is that an author who placed the stop by clicking a
 * spot reopens the deployment and sees a direction and a duration
 * instead. Nothing was lost — those two describe the same motion, and
 * this returns exactly the spot that was clicked — but a form that
 * shows neither the point nor any hint that it still exists reads as
 * one that threw the setting away.
 *
 * Returns null only when the motion has no stop to speak of.
 */
export function stopPointOf(motion: Motion): { x: number; y: number } | null {
  if (motion.kind !== "sudden_stop") return null;
  if (motion.stop_point) return motion.stop_point;
  const { start, speed, heading, stop_time } = motion;
  // Read into locals so the narrowing survives: `positive` answers a
  // question, it does not tell the type checker what it learned.
  if (typeof speed !== "number" || typeof stop_time !== "number") return null;
  if (typeof heading !== "number" || speed <= 0 || stop_time <= 0) return null;
  const distance = speed * stop_time;
  return point(start.x + Math.cos(heading) * distance, start.y + Math.sin(heading) * distance);
}

export function stopMode(motion: Motion): StopMode {
  return motion.kind === "sudden_stop" && motion.stop_point ? "point" : "time";
}

/** Which placement modes a motion offers, in the order they are used.
 *
 * A function rather than a table, because `sudden_stop` now offers two
 * different second buttons depending on how it declares its stop — and
 * a toolbar showing both would offer the author a way to write the
 * document the server refuses.
 */
export function placementsFor(motion: Motion): TrafficPlacement[] {
  switch (motion.kind) {
    case "waypoint":
      return ["waypoint"];
    case "periodic":
      return ["periodic-start", "periodic-end"];
    case "random_walk":
      return ["random-walk-origin"];
    case "sudden_stop":
      return stopMode(motion) === "point"
        ? ["sudden-stop-start", "sudden-stop-point"]
        : ["sudden-stop-start", "sudden-stop-heading"];
  }
}

const DEGREES = 180 / Math.PI;

/** The traffic a draft carries, as a list this module can work with.
 *
 * `ProfileDraft` is deliberately loose — the shape is the server's to
 * define, and a mirrored interface in TypeScript would be the second
 * definition `lib/deployments` exists to avoid. That looseness has to
 * end *somewhere* to be usable, and one narrowing function is a better
 * place than a cast at every call site.
 */
export function trafficOf(draft: ProfileDraft | null): DynamicObstacle[] {
  const environment = draft?.environment;
  if (!environment || typeof environment !== "object") return [];
  const list = (environment as Record<string, unknown>).dynamic_obstacles;
  return Array.isArray(list) ? (list as DynamicObstacle[]) : [];
}

function point(x: number, y: number): Point2D {
  return { x, y };
}

/** A motion of the chosen kind, laid out around `anchor`.
 *
 * The anchor is somewhere the author is already looking — the mission
 * start — so a new obstacle appears on screen rather than at the map's
 * origin, which on most maps is a corner behind a wall.
 */
export function blankMotion(kind: MotionKind, anchor: Point2D): Motion {
  switch (kind) {
    case "waypoint":
      return {
        kind: "waypoint",
        waypoints: [point(anchor.x, anchor.y), point(anchor.x + 4, anchor.y)],
        speed: 0.6,
        loop: false,
        ping_pong: true,
      };
    case "periodic":
      return {
        kind: "periodic",
        start: point(anchor.x, anchor.y),
        end: point(anchor.x, anchor.y + 4),
        period: 12,
        phase: 0,
      };
    case "random_walk":
      return {
        kind: "random_walk",
        origin: point(anchor.x, anchor.y),
        speed: 0.5,
        change_interval: 1.5,
        max_radius: 2,
        seed_offset: 0,
      };
    case "sudden_stop":
      // Opens in the mode the shipped profiles use, so a new obstacle
      // is the same shape as the ones already on file.
      return {
        kind: "sudden_stop",
        start: point(anchor.x, anchor.y),
        heading: 0,
        speed: 0.8,
        stop_time: 4,
      };
  }
}

/** Switch how a sudden stop declares where it ends.
 *
 * **Built fresh, like `changeMotionKind`, and for the same reason.**
 * The server takes exactly one description; leaving the other's fields
 * behind would send a document it refuses — and if it ever stopped
 * refusing, a stale heading beside a stop point would be a second
 * opinion about which way the obstacle goes.
 *
 * The switch keeps what carries over honestly. Going to a point, the
 * stop point starts where the old heading and duration would have put
 * the obstacle — the same motion, said the other way, so the picture
 * on the map does not jump. Coming back, the heading and duration are
 * read off the point for the same reason.
 */
export function withStopMode(motion: Motion, mode: StopMode): Motion {
  if (motion.kind !== "sudden_stop" || stopMode(motion) === mode) return motion;
  const { start, speed } = motion;
  if (mode === "point") {
    const heading = motion.heading ?? 0;
    const distance = positive(speed) && positive(motion.stop_time) ? speed * motion.stop_time : 2;
    return {
      kind: "sudden_stop",
      start,
      speed,
      stop_point: point(
        start.x + Math.cos(heading) * distance,
        start.y + Math.sin(heading) * distance,
      ),
    };
  }
  const target = motion.stop_point ?? start;
  const dx = target.x - start.x;
  const dy = target.y - start.y;
  const distance = Math.hypot(dx, dy);
  return {
    kind: "sudden_stop",
    start,
    speed,
    heading: distance > 0 ? Math.atan2(dy, dx) : 0,
    // Rounded because it is about to be shown in a box somebody may
    // type over; a duration of 4.999999999 reads as a number nobody
    // chose. Not a rule — the server decides what is legal.
    stop_time: positive(speed) && distance > 0 ? Math.round((distance / speed) * 100) / 100 : 4,
  };
}

/** The speed a motion declares, or undefined for the one that does not.
 *  `periodic` states a period instead, and derives its speed from the
 *  chord — which is why changing into it drops the number. */
function speedOf(motion: Motion): number | undefined {
  return motion.kind === "periodic" ? undefined : motion.speed;
}

/** Switch an obstacle to another motion law.
 *
 * **Built fresh rather than spread over the old one.** A `periodic`
 * carrying a leftover `waypoints` array validates — neither `Motion` nor
 * `DynamicObstacle` forbids extra keys, unlike `TaskProfile` itself — so
 * the stray field would travel to the server, be dropped in silence, and
 * reappear in the YAML tab as a block describing a motion that is not
 * happening.
 *
 * A declared speed carries across when both laws have one, because
 * "0.8 m/s, but back and forth instead" is the edit somebody is usually
 * making. Nothing else does.
 */
export function changeMotionKind(
  obstacle: DynamicObstacle,
  kind: MotionKind,
  anchor: Point2D,
): DynamicObstacle {
  if (obstacle.motion.kind === kind) return obstacle;
  const fresh = blankMotion(kind, anchor);
  const carried = speedOf(obstacle.motion);
  const motion =
    carried !== undefined && fresh.kind !== "periodic" ? { ...fresh, speed: carried } : fresh;
  // **The head start is re-derived, because it was derived.** It is
  // seconds measured against the *old* law's cycle, and cycles differ by
  // an order of magnitude between laws: a ping-ponging route of two
  // waypoints runs thirteen seconds, a fresh sudden stop four. Carrying
  // the thirteen across leaves an obstacle whose head start is three
  // times its whole trip, so most seeds begin with it already parked at
  // its stopping place — never moving, and looking like broken traffic
  // rather than declared traffic.
  return { ...obstacle, motion, seed_time_offset: defaultSeedTimeOffset(motion) ?? 10 };
}

/** Apply a click to the field the mode names.
 *
 * `sudden-stop-heading` is the one that does not store the point: that
 * motion has a start, a direction and a stopping time, and no end. The
 * second click is a way of *aiming*, so it becomes an angle and the
 * point is discarded. Storing it would invent a field the contract does
 * not have.
 */
export function placeOnMotion(motion: Motion, mode: TrafficPlacement, at: Point2D): Motion {
  switch (mode) {
    case "waypoint":
      return motion.kind === "waypoint"
        ? { ...motion, waypoints: [...motion.waypoints, at] }
        : motion;
    case "periodic-start":
      return motion.kind === "periodic" ? { ...motion, start: at } : motion;
    case "periodic-end":
      return motion.kind === "periodic" ? { ...motion, end: at } : motion;
    case "random-walk-origin":
      return motion.kind === "random_walk" ? { ...motion, origin: at } : motion;
    case "sudden-stop-start":
      return motion.kind === "sudden_stop" ? { ...motion, start: at } : motion;
    case "sudden-stop-heading":
      return motion.kind === "sudden_stop"
        ? { ...motion, heading: Math.atan2(at.y - motion.start.y, at.x - motion.start.x) }
        : motion;
    case "sudden-stop-point":
      // The one placement that *does* store the click. Under the other
      // spelling a second click only aims, because the document has no
      // field for where it lands; under this one that field is the
      // whole point.
      return motion.kind === "sudden_stop" ? { ...motion, stop_point: at } : motion;
  }
}

export function headingDegrees(radians: number): number {
  return radians * DEGREES;
}

/** What the raw text of a number input means for the document.
 *
 * **`Number("")` is 0, and that is the trap.** Clearing a box to retype
 * it wrote a zero nobody typed: a radius of 0, refused by the server for
 * being not greater than zero — a complaint about a figure the author
 * never entered, on a field that looked empty while they read it.
 *
 * An emptied box stays empty instead. `NaN` is what "there is no number
 * here" looks like on the way through: it renders as nothing, it
 * travels as JSON `null`, and the server refuses it as a missing number,
 * which is exactly what it is. Nothing is substituted on the way in —
 * what is legal is the server's to say, and a form quietly replacing a
 * blank with a plausible figure would be filing a deployment nobody
 * wrote.
 */
export function numberFromInput(raw: string): number {
  return raw.trim() === "" ? Number.NaN : Number(raw);
}

function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function segmentSum(points: Point2D[]): number {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    total += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
  }
  return total;
}

/** One full cycle of this motion in seconds, or null when it has none.
 *
 * Three answers rather than one formula, because the route a waypoint
 * obstacle actually drives depends on the two flags:
 *
 * - ping-pong retraces the line, so a cycle is the path twice;
 * - loop returns along the closing edge, so it is the path plus that edge;
 * - with neither, the obstacle drives the route once and parks. There is
 *   no cycle to derive anything from, and pretending otherwise would
 *   hand the author a number with no meaning behind it.
 *
 * Null is also what an unfinished form gets. Nothing here checks whether
 * a speed is legal — that is the server's — but arithmetic on a blank
 * field yields `Infinity` or `NaN`, and writing either into the document
 * would be this module inventing a value nobody typed.
 */
export function cycleSeconds(motion: Motion): number | null {
  if (motion.kind === "periodic") return positive(motion.period) ? motion.period : null;
  if (motion.kind === "sudden_stop") {
    // Declared by its stopping place, the duration is the trip: the
    // server works out the same number, and the suggestion beside the
    // head-start box would otherwise go blank for half the ways of
    // writing one motion.
    if (motion.stop_point) {
      const distance = Math.hypot(
        motion.stop_point.x - motion.start.x,
        motion.stop_point.y - motion.start.y,
      );
      return positive(motion.speed) && positive(distance) ? distance / motion.speed : null;
    }
    return positive(motion.stop_time) ? motion.stop_time : null;
  }
  if (motion.kind === "random_walk") return null;

  if (!positive(motion.speed)) return null;
  const points = motion.waypoints ?? [];
  if (points.length < 2) return null;
  const path = segmentSum(points);
  if (!positive(path)) return null;
  if (motion.ping_pong) return (path * 2) / motion.speed;
  if (motion.loop) {
    const first = points[0];
    const last = points[points.length - 1];
    return (path + Math.hypot(first.x - last.x, first.y - last.y)) / motion.speed;
  }
  return null;
}

/** A head start worth one full cycle, or null when there is no cycle.
 *
 * Why a whole cycle and not any positive number: a shorter shift lets
 * the seeds explore only that fraction of the route, so they can still
 * meet the obstacle at one phase — or, as the reference warehouse did,
 * at none. The server enforces this for `periodic` and leaves it to
 * judgement elsewhere; the suggestion applies the same reasoning
 * everywhere rather than only where it is compulsory.
 */
export function suggestSeedTimeOffset(motion: Motion): number | null {
  const cycle = cycleSeconds(motion);
  return cycle === null ? null : Math.round(cycle * 100) / 100;
}

/** What fraction of its trip a one-shot motion is offered as a head
 *  start. Half: enough that seeds meet it at visibly different points,
 *  little enough that none of them meet it already parked. */
const ONE_SHOT_SHARE = 0.5;

/** The head start to *start* an obstacle at.
 *
 * **Not the same number as the suggestion for a repeating motion, and
 * the difference is the whole point.** A waypoint route or a periodic
 * crossing comes back round, so a full cycle of head start spreads the
 * seeds over every phase of a motion that never ends. A `sudden_stop`
 * does end: past `stop_time` it is parked for good. Giving it a full
 * cycle therefore hands some fraction of the seeds an obstacle that has
 * already finished — it sits at its stopping place and never moves,
 * which reads as broken traffic rather than as declared traffic.
 *
 * So a one-shot motion opens at half its trip. Every seed still sees it
 * driving, and they still see it at different places, which is what the
 * head start is for.
 *
 * A default, not a rule: the shipped `sudden_stop` scenario deliberately
 * uses more than its `stop_time`, because there the cart parks in the
 * middle of the robot's lane and blocking the route is the point. The
 * author can type any of that; this only decides where they begin.
 */
export function defaultSeedTimeOffset(motion: Motion): number | null {
  const cycle = cycleSeconds(motion);
  if (cycle === null) return null;
  const share = motion.kind === "sudden_stop" ? ONE_SHOT_SHARE : 1;
  return Math.round(cycle * share * 100) / 100;
}

/** How often a seed starts with this obstacle already parked.
 *
 * **A consequence, not a rule.** The seed head start shifts an
 * obstacle's clock by a hashed amount somewhere in `[0, offset)`. A
 * sudden stop finishes moving at `stop_time`, so any shift past that
 * lands the episode after the obstacle has already braked: it is
 * sitting at its stopping place before the robot has moved, and it
 * never travels at all. That is a legitimate thing to declare — the
 * shipped `sudden_stop` scenario does it on purpose, and its cart
 * parks in the middle of the lane where it still blocks the route —
 * but it is a surprise when the parking spot is somewhere harmless,
 * because the traffic looks broken rather than declared.
 *
 * Returns the fraction of seeds affected, or null when the question
 * does not apply. Nothing here refuses anything: `TaskProfile` decides
 * what is legal, and this only says what the numbers already mean.
 */
export function parkedFromTheStart(
  motion: Motion,
  seedTimeOffset: number | undefined,
): number | null {
  if (motion.kind !== "sudden_stop") return null;
  const cycle = cycleSeconds(motion);
  if (cycle === null || !positive(seedTimeOffset)) return null;
  return seedTimeOffset > cycle ? (seedTimeOffset - cycle) / seedTimeOffset : null;
}

/** Why there is or is not a number to offer, which is three questions.
 *
 * `suggestSeedTimeOffset` answers null in three different situations and
 * the UI has to say something different about each. Collapsing them
 * produced a real falsehood: a random walk was told its offset "still
 * has to be above zero", when a random walk is the one motion the server
 * lets sit at zero — it draws its headings from the seed already, so it
 * needs no head start to vary.
 */
export type OffsetHint =
  | { kind: "suggestion"; seconds: number }
  /** `random_walk`: seeded through its headings, so zero is legal here. */
  | { kind: "self-seeded" }
  /** A route driven once and parked: no cycle to derive a number from,
   *  and the motion still ignores the seed, so it still needs one. */
  | { kind: "one-shot" }
  /** Not enough typed in yet to work anything out. */
  | { kind: "incomplete" };

export function offsetHint(motion: Motion): OffsetHint {
  if (motion.kind === "random_walk") return { kind: "self-seeded" };
  const seconds = suggestSeedTimeOffset(motion);
  if (seconds !== null) return { kind: "suggestion", seconds };
  if (
    motion.kind === "waypoint" &&
    !motion.loop &&
    !motion.ping_pong &&
    positive(motion.speed) &&
    segmentSum(motion.waypoints ?? []) > 0
  ) {
    return { kind: "one-shot" };
  }
  return { kind: "incomplete" };
}

/** The integer that decides an obstacle's seed-derived head start.
 *
 * A copy of the server's `clock_key`, and the only copied formula in
 * this file. It earns its place by what it is used for: picking a
 * default `seed_offset` for a *new* obstacle so that adding a second one
 * does not immediately produce a document the server refuses. It never
 * decides that an existing document is wrong — the refusal for a shared
 * key comes back from `EnvironmentSpec`, addressed to `environment`,
 * like every other traffic rule.
 *
 * If the server ever hashes the whole name instead, this default goes
 * stale in the harmless direction: it keeps producing distinct offsets,
 * which stay distinct under any hash.
 */
function clockKey(obstacle: DynamicObstacle): number {
  return (obstacle.seed_offset ?? 0) + obstacle.name.length;
}

/** The smallest `seed_offset` that keeps this obstacle's clock its own. */
export function nextSeedOffset(existing: DynamicObstacle[], name: string): number {
  const taken = new Set(
    existing.filter((obstacle) => (obstacle.seed_time_offset ?? 0) > 0).map(clockKey),
  );
  let offset = 0;
  while (taken.has(offset + name.length)) offset += 1;
  return offset;
}

/** A name nobody in the list is using yet. */
function nextName(existing: DynamicObstacle[]): string {
  const used = new Set(existing.map((obstacle) => obstacle.name));
  let index = existing.length + 1;
  while (used.has(`obstacle-${index}`)) index += 1;
  return `obstacle-${index}`;
}

export function addObstacle(existing: DynamicObstacle[], anchor: Point2D): DynamicObstacle[] {
  const name = nextName(existing);
  const motion = blankMotion("waypoint", anchor);
  return [
    ...existing,
    {
      name,
      radius: 0.35,
      motion,
      seed_time_offset: defaultSeedTimeOffset(motion) ?? 10,
      seed_offset: nextSeedOffset(existing, name),
    },
  ];
}

export function updateObstacle(
  existing: DynamicObstacle[],
  index: number,
  patch: Partial<DynamicObstacle>,
): DynamicObstacle[] {
  return existing.map((obstacle, at) => (at === index ? { ...obstacle, ...patch } : obstacle));
}

export function removeObstacle(existing: DynamicObstacle[], index: number): DynamicObstacle[] {
  return existing.filter((_, at) => at !== index);
}

/** Drop the last placed waypoint, for the click that landed in a wall. */
export function dropLastWaypoint(motion: Motion): Motion {
  return motion.kind === "waypoint" && motion.waypoints.length > 0
    ? { ...motion, waypoints: motion.waypoints.slice(0, -1) }
    : motion;
}

function numberAt(draft: ProfileDraft, path: string): number | undefined {
  let current: unknown = draft;
  for (const key of path.split(".")) {
    if (!current || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === "number" ? current : undefined;
}

function blockAt(draft: ProfileDraft, path: string): Record<string, unknown> | undefined {
  let current: unknown = draft;
  for (const key of path.split(".")) {
    if (!current || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current && typeof current === "object" ? (current as Record<string, unknown>) : undefined;
}

/** The simulator's cap on how coarsely the world may be stepped.
 *  Mirrors `MAX_SIMULATION_DT`; see `previewRequestOf`. */
const MAX_SIMULATION_DT = 0.05;

/** The deployment being drafted, as the scenario the preview endpoint takes.
 *
 * **Field for field with `scenario_for`** (`packages/benchmark/.../episode.py`),
 * which is what turns a profile into an episode for real. A preview
 * built from a different subset would be a second answer to "what does
 * this deployment run", and the drift would show up as a preview that
 * disagrees with the run it previews — the exact failure the endpoint
 * exists to prevent by computing positions server-side.
 *
 * Two of those fields are not copied but derived, the same way the
 * benchmark derives them:
 *
 * - `robot` is the vehicle's physics only. `control_period` is a
 *   deployment *requirement* — G4's threshold — and reaches the
 *   simulator as `simulation_dt` instead; copying it here as well would
 *   give two fields one meaning. `type` has one legal value and the
 *   scenario schema has no room for it.
 * - `name` is a fixed label rather than an episode id, because nothing
 *   is being identified: no run comes out of a preview.
 *
 * **Null when the draft has not said something the scenario needs.**
 * The first version filled those gaps with the schema's own defaults —
 * 0.05 s, 0.25 m, 120 s — which reads as harmless and is not: the
 * request then succeeds, and the author watches traffic move under a
 * timeout and a tolerance their deployment never declared. A preview
 * showing a world nobody described is the failure this whole endpoint
 * exists to avoid, arriving by a different door. So the caller gets
 * nothing to send, and the button that would have sent it is disabled.
 */
/** The longest span the preview endpoint will sample. Matches its own
 *  validation, so a deployment with a very long timeout gets a shortened
 *  preview rather than a 422. */
export const MAX_PREVIEW_SECONDS = 600;
/** How finely the route is sampled. Fine enough that a cart's turn is a
 *  curve rather than a corner; coarse enough that a ten-minute episode
 *  is three thousand points and not a hundred thousand. */
export const PREVIEW_STEP_SECONDS = 0.2;

export function previewRequestOf(options: {
  draft: ProfileDraft;
  start: Pose2D;
  goal: Pose2D;
  mapId: string;
  time: number;
  seed: number;
}): ScenarioPreviewRequest | null {
  const { draft, start, goal, mapId, time, seed } = options;
  const physics = [
    "radius",
    "max_linear_velocity",
    "max_angular_velocity",
    "max_linear_acceleration",
    "max_angular_acceleration",
  ] as const;
  const robot = {} as Record<(typeof physics)[number], number>;
  for (const name of physics) {
    const value = numberAt(draft, `robot.${name}`);
    if (value === undefined) return null;
    robot[name] = value;
  }
  const controlPeriod = numberAt(draft, "robot.control_period");
  const goalTolerance = numberAt(draft, "constraints.goal_tolerance_m");
  const timeout = numberAt(draft, "constraints.episode_timeout_s");
  // `stuck_threshold_s` is required by the contract and has a default in
  // `Scenario`, which is the combination that hides a substitution: the
  // preview would run under the simulator's five seconds while the
  // deployment is going to declare ten, and an episode that gives up
  // early looks like traffic the robot could not get past.
  const stuck = numberAt(draft, "constraints.stuck_threshold_s");
  if (
    controlPeriod === undefined ||
    goalTolerance === undefined ||
    timeout === undefined ||
    stuck === undefined
  ) {
    return null;
  }
  const scenario: Scenario = {
    name: "deployment-preview",
    description: "",
    robot,
    start_pose: start,
    goal_pose: goal,
    goal_tolerance: goalTolerance,
    timeout_seconds: timeout,
    simulation_dt: Math.min(MAX_SIMULATION_DT, controlPeriod),
    dynamic_obstacles: trafficOf(draft),
    stuck_time_window: stuck,
    random_seed: seed,
  };
  // These two really are optional on a deployment: the server defaults
  // them, and a profile that declares neither is a legal profile rather
  // than an unfinished one.
  const noise = blockAt(draft, "environment.sensor_noise");
  if (noise) scenario.sensor_noise = noise as Scenario["sensor_noise"];
  const clearance = numberAt(draft, "clearance_preference");
  if (clearance !== undefined) scenario.clearance_preference = clearance;
  /* **The playable span is the deployment's own episode timeout.**
     Not a constant: a preview that runs for sixty seconds against a
     deployment that gives up at twenty shows an author traffic their
     episode will never meet, and one that stops at sixty against a
     three-minute timeout hides the part they were worried about. The
     number is already required above — `timeout` — because a scenario
     cannot be built without it, so this costs nothing and cannot drift
     from what the run will do.

     Clamped to the endpoint's own ceiling, so a deployment declaring a
     very long episode gets a preview rather than a refusal. */
  const duration = Math.min(timeout, MAX_PREVIEW_SECONDS);
  return { map_id: mapId, scenario, time, seed, duration, step: PREVIEW_STEP_SECONDS };
}

/** The raised view takes snapshots where the flat one takes markers.
 *  Both are fed from this one preview, because two views showing
 *  different worlds would be worse than one view — which is also why
 *  `seconds` is threaded through here rather than left at the instant
 *  the request named: with playback running, a 2.5D view frozen at t=0
 *  beside a top-down view at t=12 is precisely those two worlds. */
export function snapshotsOf(
  preview: PlayableTraffic | null,
  seconds = 0,
): ObstacleSnapshot[] {
  return trafficAt(preview, seconds).map((obstacle) => ({
    name: obstacle.name,
    x: obstacle.position.x,
    y: obstacle.position.y,
    radius: obstacle.radius,
  }));
}
