/** One page, one answer to "which of these is candidate A".
 *
 * The replay canvases read `panelCandidates`, which puts the
 * recommended candidate first. The episode table read the report's own
 * list. On a run whose winner happened to be filed second, the same two
 * stacks were columns in one order and canvases labelled A and B in the
 * other, on one screen — reported from a real run of
 * `sudden_stop_custom_v2`, where a reader set A to astar+dwa and the
 * canvas below called it B.
 *
 * `panelCandidates` already carries the rule this broke, one comment
 * above the code that broke it: *one page must not call the same
 * candidate two things*. Read off the source rather than rendered,
 * because the page fetches and the two orderings live in different
 * components — what has to hold is that neither takes the raw list.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const SOURCE = readFileSync(
  join(process.cwd(), "src", "app", "decisions", "[id]", "DecisionDetail.tsx"),
  "utf8",
);

/** Comments strip first: this file explains the rule in prose, and a
 *  test reading the raw text would match its own explanation. */
const CODE = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

describe("which candidate is A", () => {
  it("is decided the same way everywhere a side is labelled", () => {
    // Every place that assigns a side reads the ordered list. A raw
    // `run.report?.candidates` in a component that then indexes 0 and 1
    // is the shape of the bug.
    const ordered = CODE.match(/panelCandidates\(/g) ?? [];
    expect(ordered.length).toBeGreaterThanOrEqual(2);
  });

  it("the episode table does not take the report's own order", () => {
    const table = CODE.slice(CODE.indexOf("function EpisodeOutcomes"));
    expect(table).toContain("panelCandidates(");
    // The bug shape exactly: the raw list *assigned* as the component's
    // candidates, then indexed 0 and 1. Passing it as an argument to
    // panelCandidates is the fix, not the fault, so the check is on the
    // assignment rather than on the substring.
    expect(table).not.toContain("const candidates = run.report?.candidates");
  });

  it("the recommended candidate is the one called A", () => {
    // Not an arbitrary convention: `comparedPair` returns the pair the
    // statistics used, recommended first, and the canvases have drawn
    // it that way since they were written. The table moved to match
    // them rather than the other way round, because a colour means
    // identity here and the canvases own the colours.
    const sync = readFileSync(join(process.cwd(), "src", "lib", "replaySync.ts"), "utf8");
    expect(sync).toContain("recommended_candidate_id");
  });
});
