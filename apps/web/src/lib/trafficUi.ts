/** Who the map's next gesture belongs to, as one reducer.
 *
 * Three questions used to share one field: which obstacle is highlighted,
 * which of its points the next click places, and which handle a drag is
 * moving. `TrafficSelection` answered the first two with a single
 * `{index, mode}` — so "selected but placing nothing", which is what a
 * click on an obstacle's body means, had no legal value at all.
 *
 * **Three fields, one reducer, because three loose `useState`s can lie
 * to each other.** A placement pointing at obstacle A while the
 * highlight sits on B, or a drag surviving the removal of the obstacle
 * it was moving, are states no gesture produces on purpose — they only
 * appear when transitions live scattered across handlers. Every
 * transition is here, and the invariants are pinned by tests:
 *
 * - `trafficPlacement` and `activeDrag` always point at the selected
 *   obstacle;
 * - every index is in range after any document-level action.
 *
 * **The drag phase is the load-bearing part.** A pointer-down on a
 * waypoint is not yet a drag — it is a *candidate* until the pointer has
 * moved further than `dragGate` allows. Until then nothing may mutate
 * the document: a single click selects, a double-click deletes, and
 * neither should nudge the point first. Only a `committed` drag writes
 * geometry, and only a committed drag flushes anything on pointer-up.
 *
 * Decisions only — no component state, no DOM. The web tests run on
 * Node, and this file is why the interesting part does not need a
 * browser to test.
 */

import type { TrafficPlacement } from "./traffic";
import type { Point2D } from "./types";

/** One grabbable point of an authored obstacle, or its body.
 *
 * Mirrors the placement modes rather than reusing them: a placement is
 * "the next click writes this field", a handle is "this drawn point is
 * draggable" — `body` exists only as a handle (you select it, you do
 * not place it), and `sudden-stop-heading` exists only as a placement
 * (aiming is a click, not a point that persists to grab).
 */
export type TrafficHandle =
  | { kind: "waypoint"; waypoint: number }
  | { kind: "periodic-start" }
  | { kind: "periodic-end" }
  | { kind: "origin" }
  | { kind: "sudden-start" }
  /** Where a sudden stop comes to rest, when it is declared that way.
   *  Absent under the heading-and-duration spelling, which stores no
   *  such point to grab. */
  | { kind: "sudden-stop-point" }
  | { kind: "body" };

/** What the pointer went down on. */
export interface Hit {
  index: number;
  handle: TrafficHandle;
}

export interface ActiveDrag {
  hit: Hit;
  pointerId: number;
  /** `candidate` = the pointer is down but has not travelled past
   *  `dragGate`. **A candidate never mutates the document** — its
   *  pointer-up is a click, and flushing it would move a waypoint the
   *  author was only selecting or double-clicking to delete. */
  phase: "candidate" | "committed";
  /** Where the pointer went down, in client pixels — the origin the
   *  threshold is measured from. Client space on purpose: the gate is
   *  about hand steadiness, which is a property of the screen, not of
   *  the map's zoom. */
  downClient: Point2D;
}

export interface TrafficUiState {
  /** Highlighted row and brightened overlay. Survives ending a
   *  placement or a drag — the author is still "on" that obstacle. */
  selectedObstacleIndex: number | null;
  /** Which obstacle field the next map click writes. Implies selection. */
  trafficPlacement: { index: number; mode: TrafficPlacement } | null;
  /** The handle currently held down. Implies selection. */
  activeDrag: ActiveDrag | null;
}

export const IDLE_TRAFFIC_UI: TrafficUiState = {
  selectedObstacleIndex: null,
  trafficPlacement: null,
  activeDrag: null,
};

export type TrafficUiAction =
  | { type: "select"; index: number | null }
  | { type: "beginPlacement"; index: number; mode: TrafficPlacement }
  | { type: "endPlacement" }
  | { type: "beginDrag"; hit: Hit; pointerId: number; downClient: Point2D }
  | { type: "dragCommitted" }
  | { type: "endDrag" }
  /** The list grew by one at the end; `count` is the new length. The new
   *  obstacle is selected — it is what the author is about to edit. */
  | { type: "obstacleAdded"; count: number }
  | { type: "obstacleRemoved"; index: number }
  /** The whole list was swapped for another (library scenario adopted,
   *  traffic cleared for a stored/drawn map). **Clears, never clamps**:
   *  index 1 of the new list is not the same obstacle as index 1 of the
   *  old one, and a clamped selection would be in range and wrong. */
  | { type: "obstaclesReplaced" }
  /** Row `index` changed motion law. Its handles and placements name
   *  fields that no longer exist; the row itself is still the one the
   *  author is working on, so selection stays. */
  | { type: "motionKindChanged"; index: number }
  /** A new map was adopted. Nothing on it is the thing that was
   *  selected. */
  | { type: "reset" };

/** Shift an index across the removal of `removed`, or null it. */
function reindex(index: number, removed: number): number | null {
  if (index === removed) return null;
  return index > removed ? index - 1 : index;
}

export function trafficUiReducer(
  state: TrafficUiState,
  action: TrafficUiAction,
): TrafficUiState {
  switch (action.type) {
    case "select":
      // A new focus ends whatever gesture the old one had going;
      // keeping a placement aimed at another row is exactly the
      // cross-pointing this reducer exists to make unrepresentable.
      return { selectedObstacleIndex: action.index, trafficPlacement: null, activeDrag: null };
    case "beginPlacement":
      return {
        selectedObstacleIndex: action.index,
        trafficPlacement: { index: action.index, mode: action.mode },
        activeDrag: null,
      };
    case "endPlacement":
      return { ...state, trafficPlacement: null };
    case "beginDrag":
      return {
        selectedObstacleIndex: action.hit.index,
        trafficPlacement: null,
        activeDrag: {
          hit: action.hit,
          pointerId: action.pointerId,
          phase: "candidate",
          downClient: action.downClient,
        },
      };
    case "dragCommitted":
      return state.activeDrag === null
        ? state
        : { ...state, activeDrag: { ...state.activeDrag, phase: "committed" } };
    case "endDrag":
      return { ...state, activeDrag: null };
    case "obstacleAdded":
      return {
        selectedObstacleIndex: action.count - 1,
        trafficPlacement: null,
        activeDrag: null,
      };
    case "obstacleRemoved": {
      const selected =
        state.selectedObstacleIndex === null
          ? null
          : reindex(state.selectedObstacleIndex, action.index);
      const placementIndex =
        state.trafficPlacement === null
          ? null
          : reindex(state.trafficPlacement.index, action.index);
      const dragIndex =
        state.activeDrag === null ? null : reindex(state.activeDrag.hit.index, action.index);
      return {
        selectedObstacleIndex: selected,
        trafficPlacement:
          state.trafficPlacement !== null && placementIndex !== null
            ? { ...state.trafficPlacement, index: placementIndex }
            : null,
        activeDrag:
          state.activeDrag !== null && dragIndex !== null
            ? { ...state.activeDrag, hit: { ...state.activeDrag.hit, index: dragIndex } }
            : null,
      };
    }
    case "obstaclesReplaced":
    case "reset":
      return IDLE_TRAFFIC_UI;
    case "motionKindChanged":
      return {
        selectedObstacleIndex: state.selectedObstacleIndex,
        trafficPlacement:
          state.trafficPlacement?.index === action.index ? null : state.trafficPlacement,
        activeDrag: state.activeDrag?.hit.index === action.index ? null : state.activeDrag,
      };
  }
}

/** Screen pixels a pointer may wander before a press becomes a drag.
 *  Five is roughly the tremor of a deliberate double-click. */
export const DRAG_THRESHOLD_PX = 5;

/** Has this press earned the right to move things?
 *
 * Measured in client pixels from where the pointer went down. Below the
 * threshold the press is still a click — select, or half of a
 * double-click delete — and moving the waypoint under it would mutate a
 * document the author was only pointing at.
 */
export function dragGate(
  downClient: Point2D,
  currentClient: Point2D,
  thresholdPx: number = DRAG_THRESHOLD_PX,
): boolean {
  return (
    Math.hypot(currentClient.x - downClient.x, currentClient.y - downClient.y) > thresholdPx
  );
}
