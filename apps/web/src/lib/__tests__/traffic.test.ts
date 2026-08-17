/** Authoring traffic, as data.
 *
 * The web suite runs on Node with no DOM, so a click cannot be tested
 * here and a reducer can. That constraint pushed the work into
 * `lib/traffic` in the first place, and this file is the return on it:
 * every rule about *shapes and defaults* is checked directly, and the
 * component is left with wiring.
 *
 * What is deliberately absent: any test asserting that a document is
 * legal or illegal. Nothing in `lib/traffic` decides that — the verdict
 * comes from `POST /task-profiles/validate`, and `tests/api/
 * test_api_profile_validation.py` is where it is pinned.
 */

import { describe, expect, it } from "vitest";

import type { ProfileDraft } from "@/lib/deployments";

import {
  addObstacle,
  blankMotion,
  changeMotionKind,
  cycleSeconds,
  defaultSeedTimeOffset,
  dropLastWaypoint,
  nextSeedOffset,
  numberFromInput,
  offsetHint,
  parkedFromTheStart,
  placeOnMotion,
  placementsFor,
  previewRequestOf,
  removeObstacle,
  snapshotsOf,
  stopMode,
  suggestSeedTimeOffset,
  trafficOf,
  updateObstacle,
  withStopMode,
} from "@/lib/traffic";
import type {
  DynamicObstacle,
  Motion,
  PeriodicMotion,
  SuddenStopMotion,
  WaypointMotion,
} from "@/lib/types";

const ORIGIN = { x: 0, y: 0 };

function crosser(overrides: Partial<DynamicObstacle> = {}): DynamicObstacle {
  return {
    name: "cart",
    radius: 0.4,
    seed_time_offset: 20,
    seed_offset: 0,
    motion: {
      kind: "waypoint",
      waypoints: [
        { x: 0, y: 0 },
        { x: 10, y: 0 },
      ],
      speed: 1,
      loop: false,
      ping_pong: true,
    },
    ...overrides,
  };
}

describe("reading traffic off a draft", () => {
  it("finds the list a profile carries", () => {
    const draft = { environment: { dynamic_obstacles: [crosser()] } };
    expect(trafficOf(draft)).toHaveLength(1);
  });

  it("answers empty for every shape that is not a list", () => {
    // The draft is `Record<string, unknown>` on purpose, so this is the
    // one place that has to cope with a document mid-edit.
    expect(trafficOf(null)).toEqual([]);
    expect(trafficOf({})).toEqual([]);
    expect(trafficOf({ environment: null })).toEqual([]);
    expect(trafficOf({ environment: {} })).toEqual([]);
    expect(trafficOf({ environment: { dynamic_obstacles: "cart" } })).toEqual([]);
  });
});

describe("changing the motion law", () => {
  it("drops every field of the law being left behind", () => {
    /* A `periodic` carrying a leftover `waypoints` validates — neither
       Motion nor DynamicObstacle forbids extra keys — so the stray field
       would reach the server, be dropped in silence, and reappear in the
       YAML tab describing a motion that is not happening. */
    const next = changeMotionKind(crosser(), "periodic", ORIGIN);
    expect(next.motion.kind).toBe("periodic");
    expect(Object.keys(next.motion).sort()).toEqual(["end", "kind", "period", "phase", "start"]);
  });

  it("carries a declared speed across laws that both have one", () => {
    const fast = crosser({ motion: { ...blankMotion("waypoint", ORIGIN), speed: 0.9 } as Motion });
    const walking = changeMotionKind(fast, "random_walk", ORIGIN);
    expect(walking.motion.kind === "random_walk" && walking.motion.speed).toBe(0.9);
  });

  it("does not invent a speed for the law that states a period instead", () => {
    const patrol = changeMotionKind(crosser(), "periodic", ORIGIN);
    expect(patrol.motion).not.toHaveProperty("speed");
  });

  it("is a no-op when the law is already the one asked for", () => {
    const before = crosser();
    expect(changeMotionKind(before, "waypoint", ORIGIN)).toBe(before);
  });

  it("keeps what the obstacle is, whatever law it follows", () => {
    const next = changeMotionKind(crosser({ name: "rack", radius: 0.6 }), "sudden_stop", ORIGIN);
    expect(next.name).toBe("rack");
    expect(next.radius).toBe(0.6);
  });

  it("re-derives the head start, because it was derived", () => {
    /* It used to carry across, and that was a trap rather than a
       courtesy: the number is seconds measured against the *old* law's
       cycle, and cycles differ by an order of magnitude between laws. A
       ping-ponging pair of waypoints runs thirteen seconds; a fresh
       sudden stop, four. Carrying the thirteen over left an obstacle
       whose head start was three times its whole trip, so most seeds
       began with it already parked at its stopping place — never
       moving, and looking like broken traffic rather than declared
       traffic. */
    const next = changeMotionKind(crosser({ seed_time_offset: 20 }), "sudden_stop", ORIGIN);
    expect(next.seed_time_offset).toBe(defaultSeedTimeOffset(next.motion));
    expect(next.seed_time_offset).toBeLessThan(cycleSeconds(next.motion)!);
  });

  it("still offers a full cycle to a law that repeats", () => {
    /* The halving is only for a motion that ends. A route that comes
       back round has no "after" to land in, so a full cycle is what
       spreads the seeds over all of it. */
    const next = changeMotionKind(
      crosser({ seed_time_offset: 1 }),
      "periodic",
      ORIGIN,
    );
    expect(next.seed_time_offset).toBe(cycleSeconds(next.motion));
  });
});

describe("placing a point on the map", () => {
  it("appends waypoints in the order they were clicked", () => {
    const motion = placeOnMotion(
      placeOnMotion(blankMotion("waypoint", ORIGIN), "waypoint", { x: 1, y: 1 }),
      "waypoint",
      { x: 2, y: 2 },
    ) as WaypointMotion;
    expect(motion.waypoints.slice(-2)).toEqual([
      { x: 1, y: 1 },
      { x: 2, y: 2 },
    ]);
  });

  it("undoes the click that landed in a wall", () => {
    const motion = placeOnMotion(blankMotion("waypoint", ORIGIN), "waypoint", { x: 9, y: 9 });
    expect((dropLastWaypoint(motion) as WaypointMotion).waypoints).toHaveLength(2);
  });

  it("moves the two ends of a patrol independently", () => {
    let motion = blankMotion("periodic", ORIGIN);
    motion = placeOnMotion(motion, "periodic-start", { x: 3, y: 4 });
    motion = placeOnMotion(motion, "periodic-end", { x: 8, y: 4 });
    expect(motion.kind === "periodic" && motion.start).toEqual({ x: 3, y: 4 });
    expect(motion.kind === "periodic" && motion.end).toEqual({ x: 8, y: 4 });
  });

  it("turns the second click on a sudden stop into an angle and keeps no point", () => {
    /* That motion has a start, a direction and a stopping time, and no
       end. Storing the clicked point would invent a field the contract
       does not have. */
    const aimed = placeOnMotion(
      placeOnMotion(blankMotion("sudden_stop", ORIGIN), "sudden-stop-start", { x: 2, y: 2 }),
      "sudden-stop-heading",
      { x: 2, y: 5 },
    );
    expect(aimed.kind === "sudden_stop" && aimed.heading).toBeCloseTo(Math.PI / 2, 10);
    expect(Object.keys(aimed).sort()).toEqual(["heading", "kind", "speed", "start", "stop_time"]);
  });

  it("leaves a motion alone when the mode belongs to another law", () => {
    const motion = blankMotion("random_walk", ORIGIN);
    expect(placeOnMotion(motion, "periodic-end", { x: 1, y: 1 })).toBe(motion);
  });
});

describe("the two ways a sudden stop says where it ends", () => {
  const byAngle: Motion = {
    kind: "sudden_stop",
    start: { x: 0, y: 0 },
    heading: 0,
    speed: 2,
    stop_time: 3,
  };

  it("reads the mode off which description is present", () => {
    expect(stopMode(byAngle)).toBe("time");
    expect(stopMode({ ...byAngle, stop_point: { x: 6, y: 0 } })).toBe("point");
  });

  it("offers the button that belongs to the mode, and only that one", () => {
    /* A toolbar showing both would offer a way to write the document
       the server refuses. */
    expect(placementsFor(byAngle)).toEqual(["sudden-stop-start", "sudden-stop-heading"]);
    expect(placementsFor({ ...byAngle, stop_point: { x: 6, y: 0 } })).toEqual([
      "sudden-stop-start",
      "sudden-stop-point",
    ]);
  });

  it("switching to a point keeps the obstacle where it already stopped", () => {
    /* 2 m/s for 3 s along heading 0 is six metres east. Landing the new
       point anywhere else would make the picture jump for a change that
       described the same motion. */
    const switched = withStopMode(byAngle, "point");
    expect(switched.kind === "sudden_stop" && switched.stop_point).toEqual({ x: 6, y: 0 });
  });

  it("switching back reads the heading and the duration off the point", () => {
    const byPoint: Motion = {
      kind: "sudden_stop",
      start: { x: 1, y: 1 },
      speed: 2,
      stop_point: { x: 1, y: 5 },
    };
    const switched = withStopMode(byPoint, "time");
    expect(switched.kind === "sudden_stop" && switched.heading).toBeCloseTo(Math.PI / 2);
    expect(switched.kind === "sudden_stop" && switched.stop_time).toBe(2);
  });

  it("drops the fields of the description it left", () => {
    /* The server takes exactly one. Leaving the other behind would send
       a document it refuses — and a stale heading beside a stop point
       would be a second opinion about which way the obstacle goes. */
    const toPoint = withStopMode(byAngle, "point");
    expect(Object.keys(toPoint).sort()).toEqual(["kind", "speed", "start", "stop_point"]);
    const andBack = withStopMode(toPoint, "time");
    expect(Object.keys(andBack).sort()).toEqual([
      "heading",
      "kind",
      "speed",
      "start",
      "stop_time",
    ]);
  });

  it("changes nothing when asked for the mode it is already in", () => {
    expect(withStopMode(byAngle, "time")).toBe(byAngle);
  });

  it("survives a half-typed speed rather than writing Infinity", () => {
    const switched = withStopMode({ ...byAngle, speed: Number.NaN }, "point");
    const point = switched.kind === "sudden_stop" ? switched.stop_point : undefined;
    expect(Number.isFinite(point?.x)).toBe(true);
    expect(Number.isFinite(point?.y)).toBe(true);
  });

  it("places the stopping point from a click, storing it", () => {
    /* The one placement that keeps the point. Under the other spelling
       a second click only aims, because the document has no field for
       where it lands. */
    const placed = placeOnMotion({ ...byAngle, stop_point: { x: 6, y: 0 } }, "sudden-stop-point", {
      x: 2,
      y: 9,
    });
    expect(placed.kind === "sudden_stop" && placed.stop_point).toEqual({ x: 2, y: 9 });
  });

  it("works out how often a seed starts with it already parked", () => {
    /* The head start shifts the clock somewhere in [0, offset). Past
       `stop_time` the episode begins after the obstacle has braked: it
       sits at its stopping place and never travels. A consequence of
       two numbers, not a rule — the shipped `sudden_stop` scenario
       declares exactly this on purpose. */
    // 3 s trip, 6 s of head start: half the shifts land after it.
    expect(parkedFromTheStart(byAngle, 6)).toBeCloseTo(0.5);
    expect(parkedFromTheStart(byAngle, 4)).toBeCloseTo(0.25);
  });

  it("says nothing when every seed sees it driving", () => {
    expect(parkedFromTheStart(byAngle, 3)).toBeNull();
    expect(parkedFromTheStart(byAngle, 1)).toBeNull();
  });

  it("asks the question only of the motion it applies to", () => {
    /* A waypoint route that loops has no "after" to land in, and a
       random walk never stops at all. */
    expect(parkedFromTheStart(blankMotion("waypoint", ORIGIN), 99)).toBeNull();
    expect(parkedFromTheStart(blankMotion("random_walk", ORIGIN), 99)).toBeNull();
  });

  it("stays quiet on a half-typed obstacle rather than dividing by nothing", () => {
    expect(parkedFromTheStart(byAngle, undefined)).toBeNull();
    expect(parkedFromTheStart(byAngle, Number.NaN)).toBeNull();
    expect(parkedFromTheStart({ ...byAngle, stop_time: Number.NaN }, 6)).toBeNull();
  });

  it("measures the trip from the stopping point when that is the spelling", () => {
    const byPoint: Motion = {
      kind: "sudden_stop",
      start: { x: 0, y: 0 },
      speed: 2,
      stop_point: { x: 0, y: 4 },
    };
    // 4 m at 2 m/s is a 2 s trip; a 4 s head start parks half the seeds.
    expect(parkedFromTheStart(byPoint, 4)).toBeCloseTo(0.5);
  });

  it("derives the cycle from the trip when the stop is a place", () => {
    /* Otherwise the head-start suggestion would go blank for half the
       ways of writing one motion. */
    expect(
      cycleSeconds({
        kind: "sudden_stop",
        start: { x: 0, y: 0 },
        speed: 2,
        stop_point: { x: 0, y: 5 },
      }),
    ).toBe(2.5);
  });
});

describe("suggesting a seed head start", () => {
  const path = (overrides: Partial<WaypointMotion>): Motion => ({
    ...(blankMotion("waypoint", ORIGIN) as WaypointMotion),
    waypoints: [
      { x: 0, y: 0 },
      { x: 18, y: 0 },
    ],
    speed: 0.8,
    loop: false,
    ping_pong: false,
    ...overrides,
  });

  it("is the route twice over when the obstacle retraces it", () => {
    // The shipped crossing deployment's own number: 2 x 18 m at 0.8 m/s.
    expect(suggestSeedTimeOffset(path({ ping_pong: true }))).toBe(45);
  });

  it("adds the closing edge when the obstacle loops", () => {
    const triangle = path({
      loop: true,
      speed: 1,
      waypoints: [
        { x: 0, y: 0 },
        { x: 3, y: 0 },
        { x: 3, y: 4 },
      ],
    });
    // 3 + 4 along the route, 5 back to the start.
    expect(suggestSeedTimeOffset(triangle)).toBe(12);
  });

  it("has nothing to suggest for a route driven once", () => {
    /* It parks at the far end, so there is no cycle to derive a number
       from. A suggestion here would be arithmetic with nothing behind
       it — the author still has to choose, and the server still refuses
       zero. */
    expect(suggestSeedTimeOffset(path({}))).toBeNull();
  });

  it("is one period for a patrol and the stopping time for a sudden stop", () => {
    const patrol: Motion = { ...(blankMotion("periodic", ORIGIN) as PeriodicMotion), period: 24 };
    const stop: Motion = {
      ...(blankMotion("sudden_stop", ORIGIN) as SuddenStopMotion),
      stop_time: 3.5,
    };
    expect(suggestSeedTimeOffset(patrol)).toBe(24);
    expect(suggestSeedTimeOffset(stop)).toBe(3.5);
  });

  it("has nothing to suggest for a random walk, which reads the seed itself", () => {
    expect(suggestSeedTimeOffset(blankMotion("random_walk", ORIGIN))).toBeNull();
  });

  describe("never producing a number out of a half-typed field", () => {
    /* This module writes into the document. Nothing here judges whether
       a speed is legal — that is the server's — but arithmetic on a
       blank field yields Infinity or NaN, and either one written into a
       profile is this code inventing a value nobody typed. */
    const cases: [string, Partial<WaypointMotion>][] = [
      ["speed zero", { ping_pong: true, speed: 0 }],
      ["speed missing", { ping_pong: true, speed: undefined as unknown as number }],
      ["speed not a number", { ping_pong: true, speed: "0.8" as unknown as number }],
      ["speed infinite", { ping_pong: true, speed: Number.POSITIVE_INFINITY }],
      ["speed NaN", { ping_pong: true, speed: Number.NaN }],
      ["one waypoint", { ping_pong: true, waypoints: [{ x: 0, y: 0 }] }],
      [
        "two waypoints in the same place",
        {
          ping_pong: true,
          waypoints: [
            { x: 1, y: 1 },
            { x: 1, y: 1 },
          ],
        },
      ],
    ];

    it.each(cases)("%s", (_label, overrides) => {
      expect(suggestSeedTimeOffset(path(overrides))).toBeNull();
    });

    it("also for a period or a stopping time that is not there yet", () => {
      const patrol: Motion = { ...(blankMotion("periodic", ORIGIN) as PeriodicMotion), period: 0 };
      const stop: Motion = {
        ...(blankMotion("sudden_stop", ORIGIN) as SuddenStopMotion),
        stop_time: Number.NaN,
      };
      expect(suggestSeedTimeOffset(patrol)).toBeNull();
      expect(suggestSeedTimeOffset(stop)).toBeNull();
      expect(cycleSeconds(stop)).toBeNull();
    });
  });
});

describe("why there is no number to suggest", () => {
  /** Three different situations answered `null`, and the UI said the
   *  same wrong thing about all three.
   *
   * The one that mattered: a random walk was told its head start "still
   * has to be above zero". It does not — that is the single motion the
   * server lets sit at zero, because it draws its headings from the seed
   * and already differs run to run. The form was contradicting the
   * contract it exists to serve.
   */
  const route = (overrides: Partial<WaypointMotion>): Motion => ({
    ...(blankMotion("waypoint", ORIGIN) as WaypointMotion),
    waypoints: [
      { x: 0, y: 0 },
      { x: 6, y: 0 },
    ],
    speed: 1,
    loop: false,
    ping_pong: false,
    ...overrides,
  });

  it("has a number when the route comes back round", () => {
    expect(offsetHint(route({ ping_pong: true }))).toEqual({ kind: "suggestion", seconds: 12 });
  });

  it("says a random walk needs none", () => {
    expect(offsetHint(blankMotion("random_walk", ORIGIN))).toEqual({ kind: "self-seeded" });
  });

  it("says a route driven once still needs one, chosen by hand", () => {
    expect(offsetHint(route({}))).toEqual({ kind: "one-shot" });
  });

  it("asks for the missing fields rather than claiming either", () => {
    expect(offsetHint(route({ speed: Number.NaN }))).toEqual({ kind: "incomplete" });
    expect(offsetHint(route({ waypoints: [{ x: 0, y: 0 }] }))).toEqual({ kind: "incomplete" });
  });

  it("keeps a suggestion for the two laws that have one", () => {
    const patrol: Motion = { ...(blankMotion("periodic", ORIGIN) as PeriodicMotion), period: 9 };
    const stop: Motion = {
      ...(blankMotion("sudden_stop", ORIGIN) as SuddenStopMotion),
      stop_time: 2,
    };
    expect(offsetHint(patrol)).toEqual({ kind: "suggestion", seconds: 9 });
    expect(offsetHint(stop)).toEqual({ kind: "suggestion", seconds: 2 });
  });
});

describe("reading a number out of an input", () => {
  /** The zero nobody typed.
   *
   * `Number("")` is 0, so clearing a box to retype it wrote a radius of
   * zero into the document — refused by the server for not being greater
   * than zero, which reads as a complaint about a figure the author
   * never entered, on a field that looked empty while they read it.
   */
  it("keeps an emptied box empty rather than calling it zero", () => {
    expect(numberFromInput("")).toBeNaN();
    expect(numberFromInput("   ")).toBeNaN();
  });

  it("passes a real number through untouched", () => {
    expect(numberFromInput("0.8")).toBe(0.8);
    expect(numberFromInput("-1.5")).toBe(-1.5);
  });

  it("does not correct a value it dislikes", () => {
    /* Zero is a number somebody can mean, and whether it is legal here
       is the server's to say. A form that substituted something more
       plausible would be filing a deployment nobody wrote. */
    expect(numberFromInput("0")).toBe(0);
  });
});

describe("adding an obstacle", () => {
  it("opens on a route that already has a cycle, so the head start has a number", () => {
    const [added] = addObstacle([], ORIGIN);
    expect(added.motion.kind).toBe("waypoint");
    expect(added.seed_time_offset).toBe(suggestSeedTimeOffset(added.motion));
    expect(added.seed_time_offset).toBeGreaterThan(0);
  });

  it("gives the second obstacle a clock of its own", () => {
    /* Two obstacles whose `seed_offset + name.length` coincide take the
       same head start at every seed and move as one object — the trap
       unique names do not catch, and the server refuses it. Walking the
       author into that refusal on the click that created it would be a
       poor first draft, not neutrality. */
    const list = addObstacle(addObstacle([], ORIGIN), ORIGIN);
    const keys = list.map((o) => (o.seed_offset ?? 0) + o.name.length);
    expect(new Set(keys).size).toBe(list.length);
  });

  it("counts only the obstacles that actually take a head start", () => {
    // At offset zero the shift is zero for everyone, so a shared key
    // means nothing there.
    const parked = crosser({ name: "cart", seed_offset: 0, seed_time_offset: 0 });
    expect(nextSeedOffset([parked], "rack")).toBe(0);
  });

  it("steps past a key that is taken", () => {
    expect(nextSeedOffset([crosser({ name: "cart", seed_offset: 0 })], "rack")).toBe(1);
  });

  it("names each one distinctly", () => {
    const list = addObstacle(addObstacle(addObstacle([], ORIGIN), ORIGIN), ORIGIN);
    expect(new Set(list.map((o) => o.name)).size).toBe(3);
  });
});

describe("editing the list", () => {
  it("changes one row and leaves the rest identical", () => {
    const before = [crosser({ name: "a" }), crosser({ name: "b" })];
    const after = updateObstacle(before, 1, { radius: 0.9 });
    expect(after[0]).toBe(before[0]);
    expect(after[1].radius).toBe(0.9);
    expect(after[1].name).toBe("b");
  });

  it("removes by position, not by name", () => {
    const before = [crosser({ name: "a" }), crosser({ name: "b" }), crosser({ name: "c" })];
    expect(removeObstacle(before, 1).map((o) => o.name)).toEqual(["a", "c"]);
  });
});

describe("the preview request", () => {
  const draft = {
    robot: {
      type: "differential_drive",
      radius: 0.26,
      max_linear_velocity: 0.8,
      max_angular_velocity: 1.2,
      max_linear_acceleration: 0.5,
      max_angular_acceleration: 1,
      control_period: 0.02,
    },
    clearance_preference: 4,
    constraints: { goal_tolerance_m: 0.2, episode_timeout_s: 180, stuck_threshold_s: 10 },
    environment: {
      sensor_noise: { lidar_range_sigma_m: 0.02, wheel_slip_fraction: 0.02 },
      dynamic_obstacles: [crosser()],
    },
  };
  const options = {
    draft: draft as ProfileDraft,
    start: { x: 2, y: 3, theta: 0 },
    goal: { x: 38, y: 21, theta: 1.57 },
    mapId: "map-1",
    time: 4,
    seed: 7,
  };
  const built = () => {
    const request = previewRequestOf(options);
    if (!request) throw new Error("the complete draft should produce a request");
    return request;
  };

  it("carries the time and the seed the endpoint asks for", () => {
    const request = built();
    expect(request.time).toBe(4);
    expect(request.seed).toBe(7);
    expect(request.scenario.random_seed).toBe(7);
  });

  it("names the scenario, because the schema requires one", () => {
    expect(built().scenario.name).toBeTruthy();
  });

  it("hands over the vehicle's physics and nothing else", () => {
    /* `control_period` is a deployment requirement — G4's threshold —
       and reaches the simulator as `simulation_dt`. Copying it here as
       well would give two fields one meaning, which is the boundary
       `_robot_config` exists to hold. */
    expect(Object.keys(built().scenario.robot).sort()).toEqual([
      "max_angular_acceleration",
      "max_angular_velocity",
      "max_linear_acceleration",
      "max_linear_velocity",
      "radius",
    ]);
  });

  it("steps the world no more coarsely than the controller acts", () => {
    expect(built().scenario.simulation_dt).toBe(0.02);
  });

  it("never steps it more coarsely than the benchmark would", () => {
    const slow = { ...draft, robot: { ...draft.robot, control_period: 0.5 } };
    expect(previewRequestOf({ ...options, draft: slow })?.scenario.simulation_dt).toBe(0.05);
  });

  it("carries every field `scenario_for` fills, so the preview is the deployment", () => {
    /* The drift this guards: a preview built from a smaller subset would
       be a second answer to what this deployment runs, and it would show
       up as traffic in the wrong place at the same instant. */
    const scenario = built().scenario;
    for (const field of [
      "name",
      "robot",
      "start_pose",
      "goal_pose",
      "goal_tolerance",
      "timeout_seconds",
      "simulation_dt",
      "dynamic_obstacles",
      "sensor_noise",
      "clearance_preference",
      "random_seed",
      "stuck_time_window",
    ]) {
      expect(scenario, `missing ${field}`).toHaveProperty(field);
    }
  });

  it("omits the optional blocks the draft has not said", () => {
    /* Absent is the honest answer for these three: the server has a
       default for each, and sending one the deployment never declared
       would be inventing a world. */
    const bare = previewRequestOf({
      ...options,
      draft: { robot: draft.robot, constraints: draft.constraints },
    });
    expect(bare?.scenario).not.toHaveProperty("sensor_noise");
    expect(bare?.scenario).not.toHaveProperty("clearance_preference");
    expect(bare?.scenario.dynamic_obstacles).toEqual([]);
  });

  describe("refusing to build a request the draft cannot support", () => {
    /* The first version filled these three with the schema's own
       defaults — 0.05 s, 0.25 m, 120 s. That reads as harmless and is
       not: the request succeeds, and the author watches traffic move
       under a timeout and a tolerance their deployment never declared.
       A preview showing a world nobody described is the failure this
       endpoint exists to prevent, arriving by another door. */
    const without = (path: string): ProfileDraft => {
      const [head, tail] = path.split(".");
      const block = { ...(draft[head as keyof typeof draft] as Record<string, unknown>) };
      delete block[tail];
      return { ...draft, [head]: block };
    };

    it.each([
      ["robot.control_period"],
      ["robot.radius"],
      ["robot.max_linear_velocity"],
      ["constraints.goal_tolerance_m"],
      ["constraints.episode_timeout_s"],
      /* The one that hid the longest, because `Scenario` defaults it:
         the preview would have run under the simulator's five seconds
         while the deployment declares ten, and an episode giving up
         early reads as traffic the robot could not get past. */
      ["constraints.stuck_threshold_s"],
    ])("returns nothing to send when %s is missing", (path) => {
      expect(previewRequestOf({ ...options, draft: without(path) })).toBeNull();
    });

    it("carries the declared stuck threshold rather than the simulator's", () => {
      expect(built().scenario.stuck_time_window).toBe(10);
    });

    it("returns nothing when there is no draft at all", () => {
      expect(previewRequestOf({ ...options, draft: {} })).toBeNull();
    });
  });
});

describe("the raised view", () => {
  it("takes snapshots where the flat one takes markers", () => {
    const snapshots = snapshotsOf({
      time: 3,
      seed: 0,
      valid: true,
      errors: [],
      dynamic_obstacles: [{ name: "cart", radius: 0.4, position: { x: 5, y: 6 } }],
    });
    expect(snapshots).toEqual([{ name: "cart", x: 5, y: 6, radius: 0.4 }]);
  });

  it("draws nothing rather than an empty aisle when there is no preview yet", () => {
    expect(snapshotsOf(null)).toEqual([]);
  });
});
