/** The collision-bound cell, on the four shapes the stored runs contain.
 *
 * Every case below is taken from a real run, because the two that matter
 * are ones a hand-written fixture would not think to invent: a clean
 * record whose episodes were nearly all replays, and a candidate that
 * collided and therefore has no bound at all.
 */

import { describe, expect, it } from "vitest";

import { collisionBoundCell } from "@/lib/collisionBound";
import type { RunCandidate } from "@/lib/decisions";

const withG2 = (g2: Record<string, unknown> | null, over: Partial<RunCandidate> = {}) =>
  ({
    candidate_id: "c",
    n_distinct_episodes: 30,
    gates: g2 ? { G2: g2 } : {},
    ...over,
  }) as unknown as RunCandidate;

describe("a clean record", () => {
  it("quotes the bound with the sample it rests on", () => {
    /* Run 5753d464c9f6. */
    expect(
      collisionBoundCell(
        withG2({ observed: 0, upper_bound_95: 0.1, n_runs: 30, n_distinct_episodes: 30 }),
      ),
    ).toEqual({ kind: "bound", bound: 0.1, observed: 0, distinct: 30 });
  });

  it("counts distinct episodes, not rows", () => {
    /* Run 98f6cdb257e7: thirty rows, one distinct episode, bound 3.0.
       The gate publishes both counts and its own comment says why —
       quoting the row count "is what produced a card claiming 3.0% from
       one episode driven a hundred times". */
    const cell = collisionBoundCell(
      withG2({ observed: 0, upper_bound_95: 3.0, n_runs: 30, n_distinct_episodes: 1 }),
    );
    expect(cell).toEqual({ kind: "bound", bound: 3.0, observed: 0, distinct: 1 });
  });

  it("does not clamp a bound that came out above one", () => {
    /* `3/1` is 300%, vacuous as a probability and easy to mistake for a
       rendering fault. It is what one distinct episode supports, and the
       denominator beside it says so; clamping would turn an obviously
       useless bound into a plausible-looking one. */
    const cell = collisionBoundCell(
      withG2({ observed: 0, upper_bound_95: 3.0, n_distinct_episodes: 1 }),
    );
    expect(cell.kind).toBe("bound");
    expect(cell.kind === "bound" && cell.bound).toBe(3.0);
  });
});

describe("a record with collisions in it", () => {
  it("says the rule does not apply rather than quoting a bound", () => {
    /* Run cb323e9d542b. The rule of three is for zero-event data only,
       so the platform publishes `upper_bound_95: null` (gates.py:199). */
    expect(
      collisionBoundCell(
        withG2({ observed: 34, upper_bound_95: null, n_runs: 245, n_distinct_episodes: 85 }),
      ),
    ).toEqual({ kind: "notApplicable", observed: 34, distinct: 85 });
  });

  it("still carries the sample, so the reader can weigh the count", () => {
    /* 38 collisions in 245 distinct episodes and 34 in 85 are different
       findings; the count alone does not separate them. */
    const cell = collisionBoundCell(
      withG2({ observed: 38, upper_bound_95: null, n_runs: 245, n_distinct_episodes: 245 }),
    );
    expect(cell).toEqual({ kind: "notApplicable", observed: 38, distinct: 245 });
  });

  it("keys on the missing bound, not on the collision count", () => {
    /* The platform decides when a bound may be quoted. Re-deriving that
       rule here would be a second place for it to be decided, free to
       drift from the gate that produced the verdict. */
    const odd = collisionBoundCell(withG2({ observed: 0, upper_bound_95: null, n_distinct_episodes: 30 }));
    expect(odd.kind).toBe("notApplicable");
  });
});

describe("a run that recorded nothing", () => {
  it("says unknown when there is no G2 payload", () => {
    expect(collisionBoundCell(withG2(null))).toEqual({ kind: "unknown" });
  });

  it("says unknown rather than guessing a denominator", () => {
    /* No distinct count anywhere: a bound without the sample it rests on
       is the thing this cell exists to stop showing. */
    expect(
      collisionBoundCell(
        withG2({ observed: 0, upper_bound_95: 0.1 }, { n_distinct_episodes: undefined }),
      ),
    ).toEqual({ kind: "unknown" });
  });

  it("falls back to the candidate's own distinct count", () => {
    /* Same quantity by another route — unlike `n_runs`, which is the
       row count and is never an acceptable substitute. */
    expect(
      collisionBoundCell(withG2({ observed: 0, upper_bound_95: 0.1, n_runs: 100 })),
    ).toEqual({ kind: "bound", bound: 0.1, observed: 0, distinct: 30 });
  });
});
