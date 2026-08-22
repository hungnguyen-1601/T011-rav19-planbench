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

import { readFileSync } from "node:fs";
import { join } from "node:path";

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

describe("which cell is marked as leading", () => {
  it("marks the better side and says so in words too", () => {
    const html = renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[
          candidate({ candidate_id: "a", pooled_p99_latency_ms: 7.85 }),
          candidate({ candidate_id: "b", pooled_p99_latency_ms: 17.2 }),
        ]}
      />,
    );
    /* Lower latency leads. The mark is a class plus a phrase — never a
       colour on its own, which a greyscale screenshot or a colourblind
       reader would lose entirely. */
    const cells = [...html.matchAll(/<td class="(comparison-cell comparison-value[^"]*)">(.*?)<\/td>/g)];
    const leading = cells.filter(([, cls]) => cls.includes("is-best"));
    expect(leading.length).toBeGreaterThan(0);
    for (const [, , inner] of leading) expect(inner).toContain("(leads)");
  });

  it("marks nobody on a row with no direction", () => {
    /* Replans is evidence, not a score: it is already charged in travel
       time and in latency, and marking a winner would price it twice. */
    const html = renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[
          candidate({ candidate_id: "a", replan_count: 30 }),
          candidate({ candidate_id: "b", replan_count: 242 }),
        ]}
      />,
    );
    const replanRow = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Replans across the run"))!;
    expect(replanRow).toBeTruthy();
    expect(replanRow).not.toContain("is-best");
  });
});

describe("the collision bound carries the sample it rests on", () => {
  /** The collision-bound row's two cells, as text. */
  const boundRow = (g2a: Record<string, unknown> | null, g2b: Record<string, unknown> | null) => {
    const html = renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[
          candidate({ candidate_id: "a", gates: (g2a ? { G2: g2a } : {}) as RunCandidate["gates"] }),
          candidate({ candidate_id: "b", gates: (g2b ? { G2: g2b } : {}) as RunCandidate["gates"] }),
        ]}
      />,
    );
    const row = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Collision probability"))!;
    return row.replace(/<[^>]+>/g, "|");
  };

  it("prints the denominator beside the bound, out of the tooltip", () => {
    /* Run 5753d464c9f6. `≤ 10.0 %` alone reads as a measurement of the
       robot; it is `3/N`, so a lower number means a bigger sample. */
    const row = boundRow(
      { observed: 0, upper_bound_95: 0.1, n_runs: 30, n_distinct_episodes: 30 },
      { observed: 0, upper_bound_95: 0.1, n_runs: 30, n_distinct_episodes: 30 },
    );
    expect(row).toContain("≤ 10.0");
    expect(row).toContain("0 / 30 distinct episodes");
    /* And the clause that is true of the whole row sits in the label. */
    expect(row).toContain("rule of three");
  });

  it("counts distinct episodes, never the row count", () => {
    /* Run 98f6cdb257e7: 30 rows, one distinct episode, bound 3.0. Saying
       `0 / 30` here claims thirty independent samples where there was
       one — the gate's own comment names this as the mistake that
       produced a card claiming 3.0% off a single replayed episode. */
    const row = boundRow(
      { observed: 0, upper_bound_95: 3.0, n_runs: 30, n_distinct_episodes: 1 },
      { observed: 0, upper_bound_95: 3.0, n_runs: 30, n_distinct_episodes: 1 },
    );
    expect(row).toContain("0 / 1 distinct episodes");
    expect(row).not.toContain("/ 30 distinct");
    /* Unclamped: `3/1` is 300%, and the denominator beside it is what
       makes that legible rather than a rendering fault. */
    expect(row).toContain("≤ 300.0");
  });

  it("says the rule does not apply once a collision was seen", () => {
    /* Run cb323e9d542b. Neither `≤` — there is no bound to quote — nor
       "not measured", which would be false. */
    const row = boundRow(
      { observed: 0, upper_bound_95: 0.1, n_distinct_episodes: 30 },
      { observed: 34, upper_bound_95: null, n_runs: 245, n_distinct_episodes: 85 },
    );
    expect(row).toContain("not applicable");
    expect(row).toContain("34 collisions / 85 distinct episodes");
    expect(row).not.toContain("not measured");
  });

  it("still says nothing when the run has no G2 payload", () => {
    const row = boundRow(null, null);
    expect(row).toContain("not measured");
    expect(row).not.toContain("not applicable");
  });
});

describe("an absent value says so in words", () => {
  it("puts no em dash in any value cell, on any shape of run", () => {
    /* The acceptance for this: `—` served both "the run did not record
       it" and, to a hurried reader, "zero". They are opposite readings.
       The words are also translated and searchable, which a glyph is
       not. Checked across a full candidate and an empty one, since the
       dash used to appear only on the empty side. */
    for (const field of [
      [candidate({ candidate_id: "a" }), candidate({ candidate_id: "b" })],
      [
        candidate({ candidate_id: "a" }),
        candidate({ candidate_id: "b", gates: {}, episodes: undefined, replan_count: undefined } as Partial<RunCandidate>),
      ],
      [candidate({ candidate_id: "a", gates: {}, episodes: undefined } as Partial<RunCandidate>)],
    ]) {
      const html = renderToStaticMarkup(
        <ComparisonGrid run={run} candidates={field as RunCandidate[]} />,
      );
      const cells = [...html.matchAll(/<td class="comparison-cell comparison-value[^"]*">(.*?)<\/td>/g)];
      expect(cells.length).toBeGreaterThan(0);
      for (const [, inner] of cells) expect(inner).not.toContain("—");
    }
  });

  it("keeps a measured zero reading as zero", () => {
    /* The other half. A test that only forbids the dash would pass on a
       page that had quietly turned every zero into "not measured". */
    const html = renderToStaticMarkup(
      <ComparisonGrid run={run} candidates={[candidate({ candidate_id: "a" }), candidate({ candidate_id: "b" })]} />,
    );
    const collisions = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Collisions observed"))!;
    expect(collisions).toContain('<span class="num">0</span>');
    expect(collisions).not.toContain("not measured");
  });
});

describe("a caveat sits with the number it qualifies", () => {
  const withWarning = () =>
    renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[candidate({ candidate_id: "a" }), candidate({ candidate_id: "b" })]}
        hostWarning={<span className="comparison-host-warning">unpinned host</span>}
      />,
    );

  it("lands in the latency row and in no other", () => {
    /* G4 reads wall-clock latency, so an unpinned machine muddies p99
       and leaves worst clearance, success rate and memory exactly as
       trustworthy as before. As a banner over the table it claimed all
       of them. */
    const rows = [...withWarning().matchAll(/<tr>(.*?)<\/tr>/gs)].map(([, inner]) => inner);
    const carrying = rows.filter((inner) => inner.includes("unpinned host"));
    expect(carrying).toHaveLength(1);
    expect(carrying[0]).toContain("Planner latency, pooled p99");
  });

  it("sits in the label cell, not in a value cell", () => {
    /* It qualifies the row, not one candidate's figure. */
    const latency = [...withWarning().matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("unpinned host"))!;
    const label = latency.slice(0, latency.indexOf("</th>"));
    expect(label).toContain("unpinned host");
  });

  it("draws nothing at all when the host was pinned", () => {
    /* No empty wrapper left behind: a caveat with no text is a caveat
       the reader looks for and does not find. */
    const html = renderToStaticMarkup(
      <ComparisonGrid run={run} candidates={[candidate({ candidate_id: "a" })]} />,
    );
    expect(html).not.toContain("comparison-host-warning");
  });
});

describe("the sentence above the table", () => {
  it("counts the marks the table actually made", () => {
    /* Real run 20750b0d9dbe: astar+dwa leads success rate and latency,
       rrtstar+dwa leads nothing, and the rows both sides recorded
       identically are ties. The sentence must not disagree with the
       cells directly under it. */
    const html = renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[
          candidate({ candidate_id: "a", stack_label: "astar+dwa", success_rate: 1, pooled_p99_latency_ms: 7.85 }),
          candidate({ candidate_id: "b", stack_label: "rrtstar+dwa", success_rate: 0.633, pooled_p99_latency_ms: 17.2 }),
        ]}
      />,
    );
    const sentence = html.slice(
      html.indexOf('class="comparison-summary"'),
      html.indexOf("</p>"),
    );
    const tinted = (html.match(/is-best/g) ?? []).length;
    const claimed = [...sentence.matchAll(/leads on (\d+)|on (\d+)$|, \w[\w+]* on (\d+)/g)];
    expect(sentence).toContain("astar+dwa leads on");
    expect(sentence).toContain("rrtstar+dwa on");
    /* The two win counts in the sentence sum to the tinted cells. */
    const numbers = [...sentence.matchAll(/on (\d+)/g)].map((m) => Number(m[1]));
    expect(numbers.length).toBeGreaterThanOrEqual(2);
    expect(numbers[0] + numbers[1]).toBe(tinted);
    expect(claimed.length).toBeGreaterThan(0);
  });

  it("drops the tie clause when nothing tied", () => {
    /* Rather than making "0 tied" read in two languages. */
    const html = renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[
          candidate({ candidate_id: "a", gates: {}, episodes: undefined } as Partial<RunCandidate>),
          candidate({ candidate_id: "b", gates: {}, episodes: undefined, success_rate: 0.5 } as Partial<RunCandidate>),
        ] as RunCandidate[]}
      />,
    );
    expect(html).not.toContain("0 tied");
  });

  it("writes no sentence for a field it cannot describe", () => {
    /* One candidate, and three: "A leads on four, B on two" has no room
       for C. */
    for (const field of [
      [candidate({ candidate_id: "a" })],
      [candidate({ candidate_id: "a" }), candidate({ candidate_id: "b" }), candidate({ candidate_id: "c" })],
    ]) {
      const html = renderToStaticMarkup(<ComparisonGrid run={run} candidates={field} />);
      expect(html, `${field.length} candidates`).not.toContain("comparison-summary");
    }
  });
});

describe("when both candidates name to the same words", () => {
  it("falls back to the letters", () => {
    /* Neither the stack nor the config differs — a run measuring a
       configuration against itself, which is a real thing to check
       (run-to-run variance). The sentence would otherwise read
       "astar+dwa leads on 2, astar+dwa on 0". */
    const html = renderToStaticMarkup(
      <ComparisonGrid
        run={run}
        candidates={[
          candidate({ candidate_id: "a", success_rate: 1 }),
          candidate({ candidate_id: "b", success_rate: 0.9 }),
        ]}
      />,
    );
    const sentence = html.slice(
      html.indexOf('class="comparison-summary"'),
      html.indexOf("</p>"),
    );
    expect(sentence).toContain("Candidate A leads on");
    expect(sentence).toContain("Candidate B on");
    expect(sentence).not.toContain("astar+dwa leads on");
  });
});

describe("the table is still a table", () => {
  /* The bug this guards: `.comparison-grid-head` and `.comparison-value`
     kept `display: grid` from when they were `<div>`s in a CSS grid.
     A table cell given a non-table display **stops being a cell**, and
     the browser wraps every consecutive non-cell child of a row into one
     anonymous cell — so both candidates rendered stacked inside a single
     column. Nothing threw, every markup assertion still passed, and the
     page looked like a two-column layout that had lost its second
     candidate. Only a screenshot showed it. */
  const SHEET = readFileSync(
    join(process.cwd(), "src", "app", "globals.css"),
    "utf8",
  ).replace(/\r\n/g, "\n");
  const CELL_CLASSES = [
    "comparison-cell",
    "comparison-gutter",
    "comparison-grid-head",
    "comparison-value",
    "comparison-delta",
  ];

  it("gives no cell class a display of its own", () => {
    const code = SHEET.replace(/\/\*[\s\S]*?\*\//g, "");
    const offenders: string[] = [];
    for (const [, selectors, body] of code.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const display = /(?<![-\w])display: *([\w-]+)/.exec(body)?.[1];
      if (!display || display === "table-cell" || display === "none") continue;
      for (const selector of selectors.split(",")) {
        const last = selector.trim().split(/\s+/).pop() ?? "";
        if (CELL_CLASSES.some((c) => last === `.${c}` || last.startsWith(`.${c}.`) || last.startsWith(`.${c}:`))) {
          offenders.push(`${selector.trim()} → ${display}`);
        }
      }
    }
    expect(offenders, offenders.join(" | ")).toEqual([]);
  });

  it("puts every candidate's value in its own cell of the row", () => {
    /* The rendered proof, not just the stylesheet's word for it: each
       metric row must hold one value cell per candidate. Two candidates
       collapsing into one cell is what the reader actually saw. */
    const html = draw(pair());
    const bodyRows = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .filter((inner) => inner.includes("comparison-value"));
    expect(bodyRows.length).toBeGreaterThan(5);
    for (const inner of bodyRows) {
      expect((inner.match(/<td class="comparison-cell comparison-value/g) ?? []).length).toBe(2);
    }
  });

  it("keeps the head's own layout off the header cell", () => {
    /* The wrapper the grid moved onto. Without it the two column heads
       stack, which is the same failure one row higher. */
    const html = draw(pair());
    expect((html.match(/class="head-inner"/g) ?? []).length).toBe(2);
    expect(html).toContain('<span class="value-figure">');
  });
});

describe("green for ahead, red for behind", () => {
  it("colours the two sides of a decided row differently", () => {
    const html = draw(pair());
    const success = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Success rate"))!;
    expect(success).toContain("is-best");
    expect(success).toContain("is-worst");
    expect(success).toContain("(leads)");
    expect(success).toContain("(trails)");
  });

  it("colours neither side of a tie", () => {
    /* Both candidates recorded 30 distinct episodes. A tie has no
       loser, and red there would invent a result. */
    const tied = [...draw(pair()).matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Distinct episodes"))!;
    expect(tied).not.toContain("is-best");
    expect(tied).not.toContain("is-worst");
  });

  it("colours neither side when one recorded nothing", () => {
    /* The candidate did not lose the comparison — there was none. */
    const [first, second] = pair();
    const html = draw([first, { ...second, gates: {} } as RunCandidate]);
    const bound = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Collision probability"))!;
    expect(bound).not.toContain("is-worst");
  });

  it("colours neither side on the row that marks nobody", () => {
    /* Replans is evidence, not a score. */
    const html = draw([
      candidate({ candidate_id: "a", replan_count: 30 }),
      candidate({ candidate_id: "b", replan_count: 242 }),
    ]);
    const replans = [...html.matchAll(/<tr>(.*?)<\/tr>/gs)]
      .map(([, inner]) => inner)
      .find((inner) => inner.includes("Replans across the run"))!;
    expect(replans).not.toContain("is-best");
    expect(replans).not.toContain("is-worst");
  });
});
