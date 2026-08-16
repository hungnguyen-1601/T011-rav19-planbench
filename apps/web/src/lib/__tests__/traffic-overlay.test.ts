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

import {
  HEADING_ARROW_M,
  deleteWaypointAt,
  hitTest,
  interpretDoubleClick,
  interpretPointer,
  moveHandle,
  overlayOf,
} from "@/lib/trafficOverlay";
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

describe("finding what is under the pointer", () => {
  const route = obstacle(
    {
      kind: "waypoint",
      waypoints: [
        { x: 0, y: 0 },
        { x: 10, y: 0 },
      ],
      speed: 1,
    },
    { radius: 0.5 },
  );

  it("catches a waypoint the pointer is near", () => {
    expect(hitTest([route], null, { x: 10.1, y: 0.05 }, 0.3)).toEqual({
      index: 0,
      handle: { kind: "waypoint", waypoint: 1 },
    });
  });

  it("finds nothing out in the open", () => {
    expect(hitTest([route], null, { x: 40, y: 40 }, 0.3)).toBeNull();
  });

  it("lets a handle win over the body it sits inside", () => {
    /* Waypoint 0 is the route's first point *and* the centre of the
       body disc. Without this order the fine target is unreachable —
       every press on it would select instead of grab. */
    expect(hitTest([route], null, { x: 0, y: 0 }, 0.3)?.handle).toEqual({
      kind: "waypoint",
      waypoint: 0,
    });
  });

  it("selects the body when the press is on it but off every point", () => {
    // Inside the 0.5 m radius, well away from either end of the route.
    expect(hitTest([route], null, { x: 0.4, y: 0.3 }, 0.05)?.handle).toEqual({ kind: "body" });
  });

  it("takes the nearer of two candidates", () => {
    const pair = [
      obstacle({ kind: "waypoint", waypoints: [{ x: 0, y: 0 }], speed: 1 }, { name: "a" }),
      obstacle({ kind: "waypoint", waypoints: [{ x: 1, y: 0 }], speed: 1 }, { name: "b" }),
    ];
    expect(hitTest(pair, null, { x: 0.9, y: 0 }, 2)?.index).toBe(1);
  });

  it("gives an exact tie to the obstacle already selected", () => {
    /* Two carts parked on top of each other. The author is working on
       one of them, and having the press land on its neighbour is the
       more surprising of the two outcomes. */
    const stacked = [
      obstacle({ kind: "waypoint", waypoints: [{ x: 5, y: 5 }], speed: 1 }, { name: "a" }),
      obstacle({ kind: "waypoint", waypoints: [{ x: 5, y: 5 }], speed: 1 }, { name: "b" }),
    ];
    expect(hitTest(stacked, 1, { x: 5, y: 5 }, 0.3)?.index).toBe(1);
    expect(hitTest(stacked, 0, { x: 5, y: 5 }, 0.3)?.index).toBe(0);
  });

  it("falls back to the lower index so the answer never depends on order", () => {
    const stacked = [
      obstacle({ kind: "waypoint", waypoints: [{ x: 5, y: 5 }], speed: 1 }, { name: "a" }),
      obstacle({ kind: "waypoint", waypoints: [{ x: 5, y: 5 }], speed: 1 }, { name: "b" }),
    ];
    expect(hitTest(stacked, null, { x: 5, y: 5 }, 0.3)?.index).toBe(0);
  });

  it("scales its reach with the tolerance it is given", () => {
    /* The caller converts a pixel tolerance at the current zoom. A map
       zoomed out has a very different idea of how far 8 px is. */
    expect(hitTest([route], null, { x: 11, y: 0 }, 0.3)).toBeNull();
    expect(hitTest([route], null, { x: 11, y: 0 }, 1.5)).not.toBeNull();
  });
});

describe("moving a held handle", () => {
  it("replaces the waypoint being dragged rather than appending one", () => {
    /* The difference from `placeOnMotion`, and the whole reason this
       exists: routing a drag through the placing version would leave a
       trail of points behind the cursor. */
    const moved = moveHandle(
      {
        kind: "waypoint",
        waypoints: [
          { x: 0, y: 0 },
          { x: 1, y: 1 },
          { x: 2, y: 2 },
        ],
        speed: 1,
      },
      { kind: "waypoint", waypoint: 1 },
      { x: 9, y: 9 },
    );
    expect(moved.kind === "waypoint" && moved.waypoints).toEqual([
      { x: 0, y: 0 },
      { x: 9, y: 9 },
      { x: 2, y: 2 },
    ]);
  });

  it("moves each law's own point and leaves the rest of it alone", () => {
    const periodic = moveHandle(
      blankMotion("periodic", ANCHOR),
      { kind: "periodic-end" },
      { x: 7, y: 7 },
    );
    expect(periodic.kind === "periodic" && periodic.end).toEqual({ x: 7, y: 7 });
    expect(periodic.kind === "periodic" && periodic.period).toBe(12);

    const walk = moveHandle(blankMotion("random_walk", ANCHOR), { kind: "origin" }, { x: 4, y: 4 });
    expect(walk.kind === "random_walk" && walk.origin).toEqual({ x: 4, y: 4 });

    const stop = moveHandle(
      blankMotion("sudden_stop", ANCHOR),
      { kind: "sudden-start" },
      { x: 3, y: 1 },
    );
    expect(stop.kind === "sudden_stop" && stop.start).toEqual({ x: 3, y: 1 });
  });

  it("moves nothing for a body", () => {
    /* Dragging an obstacle whole would have to decide what that means
       per law — every waypoint or just the first? — and each answer is
       a different edit. Bodies are for selecting. */
    const motion = blankMotion("waypoint", ANCHOR);
    expect(moveHandle(motion, { kind: "body" }, { x: 9, y: 9 })).toEqual(motion);
  });

  it("ignores a handle that does not belong to the law", () => {
    const motion = blankMotion("periodic", ANCHOR);
    expect(moveHandle(motion, { kind: "waypoint", waypoint: 0 }, { x: 9, y: 9 })).toEqual(motion);
  });
});

describe("deleting one waypoint", () => {
  it("removes the point named and keeps the order of the rest", () => {
    const trimmed = deleteWaypointAt(
      {
        kind: "waypoint",
        waypoints: [
          { x: 0, y: 0 },
          { x: 1, y: 1 },
          { x: 2, y: 2 },
        ],
        speed: 1,
      },
      1,
    );
    expect(trimmed.kind === "waypoint" && trimmed.waypoints).toEqual([
      { x: 0, y: 0 },
      { x: 2, y: 2 },
    ]);
  });

  it("leaves a law with no waypoints untouched", () => {
    const motion = blankMotion("periodic", ANCHOR);
    expect(deleteWaypointAt(motion, 0)).toEqual(motion);
  });
});

describe("what a press means", () => {
  const onHandle = { index: 0, handle: { kind: "waypoint" as const, waypoint: 0 } };
  const onBody = { index: 0, handle: { kind: "body" as const } };

  it("places while a placement is armed, whatever is under the pointer", () => {
    expect(interpretPointer(true, onHandle)).toBe("place");
    expect(interpretPointer(true, null)).toBe("place");
  });

  it("grabs a handle, selects a body, and leaves open floor to the mission", () => {
    expect(interpretPointer(false, onHandle)).toBe("begin-drag");
    expect(interpretPointer(false, onBody)).toBe("select");
    expect(interpretPointer(false, null)).toBe("mission");
  });
});

describe("what a double-click means", () => {
  const onWaypoint = { index: 2, handle: { kind: "waypoint" as const, waypoint: 1 } };
  const onBody = { index: 2, handle: { kind: "body" as const } };

  it("removes the waypoint under it", () => {
    expect(interpretDoubleClick(false, onWaypoint, false)).toEqual({
      delete: true,
      index: 2,
      waypoint: 1,
    });
  });

  it("does not delete while a placement is armed", () => {
    /* There, two presses are two placements — which is what was asked
       for. Deleting as well would undo the point just made. */
    expect(interpretDoubleClick(true, onWaypoint, false)).toEqual({ delete: false });
  });

  it("does not delete when the pointer dragged in between", () => {
    /* A deliberate drag that happens to end near where it started is
       not a request to remove what was just moved. */
    expect(interpretDoubleClick(false, onWaypoint, true)).toEqual({ delete: false });
  });

  it("does not delete a body or empty floor", () => {
    /* Only a waypoint is removable on its own: the other points are
       the law's own fields, and a periodic motion missing its start is
       not a motion with one fewer point. */
    expect(interpretDoubleClick(false, onBody, false)).toEqual({ delete: false });
    expect(interpretDoubleClick(false, null, false)).toEqual({ delete: false });
  });
});
