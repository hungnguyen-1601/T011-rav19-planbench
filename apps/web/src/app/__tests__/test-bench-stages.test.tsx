/** The test bench in two screens: prepare an episode, then watch it.
 *
 * One long column asked the reader to hold a form and a canvas in view
 * at once, and neither was what they were doing. The page now shows the
 * setup form until Run is pressed and the console after it, and the
 * three claims worth defending are the ones that were easy to get wrong:
 *
 * 1. **The switch happens on the press, not on the data.** Nothing on
 *    the page says "a result exists": `map` is set by Show world as
 *    well, `plan` only arrives when the server replies, and
 *    `stream.frames` stays empty for an episode that planned nothing. A
 *    screen picked from any of them puts the reader back on the form for
 *    the whole run, or leaves them there for good when the answer is
 *    `no_path`.
 * 2. **Show world is not a run.** It stages a map so the reader can
 *    check the world before committing to it, so it has to answer where
 *    they are — which is why the setup screen has a canvas of its own.
 * 3. **Nothing is unmounted.** `useEpisodeStream` holds the socket, the
 *    frames, the metrics and the playhead, and unmounting it closes the
 *    socket and drops all of it — recoverable only by running another
 *    episode. The panels are hidden the way `DecisionTabs` hides its
 *    own, and the CSS trap that makes `hidden` silently fail is covered
 *    below.
 *
 * Two registers, for the reason `decisions-list-tabs.test.tsx` gives:
 * this repo has no jsdom. **Rendered**, through `renderToStaticMarkup`,
 * for the screen a reader lands on — effects do not run there, so first
 * paint is exactly the default state. **Source-level** for what a click
 * does, which no render here can reach.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import TestBenchPage from "../simulate/page";

const APP = join(process.cwd(), "src", "app");
const PAGE = readFileSync(join(APP, "simulate", "page.tsx"), "utf8");
const CSS = readFileSync(join(APP, "globals.css"), "utf8");

/** One handler's body, so an assertion about it cannot be satisfied by
 *  a line somewhere else in a 900-line file. */
function body(from: string, to: string): string {
  const start = PAGE.indexOf(from);
  const end = PAGE.indexOf(to, start);
  expect(start, `${from} is gone`).toBeGreaterThan(-1);
  expect(end, `${to} is gone`).toBeGreaterThan(start);
  return PAGE.slice(start, end);
}

describe("the reader lands on the setup screen", () => {
  /* No effects run under `renderToStaticMarkup`, so this markup is the
     page's default state and nothing else. */
  const html = renderToStaticMarkup(<TestBenchPage />);

  it("shows the form", () => {
    expect(html).toContain('class="panel simulate-setup"');
    expect(html).not.toMatch(/class="panel simulate-setup"[^>]*hidden/);
  });

  it("hides the console and the metrics rather than dropping them", () => {
    /* Present in the markup **and** hidden. "Absent" would pass a test
       that only checked they were not on screen, and absent is the one
       outcome that closes the socket. */
    expect(html).toMatch(/class="simulate-console"[^>]*hidden=""/);
    expect(html).toMatch(/class="simulate-metrics"[^>]*hidden=""/);
  });

  it("hides the way back, because there is nothing to go back from", () => {
    expect(html).toMatch(/class="simulate-stage-bar"[^>]*hidden=""/);
  });

  it("keeps the playback controls and the telemetry in the document", () => {
    /* They live inside the console. If the console were a ternary these
       would be gone, and with them the hook that owns the playhead. */
    expect(html).toContain("simulate-playback");
    expect(html).toContain("simulate-side-panel");
  });

  it("says nothing about an episode's status yet", () => {
    /* `ready` is not news before a run, and after one it would be the
       previous run's verdict standing over a form being edited. */
    expect(html).toMatch(/class="simulate-status simulate-status--ready"[^>]*hidden=""/);
  });

  it("puts up no preview canvas before a world is staged", () => {
    expect(html).not.toContain("simulate-preview");
  });
});

describe("the screen is a state, not a guess at one", () => {
  it("is held rather than derived from map, plan or frames", () => {
    /* Each of those answers a different question, and the difference is
       exactly the reader this page fails: `map` is true after Show
       world, `plan` only once the server has replied, `frames` only when
       the robot moved. */
    expect(PAGE).toContain('type BenchStage = "setup" | "results"');
    expect(PAGE).toContain('const [stage, setStage] = useState<BenchStage>("setup")');
    expect(PAGE).toContain('const showingRun = stage === "results"');
  });

  it("never reads a stage back out of the run's data", () => {
    for (const derived of [
      "map ? \"results\"",
      "plan ? \"results\"",
      "stream.frames.length > 0 ? \"results\"",
    ]) {
      expect(PAGE).not.toContain(derived);
    }
  });
});

describe("pressing Run moves to the results screen immediately", () => {
  const run = body("const runOne = useCallback", "const anotherBench");

  it("switches before the episode is asked for, not after it answers", () => {
    /* Awaiting first would hold the reader on the form for the whole
       run and then move the page under them at the end — the one moment
       the screen exists to show is the one they would miss. */
    expect(run).toContain('setStage("results")');
    expect(run.indexOf('setStage("results")')).toBeLessThan(run.indexOf("await prepare()"));
  });

  it("keeps them there when the episode produced no trajectory", () => {
    /* `no_path` has a plan, no frames and a reason. Sending that reader
       back to the form would file the answer on the screen they are not
       looking at. Nothing in the handler returns to setup — including
       the branch that sets the failure text. */
    expect(run).toContain("bench.noPath");
    expect(run).not.toContain('setStage("setup")');
  });

  it("reports the reason outside both screens, so it survives the switch", () => {
    /* The error box is the page's, not the form's: it is rendered above
       the setup section and carries no `hidden`, so a failure is on
       screen whichever half is up. */
    const box = PAGE.indexOf('className="error-box simulate-error"');
    expect(box).toBeGreaterThan(-1);
    expect(box).toBeLessThan(PAGE.indexOf('className="panel simulate-setup"'));
  });
});

describe("Show world stays on the setup screen", () => {
  const show = body("const showTheWorld = useCallback", "const runOne = useCallback");

  it("changes no stage at all", () => {
    /* Previewing a world is part of choosing a deployment. A button that
       moved the reader to a results screen with no result on it would
       make "look at it" and "run it" the same gesture, which is the one
       distinction this button exists to draw. */
    expect(show).not.toContain("setStage(");
  });

  it("gives the setup screen a canvas of its own to answer into", () => {
    /* The console's canvas is the episode and lives on the other screen
       now, so without this the map would have nowhere to appear. */
    expect(PAGE).toContain("{!showingRun && map ? (");
    expect(PAGE).toContain('className="panel simulate-preview"');
  });

  it("draws the deployment's world there and nothing from the run", () => {
    /* The hook still holds the previous episode's frames — see
       `anotherBench` — and a preview that drew them would put a
       trajectory under a form the reader is changing. */
    const preview = body('className="panel simulate-preview"', "{/* What the deployment fixed");
    expect(preview).toContain("authoredTraffic={overlayOf(");
    expect(preview).toContain("robotPose={start}");
    for (const fromTheRun of ["stream.", "visibleTrajectory", "plan?.path", "collisionPoint"]) {
      expect(preview, `the preview reads ${fromTheRun}`).not.toContain(fromTheRun);
    }
  });
});

describe("another test bench keeps everything that was typed", () => {
  const back = body("const anotherBench = () =>", "const visibleTrajectory");
  const note = body("/** Back to the setup screen", "const anotherBench = () =>");

  it("goes back to the form", () => {
    expect(back).toContain('setStage("setup")');
  });

  it("clears none of the four choices", () => {
    /* The reason to come back is to change one of them. A blank form
       would make the reader retype the three they were happy with. */
    for (const setter of ["setProfileId(", "setMissionId(", "setChoice(", "setSeed("]) {
      expect(back, `${setter} would wipe a choice`).not.toContain(setter);
    }
  });

  it("keeps the staged world too", () => {
    expect(back).not.toContain("setMap(null)");
    expect(back).not.toContain("setStaged(null)");
  });

  it("stops the clock without pretending it dropped the frames", () => {
    /* `reset` rewinds the playhead and pauses; only `connect` empties
       `frames`, and calling that would mean running another episode.
       The comment is the assertion here: the next reader has to know the
       trajectory is still in memory, and why nothing draws it. */
    expect(back).toContain("stream.reset()");
    expect(note).toContain("only `connect` does that");
  });
});

describe("the panels are hidden, and the CSS lets them be", () => {
  it("hides with the attribute rather than unmounting", () => {
    expect(PAGE).toContain('className="simulate-console" aria-label={t("bench.consoleTitle")} hidden={!showingRun}');
    expect(PAGE).toContain('<section className="simulate-metrics" hidden={!showingRun}>');
    expect(PAGE).toContain('aria-labelledby="simulate-setup-title" hidden={showingRun}');
  });

  it("keeps the stream hook at the page, above every switch", () => {
    /* The socket, the frames, the metrics and the playhead all live in
       it. Moved into either screen it would be unmounted by the other. */
    expect(PAGE).toContain("const stream = useEpisodeStream();");
    expect(PAGE.indexOf("const stream = useEpisodeStream();")).toBeLessThan(
      PAGE.indexOf("const anotherBench"),
    );
  });

  it("names every hidden element in the stylesheet", () => {
    /* `[hidden] { display: none }` is a UA rule and loses to any author
       `display` — the trap `.decision-tabpanel[hidden]` already
       documents. A panel with a `display` of its own would stay on
       screen with nothing in the markup saying why. */
    const rule = CSS.slice(
      CSS.indexOf(".simulate-setup[hidden]"),
      CSS.indexOf(".simulate-preview {"),
    );
    for (const selector of [
      ".simulate-setup[hidden]",
      ".deployment-conditions[hidden]",
      ".simulate-stage-bar[hidden]",
      ".simulate-console[hidden]",
      ".simulate-metrics[hidden]",
      ".simulate-status[hidden]",
    ]) {
      expect(rule, `${selector} is not covered`).toContain(selector);
    }
    expect(rule).toContain("display: none;");
  });
});

describe("the new strings exist in both languages", () => {
  it("carries every key the two screens ask for", () => {
    for (const key of [
      "bench.another",
      "bench.anotherNote",
      "bench.previewTitle",
      "bench.previewSubtitle",
    ]) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });

  it("says the choices are kept, which is the whole point of the button", () => {
    expect((en as Record<string, string>)["bench.anotherNote"]).toContain("kept");
    expect((vi as Record<string, string>)["bench.anotherNote"]).toContain("giữ nguyên");
  });

  it("leaves the two dictionaries the same size", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });
});
