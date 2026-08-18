/** The reducer that keeps selection, placement and drag honest.
 *
 * Three fields answer three questions about the map's next gesture, and
 * the failure this file guards against is them answering about
 * *different obstacles*: a placement aimed at row 2 while row 0 is
 * highlighted, or a drag surviving the removal of the obstacle it was
 * moving. Every test that matters here is either a transition from the
 * matrix in the plan or one of the two invariants.
 *
 * The drag phase tests are the load-bearing ones. A candidate drag is a
 * press that has not yet travelled past `dragGate`, and it must never
 * mutate the document — its pointer-up is a click. The reducer cannot
 * enforce "no flush" itself (flushing is the form's job), but it is the
 * single source of the `phase` field the form consults, so the phase
 * arithmetic is pinned here.
 */

import { describe, expect, it } from "vitest";

import {
  DRAG_THRESHOLD_PX,
  IDLE_TRAFFIC_UI,
  dragGate,
  trafficUiReducer,
  type Hit,
  type TrafficUiAction,
  type TrafficUiState,
} from "@/lib/trafficUi";

const HIT: Hit = { index: 1, handle: { kind: "waypoint", waypoint: 2 } };

function run(actions: TrafficUiAction[], from: TrafficUiState = IDLE_TRAFFIC_UI): TrafficUiState {
  return actions.reduce(trafficUiReducer, from);
}

/** The two statements no sequence of actions may break. */
function invariants(state: TrafficUiState): void {
  if (state.trafficPlacement !== null) {
    expect(state.selectedObstacleIndex).toBe(state.trafficPlacement.index);
  }
  if (state.activeDrag !== null) {
    expect(state.selectedObstacleIndex).toBe(state.activeDrag.hit.index);
  }
}

describe("select", () => {
  it("highlights the row and ends whatever gesture the old focus had", () => {
    const state = run([
      { type: "beginPlacement", index: 0, mode: "waypoint" },
      { type: "select", index: 2 },
    ]);
    expect(state).toEqual({
      selectedObstacleIndex: 2,
      trafficPlacement: null,
      activeDrag: null,
    });
  });

  it("select(null) clears everything", () => {
    const state = run([
      { type: "beginDrag", hit: HIT, pointerId: 7, downClient: { x: 0, y: 0 } },
      { type: "select", index: null },
    ]);
    expect(state).toEqual(IDLE_TRAFFIC_UI);
  });
});

describe("placement", () => {
  it("implies selection of the same row", () => {
    const state = run([{ type: "beginPlacement", index: 3, mode: "periodic-end" }]);
    expect(state.selectedObstacleIndex).toBe(3);
    expect(state.trafficPlacement).toEqual({ index: 3, mode: "periodic-end" });
    invariants(state);
  });

  it("ending a placement keeps the row selected", () => {
    /* The author aimed clicks at this obstacle a moment ago; dropping
       the highlight with the mode would make the panel forget where
       they were working. */
    const state = run([
      { type: "beginPlacement", index: 3, mode: "periodic-end" },
      { type: "endPlacement" },
    ]);
    expect(state.selectedObstacleIndex).toBe(3);
    expect(state.trafficPlacement).toBeNull();
  });

  it("beginPlacement ends a drag; beginDrag ends a placement", () => {
    const placed = run([
      { type: "beginDrag", hit: HIT, pointerId: 1, downClient: { x: 0, y: 0 } },
      { type: "beginPlacement", index: 1, mode: "waypoint" },
    ]);
    expect(placed.activeDrag).toBeNull();
    const dragged = run([
      { type: "beginPlacement", index: 1, mode: "waypoint" },
      { type: "beginDrag", hit: HIT, pointerId: 1, downClient: { x: 0, y: 0 } },
    ]);
    expect(dragged.trafficPlacement).toBeNull();
    invariants(placed);
    invariants(dragged);
  });
});

describe("the drag phase", () => {
  it("a fresh drag is a candidate, not yet a mutation", () => {
    const state = run([
      { type: "beginDrag", hit: HIT, pointerId: 9, downClient: { x: 100, y: 50 } },
    ]);
    expect(state.activeDrag).toEqual({
      hit: HIT,
      pointerId: 9,
      phase: "candidate",
      downClient: { x: 100, y: 50 },
    });
    expect(state.selectedObstacleIndex).toBe(HIT.index);
  });

  it("commits in place, keeping the same hit and pointer", () => {
    const state = run([
      { type: "beginDrag", hit: HIT, pointerId: 9, downClient: { x: 100, y: 50 } },
      { type: "dragCommitted" },
    ]);
    expect(state.activeDrag?.phase).toBe("committed");
    expect(state.activeDrag?.hit).toEqual(HIT);
  });

  it("committing with no drag in flight changes nothing", () => {
    expect(run([{ type: "dragCommitted" }])).toEqual(IDLE_TRAFFIC_UI);
  });

  it("ending a drag keeps the row selected", () => {
    const state = run([
      { type: "beginDrag", hit: HIT, pointerId: 9, downClient: { x: 0, y: 0 } },
      { type: "dragCommitted" },
      { type: "endDrag" },
    ]);
    expect(state.activeDrag).toBeNull();
    expect(state.selectedObstacleIndex).toBe(HIT.index);
  });
});

describe("the document changing underneath", () => {
  it("adding selects the new obstacle", () => {
    const state = run([{ type: "obstacleAdded", count: 3 }]);
    expect(state.selectedObstacleIndex).toBe(2);
    expect(state.trafficPlacement).toBeNull();
  });

  it("removing the selected obstacle clears the selection", () => {
    const state = run([
      { type: "select", index: 1 },
      { type: "obstacleRemoved", index: 1 },
    ]);
    expect(state.selectedObstacleIndex).toBeNull();
  });

  it("removing an earlier obstacle shifts every index down", () => {
    const state = run(
      [{ type: "obstacleRemoved", index: 0 }],
      {
        selectedObstacleIndex: 2,
        trafficPlacement: { index: 2, mode: "waypoint" },
        activeDrag: {
          hit: { index: 2, handle: { kind: "body" } },
          pointerId: 1,
          phase: "candidate",
          downClient: { x: 0, y: 0 },
        },
      },
    );
    expect(state.selectedObstacleIndex).toBe(1);
    expect(state.trafficPlacement?.index).toBe(1);
    expect(state.activeDrag?.hit.index).toBe(1);
    invariants(state);
  });

  it("removing the obstacle a gesture was about kills the gesture", () => {
    const state = run([
      { type: "beginDrag", hit: HIT, pointerId: 1, downClient: { x: 0, y: 0 } },
      { type: "obstacleRemoved", index: HIT.index },
    ]);
    expect(state).toEqual(IDLE_TRAFFIC_UI);
  });

  it("replacing the list clears rather than clamps", () => {
    /* Index 1 of the new list is not the same obstacle as index 1 of
       the old one. A clamped selection would be in range and wrong —
       highlighted, draggable, and somebody else's cart. */
    const state = run([
      { type: "select", index: 1 },
      { type: "obstaclesReplaced" },
    ]);
    expect(state).toEqual(IDLE_TRAFFIC_UI);
  });

  it("a motion-law change keeps the row selected but drops its gestures", () => {
    /* The row is still the one being edited; its handles and placement
       modes name fields of a law that no longer exists. */
    const state = run([
      { type: "beginPlacement", index: 1, mode: "waypoint" },
      { type: "motionKindChanged", index: 1 },
    ]);
    expect(state.selectedObstacleIndex).toBe(1);
    expect(state.trafficPlacement).toBeNull();
  });

  it("a motion-law change on another row touches nothing", () => {
    const state = run([
      { type: "beginPlacement", index: 1, mode: "waypoint" },
      { type: "motionKindChanged", index: 0 },
    ]);
    expect(state.trafficPlacement).toEqual({ index: 1, mode: "waypoint" });
  });

  it("adopting a map resets all three", () => {
    const state = run([
      { type: "beginPlacement", index: 1, mode: "waypoint" },
      { type: "reset" },
    ]);
    expect(state).toEqual(IDLE_TRAFFIC_UI);
  });
});

describe("invariants across mixed sequences", () => {
  const sequences: TrafficUiAction[][] = [
    [
      { type: "select", index: 0 },
      { type: "beginPlacement", index: 2, mode: "periodic-start" },
      { type: "obstacleRemoved", index: 1 },
    ],
    [
      { type: "beginDrag", hit: HIT, pointerId: 1, downClient: { x: 0, y: 0 } },
      { type: "dragCommitted" },
      { type: "obstacleRemoved", index: 0 },
    ],
    [
      { type: "obstacleAdded", count: 2 },
      { type: "beginPlacement", index: 1, mode: "waypoint" },
      { type: "motionKindChanged", index: 1 },
      { type: "endDrag" },
    ],
  ];

  it.each(sequences.map((actions, at) => [at, actions] as const))(
    "sequence %d never lets the three fields point at different obstacles",
    (_at, actions) => {
      let state = IDLE_TRAFFIC_UI;
      for (const action of actions) {
        state = trafficUiReducer(state, action);
        invariants(state);
      }
    },
  );
});

describe("dragGate", () => {
  it("holds a steady press below the threshold", () => {
    expect(dragGate({ x: 100, y: 100 }, { x: 103, y: 102 })).toBe(false);
  });

  it("opens once the pointer has travelled", () => {
    expect(dragGate({ x: 100, y: 100 }, { x: 100, y: 100 + DRAG_THRESHOLD_PX + 1 })).toBe(true);
  });

  it("measures diagonally, not per axis", () => {
    // 4 px in each axis is ~5.66 px of travel — past a 5 px gate even
    // though neither axis alone is.
    expect(dragGate({ x: 0, y: 0 }, { x: 4, y: 4 })).toBe(true);
  });

  it("takes a caller's own threshold", () => {
    expect(dragGate({ x: 0, y: 0 }, { x: 4, y: 4 }, 10)).toBe(false);
  });
});
