/** Which of MapCanvas's two generations of pointer props answers a gesture.
 *
 * The canvas grew a full pointer lifecycle (down/move/up/cancel, with
 * capture) for the deployment form's drag handles, while three screens
 * still speak the old dialect — `onWorldClick` fired on press,
 * `onWorldDrag` per move, and *leaving the canvas ends the drag*. That
 * last habit is load-bearing: MapPainter's stroke stops at the edge
 * because of it, so turning capture on for everybody would quietly make
 * old consumers paint past their own border.
 *
 * One event, one owner. A consumer that passes the new handler for a
 * gesture has taken that gesture over, and the legacy adapter for it
 * goes silent — both firing would be a click that places a waypoint
 * *and* selects, or a drag delivered twice at different granularities.
 * The correspondence is per-gesture (down ↔ click, move ↔ drag), so a
 * consumer can adopt the new lifecycle wholesale without the old props
 * double-firing behind it.
 *
 * A pure function so the rule is testable on Node; the canvas just asks.
 */

export interface PointerRoutingInput {
  hasPointerDown: boolean;
  hasPointerMove: boolean;
  hasPointerUp: boolean;
  hasPointerCancel: boolean;
}

export interface PointerRouting {
  /** Capture the pointer on press. Only for the new lifecycle: legacy
   *  consumers rely on the pointer *escaping* the canvas to end a drag. */
  capture: boolean;
  /** Fire `onWorldClick` on press. Off once `onWorldPointerDown` owns it. */
  legacyClick: boolean;
  /** Fire `onWorldDrag` per move. Off once `onWorldPointerMove` owns it. */
  legacyDrag: boolean;
}

export function pointerRouting(input: PointerRoutingInput): PointerRouting {
  const anyPointerHandler =
    input.hasPointerDown || input.hasPointerMove || input.hasPointerUp || input.hasPointerCancel;
  return {
    capture: anyPointerHandler,
    legacyClick: !input.hasPointerDown,
    legacyDrag: !input.hasPointerMove,
  };
}
