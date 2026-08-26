/** Taking back the last thing that changed the document.
 *
 * **Why a stack of whole documents rather than a list of edits.** An
 * edit log would have to know how to invert every operation the form
 * offers — a dragged waypoint, an adopted map that rewrites three
 * fields at once, a vehicle that fills five. Each inverse is a second
 * definition of what the operation did, free to disagree with it. A
 * snapshot cannot disagree with itself: undo is *put this back*.
 *
 * **Runs of the same edit collapse into one.** Typing `0.35` into a
 * radius is four keystrokes and four writes, and four undos to get back
 * to where the box started would make the feature useless. Consecutive
 * entries carrying the same `label` are one entry — the *first* of the
 * run is kept, because that is the state before the author started
 * changing that thing. Anything that should be undoable on its own
 * gives itself a label nothing else uses.
 *
 * Bounded, because a snapshot is a whole profile and a long editing
 * session would otherwise hold every version of it ever typed.
 */

export interface Snapshot<T> {
  /** What kind of change this state precedes. Two neighbours sharing
   *  one label are the same continuous edit. */
  label: string;
  value: T;
}

/** How many steps back the form remembers. Deep enough to cover a wrong
 *  turn while authoring, shallow enough that a profile-sized snapshot
 *  per entry stays cheap. */
export const HISTORY_LIMIT = 50;

/** Record the state a change is about to replace.
 *
 * Called *before* the change, with the document as it still is. The
 * result is a new array — the caller holds it in state, so mutating in
 * place would leave React unaware anything happened.
 */
export function pushHistory<T>(
  stack: Snapshot<T>[],
  label: string,
  value: T,
  limit: number = HISTORY_LIMIT,
): Snapshot<T>[] {
  const previous = stack[stack.length - 1];
  // Same label as the entry already on top: this is the continuation of
  // an edit whose starting point is already recorded. Keep the older
  // one — it is the state the author would expect one undo to reach.
  if (previous && previous.label === label) return stack;
  const grown = [...stack, { label, value }];
  return grown.length > limit ? grown.slice(grown.length - limit) : grown;
}

export interface UndoResult<T> {
  stack: Snapshot<T>[];
  /** The state to put back. */
  value: T;
  /** The entry the caller should hand to the redo stack, holding the
   *  state being left behind. */
  undone: Snapshot<T>;
}

/** Step back one entry, or nothing when there is no history.
 *
 * `current` is the state being left, and it comes back inside `undone`
 * so the caller can offer a redo without having to snapshot separately
 * — the two stacks are then exact mirrors of each other.
 */
export function undoHistory<T>(stack: Snapshot<T>[], current: T): UndoResult<T> | null {
  const last = stack[stack.length - 1];
  if (!last) return null;
  return {
    stack: stack.slice(0, -1),
    value: last.value,
    undone: { label: last.label, value: current },
  };
}
