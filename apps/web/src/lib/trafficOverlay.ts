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

import type { Hit, TrafficHandle } from "./trafficUi";
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

function distance(a: Point2D, b: Point2D): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** What the pointer is over, or nothing.
 *
 * **Only authored geometry is a target.** The amber preview markers
 * draw the same obstacles at an instant the backend computed, and they
 * are deliberately inert: the author's document is the thing being
 * edited, and a snapshot has no index anybody can trust back — two
 * obstacles may share a name, and the reply is a list of positions
 * rather than of rows.
 *
 * The tie-break order is fixed rather than "whatever the loop found
 * first", because ties are common: waypoint 3 of a route often sits
 * inside the body disc of the same obstacle, and two obstacles parked
 * on one aisle overlap. In order:
 *
 * 1. **a handle beats a body** — the small precise target wins over the
 *    large one it sits inside, or fine points would be unreachable;
 * 2. **nearest wins**;
 * 3. **the selected obstacle wins a tie** — the author is working on
 *    it, and having a click land on its neighbour is the more
 *    surprising outcome;
 * 4. **lower index wins**, so the answer never depends on iteration
 *    order.
 *
 * `selectedIndex` is a parameter rather than something the caller
 * applies afterwards: rule 3 is part of the decision, and a caller
 * re-doing it would be a second copy of the ordering.
 */
export function hitTest(
  obstacles: DynamicObstacle[],
  selectedIndex: number | null,
  point: Point2D,
  tolWorld: number,
): Hit | null {
  const overlay = overlayOf(obstacles, selectedIndex);
  let best: { hit: Hit; onHandle: boolean; away: number; selected: boolean } | null = null;
  const consider = (candidate: { hit: Hit; onHandle: boolean; away: number; selected: boolean }) => {
    if (best === null) {
      best = candidate;
      return;
    }
    const better =
      candidate.onHandle !== best.onHandle
        ? candidate.onHandle
        : candidate.away !== best.away
          ? candidate.away < best.away
          : candidate.selected !== best.selected
            ? candidate.selected
            : candidate.hit.index < best.hit.index;
    if (better) best = candidate;
  };

  for (const shape of overlay.shapes) {
    for (const grip of shape.handles) {
      const away = distance(grip.at, point);
      if (away <= tolWorld) {
        consider({
          hit: { index: shape.index, handle: grip.handle },
          onHandle: true,
          away,
          selected: shape.selected,
        });
      }
    }
    if (shape.home) {
      // The body is as big as the obstacle says it is, plus the same
      // slack a handle gets — a 0.35 m cart drawn small is otherwise
      // harder to click than the points on its route.
      const reach = (shape.radius ?? 0) + tolWorld;
      const away = distance(shape.home, point);
      if (away <= reach) {
        consider({
          hit: { index: shape.index, handle: { kind: "body" } },
          onHandle: false,
          away,
          selected: shape.selected,
        });
      }
    }
  }
  return best === null ? null : (best as { hit: Hit }).hit;
}

/** Move the one point a handle names, leaving the rest of the law alone.
 *
 * The sibling of `placeOnMotion`, and deliberately not the same
 * function: placing *appends* a waypoint, dragging *replaces* the one
 * being held. A drag routed through the placing version would leave a
 * trail of points behind the cursor.
 *
 * `body` moves nothing. Dragging an obstacle whole would have to decide
 * what that means for each law — every waypoint, or only the first? the
 * origin, or the whole wander circle? — and each answer is a different
 * edit. Clicking a body selects; the points are moved by their handles.
 */
export function moveHandle(motion: Motion, handle: TrafficHandle, at: Point2D): Motion {
  switch (handle.kind) {
    case "waypoint":
      return motion.kind === "waypoint"
        ? {
            ...motion,
            waypoints: motion.waypoints.map((point, index) =>
              index === handle.waypoint ? at : point,
            ),
          }
        : motion;
    case "periodic-start":
      return motion.kind === "periodic" ? { ...motion, start: at } : motion;
    case "periodic-end":
      return motion.kind === "periodic" ? { ...motion, end: at } : motion;
    case "origin":
      return motion.kind === "random_walk" ? { ...motion, origin: at } : motion;
    case "sudden-start":
      return motion.kind === "sudden_stop" ? { ...motion, start: at } : motion;
    case "body":
      return motion;
  }
}

/** Remove one waypoint by position.
 *
 * Distinct from `dropLastWaypoint`, which undoes the click that just
 * landed in a wall. This is for the point in the middle of a finished
 * route that turned out to be wrong. */
export function deleteWaypointAt(motion: Motion, waypoint: number): Motion {
  return motion.kind === "waypoint"
    ? { ...motion, waypoints: motion.waypoints.filter((_, index) => index !== waypoint) }
    : motion;
}

/** What a press on the map means. One table, so two handlers cannot
 *  each answer it differently.
 *
 * - `place`: a placement mode is armed, so the click writes the field
 *   that mode names — unchanged from before this, including the guard
 *   that stops a drag spraying waypoints;
 * - `begin-drag`: a handle is under the pointer, and the press becomes
 *   a *candidate* drag (see `trafficUi`) that must clear `dragGate`
 *   before it moves anything;
 * - `select`: an obstacle's body, which focuses it and nothing more;
 * - `mission`: nothing of the traffic is under the pointer, so the
 *   start/goal placer keeps the gesture it has always had.
 */
export function interpretPointer(
  placementArmed: boolean,
  hit: Hit | null,
): "place" | "begin-drag" | "select" | "mission" {
  if (placementArmed) return "place";
  if (hit === null) return "mission";
  return hit.handle.kind === "body" ? "select" : "begin-drag";
}

/** Whether a double-click deletes the waypoint under it.
 *
 * Three ways it must not, and each was a real way to lose a point:
 *
 * - **a placement is armed** — there, two presses are two placements,
 *   which is what the author asked for. Deleting as well would undo the
 *   second point they just made;
 * - **the pointer dragged in between** — a deliberate drag ending near
 *   where it started is not a request to delete what was just moved;
 * - **nothing grabbable is under it**, or the target is a body rather
 *   than a waypoint: only a waypoint is removable on its own. The other
 *   points are the motion law's own fields, and a law missing its start
 *   is not a law with one fewer point.
 */
export function interpretDoubleClick(
  placementArmed: boolean,
  hit: Hit | null,
  draggedInSequence: boolean,
): { delete: true; index: number; waypoint: number } | { delete: false } {
  if (placementArmed || draggedInSequence || hit === null) return { delete: false };
  return hit.handle.kind === "waypoint"
    ? { delete: true, index: hit.index, waypoint: hit.handle.waypoint }
    : { delete: false };
}
