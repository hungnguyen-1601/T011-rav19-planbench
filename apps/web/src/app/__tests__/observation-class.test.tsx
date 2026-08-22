/** What each candidate was allowed to see — moved, not dropped.
 *
 * These claims used to live in `leaderboard-observation.test.tsx`,
 * against `/leaderboard` and `/algorithms`. Both pages retired in P6, but
 * the property they guarded is not a property of those pages: **a
 * comparison between candidates shown different things is measuring the
 * difference in what they were shown.** A controller reading the static
 * map and one reading only its LiDAR are answering different questions,
 * so ΔU between them prices the privilege as much as the planner — and
 * the Decision Card would name a winner on that basis.
 *
 * So the declaration follows the flow that replaced those pages:
 * `/candidates` states it before anybody runs anything, and
 * `/decisions/[id]` states it beside the numbers it qualifies.
 *
 * **Every registry entry declares the same pair today**, so the warning
 * never renders. That is the reason to write it now rather than later:
 * the first entry that does not match would otherwise turn an unlike
 * comparison into one that looks like a like one, with nothing on screen
 * and nothing in the export to catch it.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { observationClasses } from "../../lib/decisions";
import type { RunCandidate } from "../../lib/decisions";

const APP = join(process.cwd(), "src", "app");
const CANDIDATES = readFileSync(join(APP, "candidates", "page.tsx"), "utf8");
const DETAIL = readFileSync(join(APP, "decisions", "[id]", "page.tsx"), "utf8");
/* The comparison table, extracted so tests can render it — a
   function declared inside a fetching page cannot be imported. */
const GRID = readFileSync(
  join(process.cwd(), "src", "components", "ComparisonGrid.tsx"),
  "utf8",
);
const EN = en as Record<string, string>;

function candidate(local: string | null): RunCandidate {
  return { local_observation_class: local } as unknown as RunCandidate;
}

describe("the declaration is made before a run, not after", () => {
  it("the candidates page prints both classes", () => {
    /* This is where a stack is chosen, so it is where "what does this
       one get to see" has to be answerable. `/algorithms` was the only
       page that said it; it retired into this one. */
    expect(CANDIDATES).toContain("stack.global_observation_class");
    expect(CANDIDATES).toContain("stack.local_observation_class");
    expect(en).toHaveProperty("candidates.stacks.observation");
    expect(vi).toHaveProperty("candidates.stacks.observation");
  });
});

describe("the report says what each candidate was shown", () => {
  it("carries the class from the registry into the run", () => {
    /* Recorded at run time rather than looked up when the page renders:
       the registry can change, and a stored run has to keep describing
       the comparison that actually happened (HĐ-13). */
    const selection = readFileSync(
      join(process.cwd(), "..", "..", "packages", "benchmark", "planbench_benchmark", "selection.py"),
      "utf8",
    );
    expect(selection).toContain('"local_observation_class"');
    expect(selection).toContain("def _observation_classes(");
  });

  it("renders a column, and names the gap when nobody declared one", () => {
    /* A blank cell reads as "same as the rest", which is the one thing
       an undeclared stack cannot be shown to be. */
    // It was a column of the gate table. That table is gone, so the
    // fact moved onto each candidate card — it had to move rather
    // than go, because `ObservationNotice` fires only when the
    // classes *differ*, and a lone undeclared stack raises no
    // warning at all.
    // It was a column of the gate table, then a badge on the card,
    // and is now a row of the comparison grid. It had to keep
    // moving rather than go, because `ObservationNotice` fires only
    // when the classes *differ* — a lone undeclared stack raises no
    // warning at all.
    expect(GRID).toContain("candidate.local_observation_class ?");
    expect(GRID).toContain("decisions.gates.observationUnknown");
    expect(GRID).toContain("comparison-flags");
    expect(EN["decisions.gates.observationUnknownNote"]).toContain("cannot be shown");
  });
});

describe("mixing classes is a finding, and it is never silent", () => {
  it("says nothing when the field saw the same world", () => {
    expect(observationClasses([candidate("lidar_only"), candidate("lidar_only")])).toHaveLength(1);
  });

  it("counts undeclared as its own class rather than dropping it", () => {
    /* A stack whose inputs nobody wrote down cannot be shown to match
       the others, so silence must not fold into whatever the rest
       declared. */
    expect(observationClasses([candidate("lidar_only"), candidate(null)])).toEqual([
      "lidar_only",
      null,
    ]);
  });

  it("warns above the cards, where the numbers are", () => {
    // It used to sit above the gate table. That table is gone, so
    // the warning moved to the top of the comparison — it is a
    // finding about the whole run, and leaving it to be deleted
    // along with the section it happened to live in would have been
    // the quiet way to lose it.
    /* The grid moved into its own component, so the ordering claim is
       now about the panel that wraps it. */
    const comparison = DETAIL.slice(DETAIL.indexOf("function CandidateComparison("));
    expect(comparison).toContain("<ObservationNotice");
    expect(comparison.indexOf("<ObservationNotice")).toBeLessThan(
      comparison.indexOf("<ComparisonGrid"),
    );
  });

  it("explains what the mixture does to ΔU rather than only flagging it", () => {
    /* "Mixed observation classes" alone invites the question "so what".
       The answer is the whole point: the ranking is partly measuring the
       privilege. */
    expect(EN["decisions.gates.mixedObservation"]).toContain("ΔU");
    expect((vi as Record<string, string>)["decisions.gates.mixedObservation"]).toContain("ΔU");
  });

  it("states the fact and does not refuse the run", () => {
    /* Hiding a comparison the platform agreed to perform would be this
       component overruling the reader, who is the one who knows whether
       the difference was deliberate. */
    const notice = DETAIL.slice(
      DETAIL.indexOf("function ObservationNotice"),
      DETAIL.indexOf("function CandidateRow"),
    );
    expect(notice).toContain("classes.length < 2");
    expect(notice).not.toContain("return null;\n  }\n  throw");
  });
});

describe("the exported document carries it too", () => {
  it("has the column and the warning", () => {
    /* On paper this matters more than on screen: the reader cannot ask
       a follow-up question of a Markdown file. */
    // Both documents, not just the Markdown: the finding moved to
    // `decision_export` when Excel arrived, and a caveat that travels
    // with only one of two files stops travelling the moment somebody
    // prefers the other.
    const shared = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "decision_export.py"),
      "utf8",
    );
    const workbook = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "decision_xlsx.py"),
      "utf8",
    );
    const texts = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "decision_text.py"),
      "utf8",
    );
    // The column header is a word, and words moved to the text table
    // when the export became bilingual — the column itself is still
    // declared beside the rows it heads.
    expect(texts).toContain('"en": "Shown"');
    expect(shared).toContain('"column.gate.shown"');
    expect(shared).toContain("def mixed_observation(");
    expect(workbook).toContain("mixed_observation");
  });
});
