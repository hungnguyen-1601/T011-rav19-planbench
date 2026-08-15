/** Deciding which of several in-flight answers is still wanted.
 *
 * **Why this is a module and not four lines inside a component.** Three
 * handlers on the deployment form finish after an await — checking a
 * document, previewing traffic, adopting a map — and each of them can
 * land on a page that has moved on. The failures are all the same shape
 * and none of them is visible in a screenshot: a preview of the previous
 * numbers drawn over the current map, a map's paths written under a
 * different map's grid, a green tick for a document nobody is looking at
 * any more.
 *
 * The first three attempts at this lived inline and each was subtly
 * wrong in a way the tests could not see, because the web suite runs on
 * Node with no DOM and could only grep for the *presence* of a guard.
 * Out here the interleaving itself is testable: claim, claim, finish out
 * of order, and assert which one is allowed to write.
 *
 * The rule is one sentence — **the newest claim wins, and everything
 * older is discarded** — and `supersede` is how a change that starts no
 * request of its own (typing in a field, scrubbing to another instant)
 * still cancels the ones already running.
 */

export interface Sequencer {
  /** Take the next token. The caller must hold it until its work is done. */
  claim(): number;
  /** Is this token still the newest? False once anything else claimed. */
  isCurrent(token: number): boolean;
  /** Invalidate every outstanding token without issuing one. */
  supersede(): void;
}

export function createSequencer(): Sequencer {
  let latest = 0;
  return {
    claim: () => (latest += 1),
    isCurrent: (token) => token === latest,
    supersede: () => {
      latest += 1;
    },
  };
}
