/** The reading of the comparison table.
 *
 * Four rules, and the two ways a reading goes wrong: claiming a
 * trade-off where one candidate simply leads everything, and staying
 * silent where it does.
 */

import { describe, expect, it } from "vitest";

import type { MetricRow } from "@/lib/candidateMetrics";
import { tradeoffs } from "@/lib/tradeoffs";

const row = (
  key: string,
  direction: MetricRow["direction"],
  values: (number | null)[],
  threshold?: string,
): MetricRow => ({
  key,
  direction,
  values,
  numberText: values.map((value) => (value === null ? null : String(value))),
  threshold,
});

describe("what the table amounts to", () => {
  it("names a trade-off with the counts on both sides", () => {
    /* "A is more accurate but B is faster" is a shape, not a finding —
       the reader cannot check it and it stays true-sounding after the
       data changes underneath it. */
    const found = tradeoffs(
      [
        row("successRate", "higher", [1, 0.6]),
        row("worstClearance", "higher", [0.47, 0.13]),
        row("p99", "lower", [17.2, 7.85]),
        row("memory", "lower", [8.1, 8.0]),
      ],
      2,
    );
    expect(found[0].kind).toBe("tradeoff");
    expect(found[0].side).toBe(0);
    expect(found[0].vars).toMatchObject({ achieved: "2", spent: "2" });
    expect(found[0].metrics).toContain("p99");
  });

  it("says out loud that there is no trade-off when one side leads everything", () => {
    /* Rendering nothing here leaves the reader to work out for
       themselves whether the table is one-sided or they misread it. */
    const found = tradeoffs(
      [
        row("successRate", "higher", [1, 0.633]),
        row("worstClearance", "higher", [0.47, 0.133]),
        row("p99", "lower", [7.85, 17.2]),
        row("medianTravel", "lower", [22.5, 40]),
      ],
      2,
    );
    expect(found[0].kind).toBe("sweep");
    expect(found[0].side).toBe(0);
    expect(found[0].vars).toMatchObject({ won: "4", total: "4" });
  });

  it("never calls a sweep a trade-off", () => {
    /* The failure that matters: a reader told to weigh a trade-off that
       does not exist will go looking for the half they are missing. */
    const found = tradeoffs(
      [row("successRate", "higher", [1, 0.6]), row("p99", "lower", [7, 17])],
      2,
    );
    expect(found.map((entry) => entry.kind)).not.toContain("tradeoff");
  });

  it("reports how narrow the reading is when rows went unmeasured", () => {
    /* A comparison resting on two rows where the reader can see four is
       a narrower claim than it looks. */
    const found = tradeoffs(
      [
        row("successRate", "higher", [1, 0.6]),
        row("p99", "lower", [7, 17]),
        row("noPathRate", "lower", [null, 0.1]),
        row("memory", "lower", [8, null]),
      ],
      2,
    );
    const narrow = found.find((entry) => entry.kind === "unmeasured")!;
    expect(narrow.vars).toMatchObject({ count: "2", scored: "2" });
  });

  it("counts a directionless row as neither compared nor missing", () => {
    /* `replans` is evidence, not a score. Counting it as unmeasured
       would report a gap the run does not have. */
    const found = tradeoffs(
      [row("successRate", "higher", [1, 0.6]), row("replans", "none", [30, 242])],
      2,
    );
    expect(found.find((entry) => entry.kind === "unmeasured")).toBeUndefined();
  });

  it("flags a row that came out level against a declared limit", () => {
    /* Winning a metric and clearing its budget are different facts, and
       the delta column shows only the first. */
    const found = tradeoffs([row("memory", "lower", [8, 8], "3277")], 2);
    expect(found.find((entry) => entry.kind === "atLimit")!.vars).toMatchObject({ count: "1" });
  });

  it("says nothing about a run with one candidate", () => {
    /* Every sentence here is comparative. */
    expect(tradeoffs([row("successRate", "higher", [1])], 1)).toEqual([]);
  });

  it("stops at five, because a longer list stops being read", () => {
    const many = Array.from({ length: 12 }, (_, index) =>
      row(`m${index}`, "lower", [1, 2], "3"),
    );
    expect(tradeoffs(many, 2).length).toBeLessThanOrEqual(5);
  });
});
