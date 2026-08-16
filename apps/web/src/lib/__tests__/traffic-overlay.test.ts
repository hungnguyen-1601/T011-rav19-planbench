/** The declared traffic, turned into geometry.
 *
 * Two things are being defended here. First that every kind draws
 * something the author placed — a waypoint route with no polyline is
 * back to clicking into an empty map. Second, and less obvious, that a
 * half-typed field cannot take the canvas down: `numberFromInput` puts
 * `NaN` in a cleared box on purpose, and `ctx.arc(x, y, NaN, …)`
 * throws, so one emptied radius while editing would blank the map.
 */

import { describe, expect, it } from "vitest";

import { HEADING_ARROW_M, overlayOf } from "@/lib/trafficOverlay";
import { blankMotion } from "@/lib/traffic";
import type {
  DynamicObstacle,
  Motion,
  Point2D,
  RandomWalkMotion,
  WaypointMotion,
} from "@/lib/types";

const ANCHOR: Point2D = { x: 2, y: 3 };

function obstacle(motion: Motion, overrides: Partial<DynamicObstacle> = {}): DynamicObstacle {
  return { name: "cart", radius: 0.4, seed_time_offset: 10, motion, ...overrides };
}

function only(obstacles: DynamicObstacle[], selected: number | null = null) {
  return overlayOf(obstacles, selected).shapes[0];
}

describe("a waypoint route", () => {
  const route = obstacle({
    kind: "waypoint",
    waypoints: [
      { x: 1, y: 1 },
      { x: 5, y: 1 },
      { x: 5, y: 6 },
    ],
    speed: 0.8,
    loop: false,
    ping_pong: true,
  });

  it("draws the points in the order they are driven", () => {
    const shape = only([route]);
    expect(shape.path).toHaveLength(3);
    expect(shape.path[0]).toEqual({ x: 1, y: 1 });
    expect(shape.home).toEqual({ x: 1, y: 1 });
  });

  it("numbers each waypoint so a route crossing itself stays readable", () => {
    expect(only([route]).handles.map((grip) => grip.label)).toEqual(["1", "2", "3"]);
  });

  it("hands each point a handle naming its own position in the list", () => {
    expect(only([route]).handles[2].handle).toEqual({ kind: "waypoint", waypoint: 2 });
  });

  it("leaves the closing edge undrawn unless the route loops", () => {
    expect(only([route]).closingEdge).toBeNull();
  });

  it("draws the closing edge when it does", () => {
    const looped = obstacle({
      ...(route.motion as WaypointMotion),
      loop: true,
      ping_pong: false,
    });
    expect(only([looped]).closingEdge).toEqual([
      { x: 5, y: 6 },
      { x: 1, y: 1 },
    ]);
  });

  it("survives having every point undone", () => {
    /* `dropLastWaypoint` can empty the list. There is nothing to stand
       on then, and inventing an origin would put a disc where nobody
       placed one. */
    const empty = only([obstacle({ kind: "waypoint", waypoints: [], speed: 0.8 })]);
    expect(empty.home).toBeNull();
    expect(empty.path).toEqual([]);
    expect(empty.handles).toEqual([]);
  });
});

describe("the other three laws", () => {
  it("joins a periodic obstacle's two ends and offers both", () => {
    const shape = only([obstacle(blankMotion("periodic", ANCHOR))]);
    expect(shape.path).toHaveLength(2);
    expect(shape.handles.map((grip) => grip.handle.kind)).toEqual([
      "periodic-start",
      "periodic-end",
    ]);
  });

  it("draws a random walk's declared bound, and no route", () => {
    const shape = only([obstacle(blankMotion("random_walk", ANCHOR))]);
    expect(shape.wanderRadius).toBe(2);
    expect(shape.path).toEqual([]);
    expect(shape.handles.map((grip) => grip.handle.kind)).toEqual(["origin"]);
  });

  it("points a sudden stop the way it was aimed", () => {
    const shape = only([
      obstacle({ kind: "sudden_stop", start: { x: 0, y: 0 }, heading: 0, speed: 3, stop_time: 8 }),
    ]);
    expect(shape.heading?.to).toEqual({ x: HEADING_ARROW_M, y: 0 });
  });

  it("keeps the arrow a fixed length rather than the distance travelled", () => {
    /* `speed × stop_time` is where the obstacle stops, and working that
       out here would be a second implementation of the motion law in
       the browser — free to disagree with the run it illustrates. The
       arrow says "this way"; the preview says where. */
    const fast = only([
      obstacle({ kind: "sudden_stop", start: { x: 0, y: 0 }, heading: 0, speed: 9, stop_time: 30 }),
    ]);
    const slow = only([
      obstacle({ kind: "sudden_stop", start: { x: 0, y: 0 }, heading: 0, speed: 0.2, stop_time: 1 }),
    ]);
    expect(fast.heading).toEqual(slow.heading);
  });

  it("gives a sudden stop one grabbable point, not two", () => {
    const shape = only([obstacle(blankMotion("sudden_stop", ANCHOR))]);
    expect(shape.handles.map((grip) => grip.handle.kind)).toEqual(["sudden-start"]);
  });
});

describe("a document being typed into", () => {
  it("drops a radius that is mid-edit instead of drawing NaN", () => {
    const shape = only([obstacle(blankMotion("waypoint", ANCHOR), { radius: Number.NaN })]);
    expect(shape.radius).toBeNull();
  });

  it("drops a wander radius that is mid-edit", () => {
    const walk = blankMotion("random_walk", ANCHOR) as RandomWalkMotion;
    const shape = only([obstacle({ ...walk, max_radius: Number.NaN })]);
    expect(shape.wanderRadius).toBeNull();
  });

  it("drops a heading that is mid-edit rather than aiming at NaN", () => {
    const shape = only([
      obstacle({
        kind: "sudden_stop",
        start: { x: 1, y: 1 },
        heading: Number.NaN,
        speed: 1,
        stop_time: 2,
      }),
    ]);
    expect(shape.heading).toBeNull();
    // The start is still a real point, so it stays grabbable.
    expect(shape.handles).toHaveLength(1);
  });

  it("skips a waypoint whose coordinates are not numbers", () => {
    const shape = only([
      obstacle({
        kind: "waypoint",
        waypoints: [{ x: 1, y: 1 }, { x: Number.NaN, y: 2 }, { x: 3, y: 3 }],
        speed: 1,
      }),
    ]);
    expect(shape.path).toHaveLength(2);
  });
});

describe("the highlight", () => {
  it("marks exactly the selected obstacle", () => {
    const three = [
      obstacle(blankMotion("waypoint", ANCHOR), { name: "a" }),
      obstacle(blankMotion("periodic", ANCHOR), { name: "b" }),
      obstacle(blankMotion("random_walk", ANCHOR), { name: "c" }),
    ];
    expect(overlayOf(three, 1).shapes.map((shape) => shape.selected)).toEqual([
      false,
      true,
      false,
    ]);
  });

  it("marks none when nothing is selected", () => {
    const shapes = overlayOf([obstacle(blankMotion("waypoint", ANCHOR))], null).shapes;
    expect(shapes.every((shape) => !shape.selected)).toBe(true);
  });

  it("keeps each shape's index so a click can name the obstacle back", () => {
    const two = [
      obstacle(blankMotion("waypoint", ANCHOR)),
      obstacle(blankMotion("periodic", ANCHOR)),
    ];
    expect(overlayOf(two, null).shapes.map((shape) => shape.index)).toEqual([0, 1]);
  });
});
