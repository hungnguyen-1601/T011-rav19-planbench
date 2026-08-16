/** One event, one owner — the rule that keeps MapCanvas's two prop
 * generations from double-firing.
 *
 * The stakes on each side: fired twice, a press both places a waypoint
 * and selects; captured for a legacy consumer, MapPainter's stroke no
 * longer stops at the canvas edge, because leaving the canvas is how
 * the old lifecycle ends a drag.
 */

import { describe, expect, it } from "vitest";

import { pointerRouting } from "@/lib/pointerRouting";

const NONE = {
  hasPointerDown: false,
  hasPointerMove: false,
  hasPointerUp: false,
  hasPointerCancel: false,
};

describe("a legacy-only consumer", () => {
  it("keeps both adapters and never captures", () => {
    expect(pointerRouting(NONE)).toEqual({
      capture: false,
      legacyClick: true,
      legacyDrag: true,
    });
  });
});

describe("the new lifecycle", () => {
  it("owning the press silences the click adapter, and only that one", () => {
    expect(pointerRouting({ ...NONE, hasPointerDown: true })).toEqual({
      capture: true,
      legacyClick: false,
      legacyDrag: true,
    });
  });

  it("owning the move silences the drag adapter, and only that one", () => {
    expect(pointerRouting({ ...NONE, hasPointerMove: true })).toEqual({
      capture: true,
      legacyClick: true,
      legacyDrag: false,
    });
  });

  it("owning the whole lifecycle silences both", () => {
    expect(
      pointerRouting({
        hasPointerDown: true,
        hasPointerMove: true,
        hasPointerUp: true,
        hasPointerCancel: true,
      }),
    ).toEqual({ capture: true, legacyClick: false, legacyDrag: false });
  });

  it("even an up/cancel-only consumer gets capture", () => {
    /* Capture is what guarantees up and cancel *arrive*. A consumer
       listening for them has asked for the lifecycle, whichever half it
       implements. The legacy adapters stay: no new handler claimed
       those gestures. */
    expect(pointerRouting({ ...NONE, hasPointerUp: true })).toEqual({
      capture: true,
      legacyClick: true,
      legacyDrag: true,
    });
  });
});
