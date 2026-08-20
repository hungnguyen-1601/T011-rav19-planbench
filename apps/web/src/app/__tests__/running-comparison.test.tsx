/** The running-comparison panel, checked the way this repository can.
 *
 * No jsdom here, so the component cannot be driven through its states.
 * The decisions it makes — direction, clock, which rung — live in
 * `lib/running.ts` and are tested directly there. What is left, and what
 * this file guards, is the part that is still wrong when the markup is
 * perfect: the panel is mounted where it can read the slider it depends
 * on, every key it names exists in both locales, and the composite is
 * never rendered without the sentence saying it is not ΔU.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { PROGRESS_CLOCK, TIME_CLOCK } from "@/lib/running";

const SRC = join(process.cwd(), "src");
const PANEL = readFileSync(join(SRC, "components", "RunningComparison.tsx"), "utf8");
const SYNC = readFileSync(join(SRC, "components", "ProgressSync.tsx"), "utf8");
const CSS = readFileSync(join(SRC, "app", "globals.css"), "utf8");
const VIEWER = readFileSync(join(SRC, "components", "TraceViewer.tsx"), "utf8");
const DETAIL = readFileSync(join(SRC, "app", "decisions", "[id]", "page.tsx"), "utf8");

describe("where the panel sits", () => {
  it("is mounted inside the progress-synced panel, not beside it", () => {
    // The rung it shows is chosen by a scrub position measured in
    // metres of progress. Mounted anywhere else it would need a second
    // copy of that position, and two positions are two positions that
    // can disagree.
    expect(SYNC).toContain("<RunningComparison");
    expect(SYNC).toContain("progress={scan.time}");
  });

  it("is fed the view's own pair, not the page's first two candidates", () => {
    // The replay was aligned for a specific pair; labelling the columns
    // from a different one would put the right numbers under the wrong
    // names.
    expect(SYNC).toContain("candidateA={view.candidate_a}");
    expect(SYNC).toContain("candidateB={view.candidate_b}");
  });
});

describe("what the panel refuses to blur", () => {
  it("tells 'could not be computed' apart from 'no difference'", () => {
    // The server sends null, never []. An empty table would render as a
    // panel with no differences in it, which reads as the two runs
    // being identical.
    expect(PANEL).toContain("running === null");
    expect(PANEL).toContain("running.none");
  });

  it("says so when neither run has reached the first rung", () => {
    expect(PANEL).toContain("running.before");
  });

  it("never prints the composite without its caveat", () => {
    // The one number on this panel that a reader will mistake for ΔU.
    expect(PANEL).toContain("partial_advantage");
    expect(PANEL).toContain("compositeCaveat(point)");
  });

  it("names which objectives went into the composite", () => {
    expect(PANEL).toContain("partial_objectives");
  });

  it("draws the two clocks as two tables", () => {
    // One eight-row block would invite reading a worst-clearance and a
    // progress fraction as answers to the same question.
    expect(PANEL).toContain("PROGRESS_CLOCK");
    expect(PANEL).toContain("TIME_CLOCK");
    expect(PANEL.match(/<ClockTable/g)?.length).toBe(2);
  });

  it("says when a number came from the choice of ruler, not from driving", () => {
    // On a run with no recorded plan, one candidate's own path is the
    // reference, and its path_efficiency is 1.000 by construction.
    expect(PANEL).toContain("isRulerArtefact");
    expect(PANEL).toContain("running.rulerArtefact");
    expect(SYNC).toContain("referenceSource={view.reference_source_candidate_id}");
  });

  it("states the lead in text as well as in colour", () => {
    expect(PANEL).toContain("sr-only");
    expect(CSS).toContain(".sr-only");
  });
});

describe("translation keys", () => {
  const literal = [...PANEL.matchAll(/t\(\s*"(running\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);
  // Built at runtime from the metric key and from the objective count,
  // so no static scan of the source would catch a missing one.
  const metrics = [...PROGRESS_CLOCK, ...TIME_CLOCK].map(
    (row) => `running.metric.${String(row.key)}`,
  );
  const caveats = [
    "running.composite.partial",
    "running.composite.full",
    "running.rulerArtefact",
  ];

  it("names at least the blocks this panel is made of", () => {
    expect(new Set(literal).size).toBeGreaterThan(6);
  });

  it.each([...new Set([...literal, ...metrics, ...caveats])])(
    "%s exists in both locales",
    (key) => {
      // A missing key renders as the key itself, which reads as broken
      // data rather than as a missing translation.
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    },
  );

  it("has a label for every metric on both clocks", () => {
    // Guards the pair rather than the list: adding a metric to
    // `lib/running.ts` without a label would otherwise ship a row
    // headed `running.metric.whatever`.
    expect(metrics.length).toBe(8);
  });
});

describe("the dynamic tiles under each canvas", () => {
  it("is fetched whichever way the two replays are aligned", () => {
    // The defect this guards: the sync request was made only in
    // progress mode, so the tiles — which do not depend on how the
    // panels are paired — appeared only behind a toggle a reader had no
    // reason to press. The page opens in time mode.
    const effect = DETAIL.slice(DETAIL.indexOf("getReplaySync"));
    expect(DETAIL).not.toContain('if (syncMode !== "progress" || !episodeId');
    expect(effect).toBeTruthy();
    expect(DETAIL).toContain("if (!episodeId || candidates.length < 2) return;");
  });

  it("reads the row the pose is drawn from, not a clock of its own", () => {
    // A series on its own time grid would drift against the scrubber,
    // and the drift would look like the metric moving.
    expect(VIEWER).toContain("running?.[visibleStep] ?? null");
  });

  it("takes each candidate's own series, not the pair's ladder", () => {
    expect(DETAIL).toContain("view?.running?.by_step[side] ?? null");
  });

  it("puts what is true now above the episode's totals", () => {
    // The static table below already reports min clearance and travel
    // time for the whole run. A cumulative tile mixed into it would
    // read as another total.
    const progress = VIEWER.indexOf("trace.running.progress");
    const duration = VIEWER.indexOf("trace.duration");
    expect(progress).toBeGreaterThan(-1);
    expect(duration).toBeGreaterThan(progress);
  });

  it("draws no dynamic tiles at all when the series is absent", () => {
    // A run whose anchors will not resolve, and the standalone viewer,
    // which has no pair and so no shared reference line. Absent beats a
    // row of dashes that look like measurements that came out empty.
    expect(VIEWER).toContain("{live ? (");
  });

  it("carries the ruler caveat onto the tile as well as into the table", () => {
    // path_efficiency is 1.000 by construction for whichever candidate
    // supplied the reference line. The tile is the more prominent of
    // the two places it appears.
    expect(VIEWER).toContain("isReferenceRuler");
    expect(VIEWER).toContain("running.rulerArtefact");
    expect(DETAIL).toContain(
      "isReferenceRuler={view?.reference_source_candidate_id === candidate.candidate_id}",
    );
  });
});

describe("tile translation keys", () => {
  const keys = [...VIEWER.matchAll(/t\(\s*"(trace\.running\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);

  it("names a label for every dynamic tile", () => {
    expect(new Set(keys).size).toBe(5);
  });

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});
