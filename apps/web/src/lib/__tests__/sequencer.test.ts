/** The interleavings, tested as interleavings.
 *
 * Three rounds of review found the same class of bug three times on this
 * form — a preview of the old numbers drawn over the new map, a map's
 * paths written under a different map's grid, a green tick for a
 * document nobody was looking at — and each time the fix was checked by
 * grepping the component for the presence of a guard. A grep cannot see
 * *when* a token is claimed, which is exactly what was wrong the third
 * time: the sequence was taken when the answer came back rather than
 * when the author chose, so the slower of two maps won.
 *
 * The web suite runs on Node with no DOM, so the click cannot be
 * simulated. The decision behind the click can, once it lives in a
 * module of its own.
 */

import { describe, expect, it } from "vitest";

import { createSequencer } from "@/lib/sequencer";

describe("the newest claim wins", () => {
  it("lets the only claim write", () => {
    const seq = createSequencer();
    expect(seq.isCurrent(seq.claim())).toBe(true);
  });

  it("keeps the second choice when the first answers last", () => {
    /** The bug this exists for, spelled out.
     *
     * Somebody picks map A, then picks map B before A has loaded. B
     * answers first, A answers second. If the order is decided by the
     * answers, A — the map nobody has selected — is the one that gets
     * written. Deciding it at the moment of choosing is what makes B
     * win regardless of who the server serves faster.
     */
    const seq = createSequencer();
    const a = seq.claim();
    const b = seq.claim();

    expect(seq.isCurrent(b)).toBe(true); // B answers first: still wanted
    expect(seq.isCurrent(a)).toBe(false); // A answers later: discarded
  });

  it("discards every earlier claim, not only the one before", () => {
    const seq = createSequencer();
    const first = seq.claim();
    const second = seq.claim();
    const third = seq.claim();

    expect([seq.isCurrent(first), seq.isCurrent(second), seq.isCurrent(third)]).toEqual([
      false,
      false,
      true,
    ]);
  });
});

describe("superseding without asking for anything", () => {
  it("cancels what is in flight", () => {
    /* Typing in a field starts no request of its own, and still means
       every answer already on its way is about a document that no longer
       exists. */
    const seq = createSequencer();
    const running = seq.claim();
    seq.supersede();
    expect(seq.isCurrent(running)).toBe(false);
  });

  it("does not hand out the token it burned", () => {
    const seq = createSequencer();
    seq.claim();
    seq.supersede();
    const next = seq.claim();
    expect(seq.isCurrent(next)).toBe(true);
  });

  it("leaves a later claim untouched", () => {
    const seq = createSequencer();
    seq.supersede();
    const after = seq.claim();
    expect(seq.isCurrent(after)).toBe(true);
  });

  it("cancels just as well through a claim nobody uses", () => {
    /* Picking the blank option in the map picker starts no request, and
       it still has to cancel the one already running: it says "not that
       map". Claiming and discarding the token is the same statement as
       superseding, which is why the picker can take its token before it
       knows whether it has anything to fetch. */
    const seq = createSequencer();
    const running = seq.claim();
    seq.claim(); // taken by the choice that fetches nothing
    expect(seq.isCurrent(running)).toBe(false);
  });
});

describe("two sequencers are two questions", () => {
  it("do not interfere", () => {
    /* Scrubbing to another instant retires the picture without
       invalidating a verdict about the document, so the preview and the
       document check count separately. */
    const preview = createSequencer();
    const adoption = createSequencer();
    const drawing = preview.claim();
    adoption.claim();
    adoption.supersede();
    expect(preview.isCurrent(drawing)).toBe(true);
  });
});
