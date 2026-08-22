/** Taking back the last change, and how much "the last change" is.
 *
 * The collapsing rule is what makes this usable rather than annoying:
 * typing `0.35` into a box is four writes, and four undos to get back
 * to where the box started would be worse than no undo at all. What is
 * pinned here is that a run collapses to the state *before* it, and
 * that things which should be separate steps stay separate.
 */

import { describe, expect, it } from "vitest";

import { HISTORY_LIMIT, pushHistory, undoHistory, type Snapshot } from "@/lib/undo";

const empty: Snapshot<string>[] = [];

describe("recording what a change replaces", () => {
  it("keeps the state a change is about to overwrite", () => {
    const stack = pushHistory(empty, "robot.radius", "before");
    expect(stack).toEqual([{ label: "robot.radius", value: "before" }]);
  });

  it("collapses a run of the same edit to its starting point", () => {
    /* Four keystrokes into one box. The state worth returning to is
       the one before the first of them, not the one before the last. */
    let stack = pushHistory(empty, "robot.radius", "0");
    stack = pushHistory(stack, "robot.radius", "0.");
    stack = pushHistory(stack, "robot.radius", "0.3");
    stack = pushHistory(stack, "robot.radius", "0.35");
    expect(stack).toHaveLength(1);
    expect(stack[0].value).toBe("0");
  });

  it("starts a new step when the edit moves to something else", () => {
    let stack = pushHistory(empty, "robot.radius", "a");
    stack = pushHistory(stack, "constraints.episode_timeout_s", "b");
    expect(stack.map((entry) => entry.label)).toEqual([
      "robot.radius",
      "constraints.episode_timeout_s",
    ]);
  });

  it("separates two gestures that touch the same field", () => {
    /* Every frame of one drag shares a label; the next drag is given a
       new one. Without that, dragging a waypoint twice would cost one
       undo and lose both moves. */
    let stack = pushHistory(empty, "drag#1", "a");
    stack = pushHistory(stack, "drag#1", "b");
    stack = pushHistory(stack, "drag#2", "c");
    expect(stack.map((entry) => entry.value)).toEqual(["a", "c"]);
  });

  it("returning to a field after leaving it is a new step", () => {
    let stack = pushHistory(empty, "a", "1");
    stack = pushHistory(stack, "b", "2");
    stack = pushHistory(stack, "a", "3");
    expect(stack).toHaveLength(3);
  });

  it("forgets the oldest entries rather than growing without end", () => {
    /* A snapshot is a whole profile, and a long session would
       otherwise hold every version of it ever typed. */
    let stack = empty;
    for (let step = 0; step < HISTORY_LIMIT + 10; step += 1) {
      stack = pushHistory(stack, `step-${step}`, String(step));
    }
    expect(stack).toHaveLength(HISTORY_LIMIT);
    expect(stack[0].value).toBe("10");
  });

  it("never mutates the stack it was given", () => {
    const before = pushHistory(empty, "a", "1");
    const after = pushHistory(before, "b", "2");
    expect(before).toHaveLength(1);
    expect(after).toHaveLength(2);
  });
});

describe("stepping back", () => {
  it("returns the state to put back and the shortened stack", () => {
    const stack = pushHistory(empty, "a", "old");
    const step = undoHistory(stack, "current");
    expect(step?.value).toBe("old");
    expect(step?.stack).toEqual([]);
  });

  it("hands back what was left behind, so redo needs no second snapshot", () => {
    /* The two stacks are exact mirrors: whatever undo takes off one,
       redo puts on the other, and neither has to know how the state
       was built. */
    const stack = pushHistory(empty, "a", "old");
    const step = undoHistory(stack, "current");
    expect(step?.undone).toEqual({ label: "a", value: "current" });
  });

  it("does nothing when there is nothing to go back to", () => {
    expect(undoHistory(empty, "current")).toBeNull();
  });

  it("walks back through several steps in order", () => {
    let stack = pushHistory(empty, "a", "1");
    stack = pushHistory(stack, "b", "2");
    stack = pushHistory(stack, "c", "3");

    const first = undoHistory(stack, "4");
    expect(first?.value).toBe("3");
    const second = undoHistory(first!.stack, first!.value);
    expect(second?.value).toBe("2");
    const third = undoHistory(second!.stack, second!.value);
    expect(third?.value).toBe("1");
    expect(undoHistory(third!.stack, third!.value)).toBeNull();
  });

  it("round-trips through redo", () => {
    const stack = pushHistory(empty, "a", "old");
    const back = undoHistory(stack, "new")!;
    const forward = undoHistory([back.undone], back.value)!;
    expect(forward.value).toBe("new");
  });
});
