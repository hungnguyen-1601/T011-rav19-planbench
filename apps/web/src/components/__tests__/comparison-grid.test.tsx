/** The comparison table, rendered.
 *
 * This is the file the extraction was for. `renderToStaticMarkup` gives
 * real HTML with no browser, which covers first render — and first
 * render is where every claim below lives. What it cannot cover is
 * clicking, which this table does not do (`docs/KNOWN_LIMITATIONS.md`).
 *
 * `useTranslation` reads a context with a default, so no provider is
 * needed: the markup comes out in English.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ComparisonGrid } from "@/components/ComparisonGrid";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";

const candidate = (over: Partial<RunCandidate> = {}): RunCandidate =>
  ({
    candidate_id: "a",
    stack_label: "astar+dwa",
    local_controller_config: "dwa_coarse",
    local_observation_class: "lidar_only",
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 7.85,
    replan_count: 30,
    cleared_gates: true,
    blocking_gates: [],
    gates: {
      G1: { result: "pass", no_path_rate: 0 },
      G2: { result: "pass", observed: 0, upper_bound_95: 0.1, n_distinct_episodes: 30 },
      G5: { result: "pass", memory_estimate_mb: 8 },
    },
    episodes: [
      { episode_context_id: "e1", success: true, min_clearance: 0.47, travel_time_s: 22.5 },
    ],
    ...over,
  }) as unknown as RunCandidate;

const run = { id: "r", recommended_candidate_id: null } as unknown as DecisionRun;

const draw = (candidates: RunCandidate[]) =>
  renderToStaticMarkup(<ComparisonGrid run={run} candidates={candidates} />);

const pair = () => [
  candidate({ candidate_id: "a", stack_label: "astar+dwa" }),
  candidate({ candidate_id: "b", stack_label: "rrtstar+dwa", success_rate: 0.633 }),
];

/** Cells in one `<tr>`, so a claim about a row is a claim about a row. */
function rows(html: string): number[] {
  return [...html.matchAll(/<tr>(.*?)<\/tr>/gs)].map(
    (match) => (match[1].match(/<t[hd][\s>]/g) ?? []).length,
  );
}

describe("every row is a row", () => {
  it("gives each row the same number of cells, flags row included", () => {
    /* The whole reason this is a table. In the flat grid it replaced, a
       flags row that emitted one cell fewer pulled every cell after it
       one column left — and the flags row only appears when a candidate
       carries a finding, so the page mis-columned itself exactly when it
       had something to report. */
    const [first, second] = pair();
    const html = draw([first, { ...second, stopped_early: { episodes_run: 12, episodes_planned: 30, gate: "G3", rule: "doomed" } } as RunCandidate]);
    const counts = rows(html);
    expect(counts.length).toBeGreaterThan(2);
    expect(new Set(counts).size, `row widths: ${counts.join(", ")}`).toBe(1);
  });

  it("keeps that true with no flags row at all", () => {
    const counts = rows(draw(pair()));
    expect(new Set(counts).size, `row widths: ${counts.join(", ")}`).toBe(1);
  });

  it("draws no flags row when nothing is flagged", () => {
    expect(draw(pair())).not.toContain("comparison-flags");
  });
});

describe("the Δ column", () => {
  it("appears for exactly two candidates", () => {
    const html = draw(pair());
    expect(html).toContain("Δ (B−A)");
    /* Success 100.0% against 63.3%: a rate gap is percentage points, not
       a proportion of a proportion. */
    expect(html).toContain("−36.7 pp");
  });

  it("is absent for one candidate and for three", () => {
    for (const field of [[candidate()], [candidate({ candidate_id: "a" }), candidate({ candidate_id: "b" }), candidate({ candidate_id: "c" })]]) {
      const html = draw(field);
      expect(html, `${field.length} candidates`).not.toContain("Δ (B−A)");
      expect(html, `${field.length} candidates`).not.toContain("comparison-delta");
      expect(new Set(rows(html)).size).toBe(1);
    }
  });
});

describe("what a cell says when the run recorded nothing", () => {
  it("says so in words rather than with a dash", () => {
    /* `—` for "not recorded" and `0` for "measured zero" are opposite
       readings, and the old grid drew the same glyph for both. */
    const blind = pair().map((c) => ({ ...c, gates: {} }) as RunCandidate);
    const html = draw(blind);
    expect(html).toContain("not measured");
    /* Scoped to the value cells: the hint tooltips are prose and use em
       dashes legitimately. The claim is about what a *number* column
       shows, not about the page's punctuation. */
    const cells = [...html.matchAll(/<td class="comparison-cell comparison-value[^"]*">(.*?)<\/td>/g)];
    expect(cells.length).toBeGreaterThan(4);
    for (const [, inner] of cells) expect(inner).not.toContain("—");
  });

  it("leaves the Δ cell empty rather than claiming a difference of zero", () => {
    const [first, second] = pair();
    const html = draw([first, { ...second, gates: {} } as RunCandidate]);
    expect(html).toContain('<td class="comparison-delta"></td>');
  });
});

describe("the column heads", () => {
  it("names the field that differs, and never the same words twice", () => {
    const heads = [...draw(pair()).matchAll(/<h4>(.*?)<\/h4>/g)].map((m) => m[1]);
    expect(heads).toEqual(["astar+dwa", "rrtstar+dwa"]);
  });

  it("names the config when the stacks match", () => {
    const html = draw([
      candidate({ candidate_id: "a", local_controller_config: "dwa_coarse" }),
      candidate({ candidate_id: "b", local_controller_config: "dwa_balanced" }),
    ]);
    const heads = [...html.matchAll(/<h4>(.*?)<\/h4>/g)].map((m) => m[1]);
    expect(heads).toEqual(["dwa_coarse", "dwa_balanced"]);
  });

  it("carries each candidate's gate verdict beside its name", () => {
    const html = draw([
      candidate({ candidate_id: "a" }),
      candidate({ candidate_id: "b", cleared_gates: false, blocking_gates: ["G3"] }),
    ]);
    expect(html).toContain("G1–G6 cleared");
    expect(html).toContain("blocked at G3");
  });

  it("marks the columns for a screen reader", () => {
    expect(draw(pair())).toContain('scope="col"');
  });
});

describe("the value cells", () => {
  it("keeps the unit out of the digits", () => {
    /* Two slots, so decimal points line up down the column. Rendering
       `text` here instead would print the unit twice. */
    const html = draw(pair());
    expect(html).toContain('<span class="num">7.85</span><span class="unit">ms</span>');
    expect(html).not.toContain("ms ms");
  });

  it("renders the unit slot even for a quantity that has none", () => {
    /* Dropping it lets a unitless row's number slide right and breaks
       the column for every row above it. */
    expect(draw(pair())).toContain('<span class="num">30</span><span class="unit"></span>');
  });
});
