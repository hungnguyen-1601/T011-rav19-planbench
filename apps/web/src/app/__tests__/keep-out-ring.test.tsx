/** B4 — the planner's keep-out is drawn, faintly, under the obstacle.
 *
 * **What was invisible.** The canvas drew a cart at its own radius —
 * 0.40 m on `sudden_stop` — while the planner refused to route within
 * `robot.radius + √2 × resolution` of it, another 0.61 m. The ring is
 * two and a half times the circle, and nothing on screen said so: a
 * robot parked half a metre clear of the cart looked like it was
 * standing in open space, and the reason it could not replan from there
 * was not drawn anywhere.
 *
 * That took a full session to work out from first principles. Drawing it
 * is what makes the next instance of this class of problem readable
 * rather than mysterious.
 *
 * **Faint on purpose.** The ring is context; the obstacle is the
 * subject. A 1.0 m disc painted at full strength over a 0.4 m cart puts
 * the eye on the wrong thing, so it is drawn *under* the obstacle, at a
 * low alpha, dashed rather than solid — a solid ring reads as a wall,
 * which is the one thing it is not. The controller drives through it
 * every time it squeezes past something; only the planner refuses to
 * route through it.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  KEEP_OUT_FILL,
  KEEP_OUT_STROKE,
  MIN_JUMP_MAGNITUDE_M,
  inflationRadius,
  keepOutRadius,
  safetyEnvelope,
} from "../../lib/keepOut";

const SRC = join(process.cwd(), "src");
const CANVAS = readFileSync(join(SRC, "components", "MapCanvas.tsx"), "utf8");
const SCENE = readFileSync(join(SRC, "components", "Scene25D.tsx"), "utf8");
const SCENE_LIB = readFileSync(join(SRC, "lib", "scene25d.ts"), "utf8");
const NAV_STACK = readFileSync(
  join(process.cwd(), "..", "..", "services", "simulator", "planbench_simulator", "nav_stack.py"),
  "utf8",
);
const FEASIBILITY = readFileSync(
  join(process.cwd(), "..", "..", "packages", "schemas", "planbench_schemas", "feasibility.py"),
  "utf8",
);
const SENSOR = readFileSync(
  join(process.cwd(), "..", "..", "packages", "schemas", "planbench_schemas", "sensor.py"),
  "utf8",
);

describe("the number matches the one the planner actually uses", () => {
  it("is robot radius, plus the safety envelope, plus the cell half-diagonal", () => {
    /* The three parts are different kinds of quantity, and that is why
       the ring surprises people: `robot.radius` is geometry, the safety
       envelope is how wrong the robot's idea of its position may be, and
       `√2 × resolution` is a property of the *map's resolution* — halve
       the cell size and the ring shrinks with nothing about the world
       having changed. */
    expect(inflationRadius(0.25, 0.26)).toBeCloseTo(0.26 + Math.SQRT2 * 0.25, 9);
    expect(inflationRadius(0.25, 0.26, 0.391)).toBeCloseTo(0.26 + 0.391 + Math.SQRT2 * 0.25, 9);
    expect(keepOutRadius(0.4, 0.25, 0.26)).toBeCloseTo(0.4 + 0.26 + Math.SQRT2 * 0.25, 9);
  });

  it("derives the envelope from the declared noise, worst case", () => {
    /* Worst case rather than a percentile: a hard bound exceeded five
       per cent of the time is not hard, and a percentile would need
       somebody to choose which one. */
    expect(safetyEnvelope(undefined)).toBe(0);
    expect(safetyEnvelope({ lidar_range_sigma_m: 0.02, wheel_slip_fraction: 0.02 })).toBe(0);
    expect(safetyEnvelope({ localization_drift_m: 0.1 })).toBeCloseTo(0.1 * Math.SQRT2, 9);
    /* A jump that *may* happen is counted as one that does: over an
       episode of many relocalisation windows, "unlikely per window" is
       "it happens". This is the 0.25 m that makes the form's ring so
       much larger than the shipped profile's. */
    expect(
      safetyEnvelope({ localization_drift_m: 0.1, localization_jump_probability: 0.02 }),
    ).toBeCloseTo(0.1 * Math.SQRT2 + 0.25, 9);
  });

  it("agrees with the simulator's definition, read from the source", () => {
    /* This is a copy of two Python definitions and there is no way
       around that, so the copies are pinned rather than trusted. Two
       hand-typed copies of an inflation radius drifting apart is exactly
       how the controller's keep-out and the planner's came to differ by
       0.30 m in the first place. */
    expect(NAV_STACK).toContain("def _inflation_radius(");
    expect(NAV_STACK).toContain(
      "hard_clearance(scenario.robot, envelope) + math.sqrt(2.0) * map_data.resolution",
    );
    expect(NAV_STACK.match(/math\.sqrt\(2\.0\) \* map_data\.resolution/g) ?? []).toHaveLength(1);

    /* And the envelope half, which is the part that changed the ring. */
    expect(FEASIBILITY).toContain("bound = drift * math.sqrt(2.0)");
    expect(FEASIBILITY).toContain("bound += max(drift, MIN_JUMP_MAGNITUDE_M)");
    expect(FEASIBILITY).toContain("return robot.radius + envelope.position_uncertainty_m");
    expect(SENSOR).toContain(`MIN_JUMP_MAGNITUDE_M = ${MIN_JUMP_MAGNITUDE_M}`);
  });

  it("reaches both views of the same map", () => {
    /* The ring is the same number in flat and raised, so a value that
       reached one and not the other would draw two answers to one
       question — the exact failure this ring exists to make visible. */
    const view = readFileSync(join(SRC, "components", "MapView.tsx"), "utf8");
    expect(view).toContain("positionUncertainty={canvas.positionUncertainty}");
    expect(SCENE_LIB).toContain("options.positionUncertainty");
  });

  it("draws nothing rather than guessing when an input is missing", () => {
    /* A ring computed from an assumed robot radius would be a picture of
       a keep-out nobody has — worse than no ring, because it looks
       authoritative. */
    expect(keepOutRadius(0.4, undefined, 0.26)).toBeNull();
    expect(keepOutRadius(0.4, 0.25, undefined)).toBeNull();
    expect(keepOutRadius(0.4, 0, 0.26)).toBeNull();
  });
});

describe("it is faint, and it sits under the obstacle", () => {
  it("uses a low-alpha fill and a lighter outline", () => {
    const alphaOf = (colour: string) => Number(colour.match(/,\s*([\d.]+)\)$/)?.[1]);
    expect(alphaOf(KEEP_OUT_FILL)).toBeLessThan(0.15);
    expect(alphaOf(KEEP_OUT_STROKE)).toBeLessThan(0.5);
    /* Same hue as the obstacle it belongs to: a different colour would
       read as a second thing in the scene rather than as that cart's
       margin. */
    expect(KEEP_OUT_FILL).toContain("240, 180, 41");
    expect(KEEP_OUT_STROKE).toContain("240, 180, 41");
  });

  it("is dashed, because a solid ring reads as a wall", () => {
    expect(CANVAS).toContain("ctx.setLineDash([4, 4])");
    expect(SCENE).toContain("ctx.setLineDash([4, 4])");
    /* And the dash is cleared again — leaving it set would dash whatever
       the next drawing call happens to be. */
    expect(CANVAS).toContain("ctx.setLineDash([])");
    expect(SCENE).toContain("ctx.setLineDash([])");
  });

  it("is painted before the obstacles in the flat view", () => {
    /* Order is the whole of "does not swamp the real shape": the
       obstacle has to land on top of its own ring. */
    expect(CANVAS.indexOf("const drawRing")).toBeLessThan(
      CANVAS.indexOf("ctx.fillStyle = COLOR.staticObstacle"),
    );
    expect(CANVAS.indexOf("drawRing(obstacle.position.x")).toBeLessThan(
      CANVAS.indexOf("if (dynamicObstacles) {"),
    );
  });

  it("is painted before the obstacles in the raised view", () => {
    expect(SCENE.indexOf("for (const ring of scene.keepOut)")).toBeLessThan(
      SCENE.indexOf("for (const obstacle of scene.obstacles)"),
    );
  });

  it("stays flat on the ground in the raised view", () => {
    /* Extruding it would draw a cylinder, and a cylinder reads as a
       second object standing there rather than as a margin on the
       floor. */
    expect(SCENE_LIB).toContain("obstacleMarker(projection, o.x, o.y, radius, 0)");
    const ring = SCENE.slice(
      SCENE.indexOf("for (const ring of scene.keepOut)"),
      SCENE.indexOf("for (const obstacle of scene.obstacles)"),
    );
    expect(ring).not.toContain("COLOR.obstacleSide");
    expect(ring).toContain("ring.base.sx");
  });
});

describe("it is explained, not just drawn", () => {
  it("captions the ring wherever a map is shown", () => {
    /* Drawn without a word is worse than not drawn: a faint ring round
       an obstacle reads as "the robot nearly hit that" unless somebody
       says otherwise, and it is the opposite — the controller drives
       inside it whenever it squeezes past something. */
    const view = readFileSync(join(SRC, "components", "MapView.tsx"), "utf8");
    expect(view).toContain("mapView.keepOut");
    expect(view).toContain("hasObstacles");
  });

  it("says what it is not, as well as what it is", () => {
    const en = JSON.parse(
      readFileSync(join(SRC, "lib", "i18n", "locales", "en.json"), "utf8"),
    ) as Record<string, string>;
    const vi = JSON.parse(
      readFileSync(join(SRC, "lib", "i18n", "locales", "vi.json"), "utf8"),
    ) as Record<string, string>;
    expect(en["mapView.keepOut"]).toContain("not a collision boundary");
    expect(vi["mapView.keepOut"]).toBeTruthy();
  });

  it("stays quiet on a map with nothing to explain", () => {
    /* A caption about obstacle margins under a picture with no obstacles
       is noise that trains people to skip captions. */
    const view = readFileSync(join(SRC, "components", "MapView.tsx"), "utf8");
    expect(view).toContain("hasObstacles ? <p");
  });
});

describe("both views draw it, from one definition", () => {
  it("the flat view rings static and moving obstacles alike", () => {
    /* The planner inflates everything it plans around, so a ring on only
       half of them would be a picture of a rule that does not exist. */
    expect(CANVAS).toContain("drawRing(obstacle.center.x, obstacle.center.y");
    expect(CANVAS).toContain("drawRing(obstacle.position.x, obstacle.position.y");
  });

  it("neither view computes the radius itself", () => {
    /* Whitespace-insensitive: the call is long enough that a formatter
       wraps it, and a test that broke on line breaks would be pinning
       Prettier rather than the code. */
    const flat = CANVAS.replace(/\s+/g, "");
    const raised = SCENE_LIB.replace(/\s+/g, "");
    expect(flat).toContain("keepOutRadius(radius,map.resolution,robotRadius,positionUncertainty)");
    expect(raised).toContain(
      "keepOutRadius(o.radius,map.resolution,options.robotRadius,options.positionUncertainty",
    );
    for (const source of [CANVAS, SCENE, SCENE_LIB]) {
      expect(source).not.toContain("Math.SQRT2 *");
    }
  });
});
