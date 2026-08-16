/** The traffic being authored, as shapes the canvas can draw.
 *
 * **Why this exists.** Until now the map showed traffic only after a
 * round trip to `POST /scenarios/preview`: press Preview, and yellow
 * discs appear where the backend says the obstacles are at *t*. Placing
 * three waypoints beforehand drew nothing at all, so authoring a route
 * meant clicking into an empty map and hoping. This turns the declared
 * document into geometry, so a route is visible the moment it is
 * written.
 *
 * **This is rendering authored data, not evaluating a motion law.** The
 * distinction is the project's standing rule (see `MapCanvas`) and it
 * survives intact here: every point below is one the author placed and
 * the document stores. Nothing is advanced through time, nothing is
 * multiplied by a speed. The one drawn thing that is not a stored point
 * is the heading arrow of a `sudden_stop`, and its length is a fixed
 * display convention — deriving it from `speed × stop_time` would be
 * computing where the obstacle stops, which is the simulator's answer
 * to give and `/scenarios/preview`'s to show.
 *
 * The handles come from here rather than from a second traversal in the
 * hit-tester: what can be grabbed is exactly what is drawn, and two
 * lists would drift into a point the author can see but not catch.
 */

import type { TrafficHandle } from "./trafficUi";
import type { DynamicObstacle, Motion, Point2D } from "./types";

/** How long a heading arrow is drawn, in metres.
 *
 * **A display convention, deliberately not the distance travelled.**
 * `speed × stop_time` is where the obstacle actually stops, and working
 * that out here would put a second implementation of the motion law in
 * the browser — the thing that must not happen, because it would then
 * be free to disagree with the run. The arrow says "this way", and
 * where it ends up is what the preview is for. */
export const HEADING_ARROW_M = 1.5;

/** A point of an authored obstacle that can be drawn and grabbed. */
export interface OverlayHandle {
  at: Point2D;
  handle: TrafficHandle;
  /** Shown beside the point — the ordinal of a waypoint, so a route
   *  that crosses itself can still be read in the order it is driven. */
  label?: string;
}

/** One obstacle's authored geometry. */
export interface OverlayShape {
  index: number;
  name: string;
  /** The obstacle's own radius, or null when the box is empty mid-edit.
   *  Null draws no disc rather than an `arc()` of `NaN`. */
  radius: number | null;
  selected: boolean;
  /** Where the obstacle's name and body-disc are drawn, and what a
   *  click selects when it misses every handle. Null when the motion
   *  has no point yet — a waypoint route whose points were all undone. */
  home: Point2D | null;
  handles: OverlayHandle[];
  /** The declared points in the order they are driven. Empty for a
   *  random walk, which declares an origin and no route. */
  path: Point2D[];
  /** The edge back to the start, drawn dashed, when the route loops.
   *  A loop is a stored flag, so this is still authored data. */
  closingEdge: [Point2D, Point2D] | null;
  /** `max_radius` of a random walk — the bound the document declares,
   *  not a position. */
  wanderRadius: number | null;
  /** Fixed-length direction indicator; see `HEADING_ARROW_M`. */
  heading: { from: Point2D; to: Point2D } | null;
}

export interface TrafficOverlay {
  shapes: OverlayShape[];
}

/** A number that can be drawn.
 *
 * Half-typed boxes reach here as `NaN` on purpose (`numberFromInput`),
 * and `ctx.arc(x, y, NaN, …)` throws — one cleared radius field would
 * take the whole canvas down mid-edit. */
function drawable(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function drawablePoint(point: Point2D | undefined): point is Point2D {
  return point !== undefined && drawable(point.x) && drawable(point.y);
}

/** The declared points of a motion, in driving order. */
function pathOf(motion: Motion): Point2D[] {
  switch (motion.kind) {
    case "waypoint":
      return (motion.waypoints ?? []).filter(drawablePoint);
    case "periodic":
      return [motion.start, motion.end].filter(drawablePoint);
    case "random_walk":
    case "sudden_stop":
      return [];
  }
}

function handlesOf(motion: Motion): OverlayHandle[] {
  switch (motion.kind) {
    case "waypoint":
      return (motion.waypoints ?? []).flatMap((at, waypoint) =>
        drawablePoint(at)
          ? [{ at, handle: { kind: "waypoint" as const, waypoint }, label: String(waypoint + 1) }]
          : [],
      );
    case "periodic":
      return [
        ...(drawablePoint(motion.start)
          ? [{ at: motion.start, handle: { kind: "periodic-start" as const } }]
          : []),
        ...(drawablePoint(motion.end)
          ? [{ at: motion.end, handle: { kind: "periodic-end" as const } }]
          : []),
      ];
    case "random_walk":
      return drawablePoint(motion.origin)
        ? [{ at: motion.origin, handle: { kind: "origin" as const } }]
        : [];
    case "sudden_stop":
      return drawablePoint(motion.start)
        ? [{ at: motion.start, handle: { kind: "sudden-start" as const } }]
        : [];
  }
}

function shapeOf(obstacle: DynamicObstacle, index: number, selected: boolean): OverlayShape {
  const motion = obstacle.motion;
  const path = pathOf(motion);
  const handles = handlesOf(motion);
  const looping =
    motion.kind === "waypoint" && Boolean(motion.loop) && path.length > 2
      ? ([path[path.length - 1], path[0]] as [Point2D, Point2D])
      : null;
  const wander =
    motion.kind === "random_walk" && drawable(motion.max_radius) && motion.max_radius > 0
      ? motion.max_radius
      : null;
  const heading =
    motion.kind === "sudden_stop" &&
    drawablePoint(motion.start) &&
    drawable(motion.heading)
      ? {
          from: motion.start,
          to: {
            x: motion.start.x + Math.cos(motion.heading) * HEADING_ARROW_M,
            y: motion.start.y + Math.sin(motion.heading) * HEADING_ARROW_M,
          },
        }
      : null;
  return {
    index,
    name: obstacle.name,
    radius: drawable(obstacle.radius) && obstacle.radius > 0 ? obstacle.radius : null,
    selected,
    // The first declared point, whichever kind of point that is. Null
    // when there is none — an undone route has nothing to stand on, and
    // a fabricated origin would be a disc at a place nobody chose.
    home: handles[0]?.at ?? null,
    handles,
    path,
    closingEdge: looping,
    wanderRadius: wander,
    heading,
  };
}

/** Every authored obstacle as geometry, with one of them highlighted. */
export function overlayOf(
  obstacles: DynamicObstacle[],
  selectedIndex: number | null,
): TrafficOverlay {
  return {
    shapes: obstacles.map((obstacle, index) =>
      shapeOf(obstacle, index, index === selectedIndex),
    ),
  };
}
