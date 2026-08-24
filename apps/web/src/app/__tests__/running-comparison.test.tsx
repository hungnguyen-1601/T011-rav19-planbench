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
const CHART = readFileSync(join(SRC, "components", "LatencyChart.tsx"), "utf8");
const CLIENT = readFileSync(join(SRC, "lib", "decisions.ts"), "utf8");
const VIEWER = readFileSync(join(SRC, "components", "TraceViewer.tsx"), "utf8");
const DETAIL = readFileSync(join(SRC, "app", "decisions", "[id]", "DecisionDetail.tsx"), "utf8");

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

  it("keeps the episode's totals out of the live row entirely", () => {
    // `Episode length` was the trace's last timestamp, which is the
    // scored `Travel time` read a second way; `Last event` is a fact
    // about the end of the run. Neither moves with the scrubber.
    expect(VIEWER).toContain("trace.running.progress");
    expect(VIEWER).not.toContain("trace.duration");
    expect(VIEWER).not.toContain('t("trace.outcome")');
    expect(DETAIL).toContain("t(\"trace.outcome\")");
  });

  it("keeps Last event beside Result rather than folded into it", () => {
    // `Result` is the gate's reading of the episode; `Last event` is
    // HĐ-5's own final record. They agree on most runs, which is
    // exactly why merging them would never be noticed.
    const result = DETAIL.indexOf("t(\"trace.result\")");
    const lastEvent = DETAIL.indexOf("t(\"trace.outcome\")");
    expect(result).toBeGreaterThan(-1);
    expect(lastEvent).toBeGreaterThan(result);
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

describe("one frame, one kind of number", () => {
  it("shows the live readings or the result, never both at once", () => {
    // A total sitting in a row of readings gets read as a reading; a
    // row of readings left up after the replay stops is a set of frozen
    // numbers under labels that say "now". Candidate B on a timeout
    // episode sat at "Planner latency now 7.63 ms" beside a p99 of
    // 2101 ms.
    expect(VIEWER).toContain("{showFinal ? (");
    expect(VIEWER).toContain("finalPanel");
  });

  it("hands the result panel in rather than building a second one", () => {
    // The viewer knows the trace, not how the run was graded. Deriving
    // a minimum from the clearance column here would be a second
    // implementation of a number the caller already renders.
    expect(VIEWER).not.toContain("outcome.min_clearance");
    expect(VIEWER).not.toContain("Math.min(...trace.clearance_m");
    expect(DETAIL).toContain("finalPanel={finalPanel}");
  });

  it("switches on its own when that replay runs out", () => {
    expect(VIEWER).toContain("visibleStep >= trace.x.length - 1");
  });

  it("puts the control on the panel it changes, one per candidate", () => {
    // Two changes from the first version, both from using it. It sat in
    // the toolbar three sections above the canvases, where a reader
    // watching a replay never looks — so it could not be found at all.
    // And it was shared, which forbade the case a reader actually
    // wants: reading one stack's results while the other still drives.
    expect(DETAIL).toContain("episode-candidate-actions");
    expect(DETAIL).toContain("onClick={onToggleFinal}");
    expect(DETAIL).not.toContain("episode-metrics-toggle");
  });

  it("keeps the two panels' switches independent", () => {
    expect(DETAIL).toContain('useState<{ a: boolean; b: boolean }>({ a: false, b: false })');
    expect(DETAIL).toContain("forceFinal={finalFor[side]}");
    expect(DETAIL).toContain("[side]: !current[side]");
  });

  it("names each switch after the field that tells the candidates apart", () => {
    // "Show final results" twice over is two controls a screen reader
    // cannot tell apart.
    //
    // This used to assert the *stack*, which fails its own reason on a
    // local-controller comparison: both candidates are `astar+dwa`, so
    // the reader heard the same label twice and the control it was
    // meant to disambiguate stayed ambiguous. `names.heading` is
    // whichever of stack or config actually differs on this run.
    expect(DETAIL).toContain("names.heading}`}");
    expect(DETAIL).not.toContain("candidate.stack_label}`}");
  });

  it("lets the reader go back to the live metrics", () => {
    // Otherwise asking for the results early is a one-way door, and
    // scrubbing afterwards shows a panel that ignores the scrubber.
    expect(DETAIL).toContain("!current[side]");
    expect(DETAIL).toContain("trace.metricsView.live");
  });

  it("still shows the result for a candidate whose trace would not load", () => {
    // No replay means no live row for the result to replace — and what
    // happened is still the answer. Hiding it behind a swap that has
    // nothing to swap with would lose it.
    expect(DETAIL).toContain("{ready ? null : finalPanel}");
  });
});

describe("the button's translation keys", () => {
  // Matched as string literals rather than as `t("...")` calls: the
  // button picks its label with a ternary *inside* the call, so a
  // call-shaped pattern finds only the hint and would report a missing
  // label as a passing test.
  const keys = [...DETAIL.matchAll(/"(trace\.metricsView\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);

  it("names the two labels and the explanation", () => {
    expect(new Set(keys).size).toBe(3);
  });

  it.each(["trace.metricsView.final", "trace.metricsView.live", "trace.metricsView.hint"])(
    "%s exists in both locales",
    (key) => {
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    },
  );
});

describe("tile translation keys", () => {
  const keys = [...VIEWER.matchAll(/t\(\s*"(trace\.running\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);

  it("names a label for every dynamic tile", () => {
    /* Five tile labels and one note. The note is `marginUnits`: worst
       clearance is reported in robot radii while the tile beside it and
       the comparison table both report metres, and one concept wearing
       two units on one screen with nothing saying so is a reader
       comparing 3.81 against 0.470. */
    expect(new Set(keys).size).toBe(6);
    expect(keys).toContain("trace.running.marginUnits");
  });

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});

describe("the planner-latency chart", () => {
  it("scales its time axis to its own episode, never to the pair's", () => {
    /* **This briefly did the opposite, for a reason that was real and
       not good enough.** Two charts drawn the same width read as the
       same duration, so both were put on the longer of the two episodes.
       What that broke is bigger: this chart is a seek control —
       `role="slider"`, with a playhead a reader drags — and on a shared
       axis the shorter run's playhead sat at 57% of the width while its
       robot was 90% of the way to the goal on the canvas directly above.
       A control whose thumb disagrees with the thing it controls is
       broken, and the duration a shared axis was meant to convey is
       already written on the axis label in seconds. */
    expect(CHART).not.toContain("tFloorS");
    expect(VIEWER).not.toContain("pairDurationS");
    expect(DETAIL).not.toContain("pairDurationS");
    // The end of *this* episode, stated rather than implied by width.
    expect(CHART).toContain("{plot.tMax.toFixed(1)} s");
  });

  it("sits under that candidate's metrics, one per algorithm", () => {
    // Latency is the one quantity here that a single number cannot
    // report: the tile reads "now" and the result panel reads p99, and
    // both are summaries of a shape.
    expect(VIEWER).toContain("<LatencyChart");
    const metrics = VIEWER.indexOf("{showFinal ? (");
    expect(VIEWER.indexOf("<LatencyChart")).toBeGreaterThan(metrics);
  });

  it("replaces the per-canvas colour note rather than dropping it", () => {
    // The note was rendered once per candidate — the same four
    // sentences twice, side by side — and it explains how the canvas is
    // drawn, which is one fact about the pair. Deleting it outright
    // would leave the colours unexplained.
    expect(VIEWER).not.toContain("trace.colourNote");
    expect(DETAIL).toContain("trace.colourNote");
    expect(en).toHaveProperty("trace.colourNote");
  });

  it("takes the threshold from the deployment, not from a constant", () => {
    // A deployment declaring a different control rate gets a different
    // line; a hard-coded 50 ms would quietly mis-grade it.
    expect(CHART).toContain("controlPeriodS");
    expect(VIEWER).toContain("controlPeriodS={trace.control_period_s}");
    expect(CLIENT).toContain("control_period_s: number;");
  });

  it("draws the running p99, not the episode's", () => {
    // The episode's p99 is a number from the future while the replay is
    // still playing. This one is the compute tile's own value turned
    // back into milliseconds — an exact inversion of the normalisation,
    // so the line and the tile beside it cannot disagree, and no second
    // percentile is computed anywhere.
    expect(CHART).toContain("p99Ms");
    expect(CHART).not.toContain("sort(");
    expect(VIEWER).toContain("live.compute_budget * trace.control_period_s * 1000");
    expect(DETAIL).not.toContain("p99Ms=");
  });

  it("goes away with the rest of the live readings", () => {
    // It is a live reading, not a summary: it belongs inside the branch
    // the result panel replaces, not below it. Matched as "somewhere
    // between the start of the live branch and its close" rather than
    // by line offsets, which move whenever a tile is added.
    expect(VIEWER).toMatch(/showFinal \? \([\s\S]*?<LatencyChart/);
    const live = VIEWER.indexOf('<div className="stat-grid"');
    expect(VIEWER.indexOf("<LatencyChart")).toBeGreaterThan(live);
  });

  it("fills in as the replay plays instead of showing the finished shape", () => {
    expect(VIEWER).toContain("step={visibleStep}");
    expect(CHART).toContain("latencyPlot(times, latencies, controlPeriodS, step)");
  });

  it("tracks the scrubber rather than standing still", () => {
    expect(VIEWER).toContain("atTime={trace.t[visibleStep] ?? 0}");
    expect(CHART).toContain("playheadFraction");
  });

  it("leaves its scale and gap rules where they can be tested", () => {
    // No jsdom here, so anything decided inside the SVG is checkable
    // only by looking at pixels.
    expect(CHART).toContain('from "@/lib/latencyChart"');
    expect(CHART).not.toContain("Math.max(peak");
  });
});

describe("latency chart translation keys", () => {
  const keys = [...CHART.matchAll(/"(trace\.latencyChart\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);

  it("names every string the chart draws", () => {
    expect(new Set(keys).size).toBe(5);
  });

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});

describe("the chart as the timeline", () => {
  it("seeks both panels, not just the one that was clicked", () => {
    // Moving one canvas alone breaks the only thing this view is for:
    // at any moment the two panels are supposed to be answering the
    // same question.
    expect(DETAIL).toContain("const seekFrom = (side: \"a\" | \"b\", seconds: number)");
    expect(DETAIL).toContain("onSeek={(seconds) => seekFrom(side, seconds)}");
    expect(VIEWER).toContain("onSeek={onSeek}");
  });

  it("converts the click's units when the scrubber is in metres", () => {
    // The chart hands back seconds on that candidate's own clock; the
    // progress scrubber holds arc length. Applying one to the other
    // would jump to a position with no relation to the click.
    expect(DETAIL).toContain("sideProgress(view, seconds, side)");
    expect(DETAIL).toContain('syncMode === "time"');
  });

  it("leaves playback running rather than pausing on every click", () => {
    // The first version paused, reasoning that a replay which keeps
    // rolling walks away from the moment just asked for. Backwards in
    // use: clicking the chart is how you jump to the interesting part
    // and *watch* it, and needing to press play again each time makes
    // the chart a worse scrubber than the scrubber.
    const start = DETAIL.indexOf("const seekFrom");
    const seek = DETAIL.slice(start, DETAIL.indexOf("};", start));
    expect(seek).not.toContain("playing:");
    expect(seek).toContain("sideProgress(view, seconds, side)");
  });

  it("hit-tests with the geometry it draws with", () => {
    // Two copies of the padding would put every seek off by the left
    // gutter, and the chart would still look right — the line and the
    // playhead are both drawn from the component's copy.
    expect(CHART).toContain('from "@/lib/latencyChart"');
    expect(CHART).toContain("timeAtFraction(plot,");
    expect(CHART).not.toMatch(/const PAD_LEFT = \d/);
  });

  it("is reachable without a mouse", () => {
    // Click-only, this is a control half the readers cannot use.
    expect(CHART).toContain('role={onSeek ? "slider" : "img"}');
    expect(CHART).toContain("onKeyDown");
    expect(CHART).toContain("ArrowRight");
    expect(CHART).toContain("aria-valuenow");
  });

  it("stays a plain image when it cannot be seeked", () => {
    // A slider role on something with no setter announces a control
    // that does not exist.
    expect(CHART).toContain('tabIndex={onSeek ? 0 : undefined}');
  });
});

describe("the reading tiles are a row a reader can scan", () => {
  it("puts the unit in the label and leaves the value a bare number", () => {
    /* With the unit inside the figure, `3.20 ms` and `11.66 ms` are
       different lengths: one panel's tile wrapped where the other's did
       not, and the digits moved every frame of the replay — on the row a
       reader is scanning across to compare the two candidates. A unit is
       a property of the metric and does not change while the run does. */
    expect(VIEWER).toContain('unit="ms"');
    expect(VIEWER).toContain('unit="m"');
    expect(VIEWER).toContain('unit="%"');
    expect(VIEWER).toContain('unit="s"');
    expect(VIEWER).not.toContain("} ms`");
    expect(VIEWER).not.toContain("} %`");
  });

  it("leaves the unit off a ratio and a count", () => {
    /* The slot stays empty rather than being filled with something
       plausible: `path_efficiency` and `replans` have no unit. */
    expect(VIEWER).toMatch(/label=\{t\("trace\.running\.replans"\)\}\s+value=/);
  });

  it("shows worst clearance in one unit, with the recorded one in the note", () => {
    /* `0.516 m · 1.99 r` was two units in one figure. It wrapped to two
       lines and left this tile taller than the six beside it. Metres
       wins the tile because the comparison table reports metres; the
       radii the platform actually recorded stay one hover away. */
    expect(VIEWER).not.toContain("} m · ${live.safety_margin");
    expect(VIEWER).toContain("radii: live.safety_margin.toFixed(2)");
    expect((en as Record<string, string>)["trace.running.marginUnits"]).toContain("{radii}");
    expect((vi as Record<string, string>)["trace.running.marginUnits"]).toContain("{radii}");
  });

  it("drops every figure in a row onto one baseline", () => {
    /* Labels are one line or three, and the values used to follow them,
       so one row held figures at three different heights. Grid rows
       already stretch the cards to a common height. */
    expect(VIEWER).toContain('className="stat-grid stat-grid--readings"');
    expect(CSS).toContain(".stat-grid--readings .stat-card-value { margin-top: auto; }");
  });
});
