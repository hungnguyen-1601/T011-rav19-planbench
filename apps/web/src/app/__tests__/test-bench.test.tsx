/** The test bench — `/simulate` after it stopped being free play.
 *
 * The page it replaces took a map, a start and a goal placed by clicking,
 * and a scenario invented on the spot. Watching that told you the
 * simulator worked; it told you nothing about the deployment you were
 * about to spend two hours measuring.
 *
 * Two claims carry the redesign, and both are the kind that fail
 * silently:
 *
 * 1. **What you watch is what the comparison will run.** Every condition
 *    comes from the deployment, and none of them is editable here. A
 *    single field that let somebody nudge the timeout "just for the
 *    preview" would turn confidence into a claim about a different
 *    experiment.
 * 2. **Nothing it produces is evidence, and the page says so first.** No
 *    trace is written, so no gate or card can see the run (HĐ-5). A
 *    reader who learns that after watching a clean episode has been told
 *    too late to have made a decision with it.
 *
 * Source-level like the other page tests: the page sits behind an effect
 * and three fetches, so a first paint would only show a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { NAV_SECTIONS } from "../../lib/navigation";
import { poseOf } from "../../lib/deployments";

const APP = join(process.cwd(), "src", "app");
const PAGE = readFileSync(join(APP, "simulate", "page.tsx"), "utf8");
const CLIENT = readFileSync(join(process.cwd(), "src", "lib", "decisions.ts"), "utf8");
const EN = en as Record<string, string>;
const VI = vi as Record<string, string>;

describe("the episode comes from a deployment, not from a form", () => {
  it("takes a deployment and one of its missions", () => {
    /* The input change is the whole feature. A map plus two clicked
       poses is a scenario nobody is going to measure. */
    expect(PAGE).toContain("listTaskProfiles()");
    expect(PAGE).toContain("stageTestBenchEpisode(");
    expect(PAGE).toContain("mission_id: mission.id");
  });

  it("no longer lets anybody place the start or the goal", () => {
    /* A draggable goal would make what you are watching a different
       episode from the one about to be measured — precisely the false
       comfort a test bench must not offer. The canvas is passed no click
       handler at all, which is what makes that unreachable rather than
       merely discouraged. */
    expect(PAGE).not.toContain("onWorldClick");
    expect(PAGE).not.toContain("placeMode");
    expect(PAGE).not.toContain("api.createScenario");
  });

  it("offers no replanning switch, because a measured episode has none", () => {
    /* `run_contract_episode` calls `run_stack` without a replanning
       config, so every episode a comparison measures runs with it off. A
       switch here would let somebody watch a navigation stack that will
       never be judged. This is the inverted half of the claim that used
       to live in `replanning-controls.test.tsx`. */
    expect(PAGE).not.toContain("ReplanningControls");
    expect(PAGE).not.toContain("NO_REPLANNING");
  });

  it("shows the deployment's conditions as text, never as inputs", () => {
    /* Timeout, tolerance, noise and traffic are read out of the stored
       profile and rendered into a table. Each one is a condition the
       comparison runs under; an editable copy would be a second
       statement of the deployment, free to disagree with it. */
    expect(PAGE).toContain("bench.conditions");
    expect(PAGE).toContain("deployment.constraints?.episode_timeout_s");
    expect(PAGE).toContain("deployment.environment?.sensor_noise");
    expect(EN["bench.conditionsNote"]).toContain("kept unchanged");
    expect(VI["bench.conditions"]).toBe("Điều kiện triển khai");
    expect(PAGE).toContain("deployment-conditions-grid");
    expect(PAGE).toContain("<ConditionGroup");
    expect(PAGE).not.toContain('<section className="panel simulate-conditions">');
  });

  it("names which noise streams are switched on", () => {
    /* A count would say nothing and the full table would drown the row
       that matters. Naming the active streams is what tells somebody at
       a glance that the episode runs under a drift they forgot they
       declared. */
    expect(PAGE).toContain("function describeNoise(");
    expect(en).toHaveProperty("bench.noiseNone");
    expect(vi).toHaveProperty("bench.noiseNone");
  });

  it("presents locked conditions as semantic compact groups", () => {
    expect(PAGE).toContain('className="deployment-condition-list"');
    expect(PAGE).toContain("<dt>");
    expect(PAGE).toContain("<dd>");
    expect(PAGE).toContain("bench.conditionsLockedHint");
    expect(PAGE).toContain("aria-expanded={conditionsExpanded}");
    expect(PAGE).toContain("bench.conditionsSummary");
  });

  it("renders replanning and active noise as labelled badges, not raw JSON", () => {
    expect(PAGE).toContain('condition-status ${deployment.replanning?.enabled ? "is-on" : "is-off"}');
    expect(PAGE).toContain("activeNoiseNames(deployment.environment?.sensor_noise)");
    expect(PAGE).toContain("bench.noiseNone");
  });

  it("shortens only the displayed context id", () => {
    expect(PAGE).toContain("shortContextId(staged.episode_context_id)");
    expect(PAGE).toContain('title={staged.episode_context_id}');
    expect(PAGE).toContain("stageTestBenchEpisode");
  });
});

describe("the seed is typed, and saying so is the point", () => {
  it("is a field rather than something the server draws", () => {
    /* Two runs with the same seed are the same episode down to the
       obstacle trajectories and the noise draws. A server-picked seed
       would make the one episode worth re-watching the one you cannot
       get back. */
    expect(PAGE).toContain('t("bench.seed")');
    expect(PAGE).toContain("seed,");
    expect(CLIENT).toContain("seed: number");
  });

  it("explains what the number buys", () => {
    expect(PAGE).toContain("bench.seedNote");
    expect(EN["bench.seedNote"]).toContain("same episode");
  });

  it("cannot be made negative or fractional", () => {
    /* The contract's seed is a non-negative integer, and a form that
       could produce 0.5 would fail at the server for a reason nobody
       chose. */
    expect(PAGE).toContain("Math.max(0, Math.trunc(Number(event.target.value)))");
  });
});

describe("nothing it produces is evidence, and the page leads with that", () => {
  it("says so before the run, not after", () => {
    const banner = PAGE.indexOf("bench.notEvidence");
    expect(banner).toBeGreaterThan(-1);
    expect(banner).toBeLessThan(PAGE.indexOf("bench.run"));
  });

  it("names the reason rather than only the fact", () => {
    /* "This is only a preview" invites the question "why does that
       matter". The trace is the answer: HĐ-5 makes it the sole input of
       the Metrics Engine, so no trace means nothing downstream can see
       the run. */
    expect(EN["bench.notEvidence"]).toContain("HĐ-5");
    expect(EN["bench.notEvidence"]).toContain("no trace");
    expect((vi as Record<string, string>)["bench.notEvidence"]).toContain("HĐ-5");
  });

  it("qualifies the metrics panel instead of leaving the numbers bare", () => {
    /* They are read off the run rather than off a trace, which makes
       them right for "did that look sane" and wrong for any claim. Bare,
       they look like the numbers a gate would use. */
    expect(PAGE).toContain("bench.metricsNote");
    expect(EN["bench.metricsNote"]).toContain("not off a trace");
  });

  it("shows the real context id rather than a preview-only label", () => {
    /* Reported honestly because it is the answer to "is this the same
       episode the comparison will run": it is, and the HĐ-3.1 hash is
       what says so. */
    expect(PAGE).toContain("staged.episode_context_id");
    expect(EN["bench.contextIdNote"]).toContain("HĐ-3.1");
  });
});

describe("switching deployment clears what the last one drew", () => {
  it("drops the mission, the staged episode, the map and the stream", () => {
    /* An old trajectory left drawn under a new deployment's map is the
       most confusing screen this page could produce: every pixel of it
       is real, and none of it is about what the header now says. */
    const effect = PAGE.slice(PAGE.indexOf("setMissionId(missions[0]"), PAGE.indexOf("const runOne"));
    expect(effect).toContain("setStaged(null)");
    expect(effect).toContain("setMap(null)");
    expect(effect).toContain("stream.reset()");
  });
});

describe("the page is reachable and translated", () => {
  it("sits with the things a reader is doing, not with the retiring flow", () => {
    /* `nav.section.doing` is now `nav.section.workspace` — a label that
       names a place rather than describing an activity. Same group. */
    const workspace = NAV_SECTIONS.find((section) => section.titleKey === "nav.section.workspace");
    expect(workspace?.items.map((item) => item.href)).toContain("/simulate");
  });

  it("is named for what it now is", () => {
    /* "Live Simulation" described the machinery; the page is now the
       cheap step before an expensive one, and the sidebar should say
       which of those a reader is looking at. */
    expect(EN["nav.simulate"]).toBe("Test Bench");
    expect((vi as Record<string, string>)["nav.simulate"]).toBe("Sân thử");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set([...PAGE.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });

  it("sends the reader on to the comparison the episode was checking for", () => {
    expect(PAGE).toContain('href="/decisions"');
    expect(en).toHaveProperty("bench.toComparison");
  });
});

describe("a stored mission is read in either shape the contract allows", () => {
  /** The bug: `/simulate` crashed on first paint.
   *
   * It defaults to the first deployment, which is a shipped one, and the
   * shipped ones hold `start: [x, y, theta]` — HĐ-2's YAML form, which
   * `Mission` accepts through a before-validator so a contract document
   * can be pasted verbatim. Deployments filed from the form hold
   * `{x, y, theta}` instead. **Both are legal and both are in the
   * store**, so the page was reading half the contract.
   *
   * Not a defensive-coding fix: nothing here is untrusted. The two
   * shapes are what HĐ-2 defines, and one boundary function resolving
   * them is the honest reading.
   */
  it("accepts the YAML triplet the shipped deployments use", () => {
    expect(poseOf([2, 8, 0])).toEqual({ x: 2, y: 8, theta: 0 });
  });

  it("accepts the dumped object the form produces", () => {
    expect(poseOf({ x: 1.5, y: 4, theta: 1.57 })).toEqual({ x: 1.5, y: 4, theta: 1.57 });
  });

  it("defaults a missing heading to zero, which the contract also does", () => {
    expect(poseOf([2, 8])).toEqual({ x: 2, y: 8, theta: 0 });
    expect(poseOf({ x: 2, y: 8 })).toEqual({ x: 2, y: 8, theta: 0 });
  });

  it("returns null rather than the origin for anything else", () => {
    /* (0, 0) is a real place on every map — usually a corner, often
       inside a wall. Substituting it would draw the robot somewhere it
       is not, which is worse than an em dash. */
    for (const value of [null, undefined, "2,8", {}, [], { x: "2", y: 8 }]) {
      expect(poseOf(value)).toBeNull();
    }
  });

  it("the page resolves the pose once instead of reaching into the mission", () => {
    /* Two readers of the same wire shape is how one of them ends up
       handling only one form again. */
    expect(PAGE).toContain("const start = poseOf(mission?.start)");
    expect(PAGE).not.toContain("mission.start.x");
    expect(PAGE).not.toContain("mission?.start ??");
  });

  it("types the wire fields as unknown rather than claiming a shape", () => {
    /* A `Pose` type here would be a claim the data does not honour, and
       TypeScript would then vouch for the crash. */
    expect(PAGE).toContain("start: unknown;");
    expect(PAGE).toContain("goal: unknown;");
  });
});

describe("the traffic is on screen, at the instant on screen", () => {
  /** Two gaps An found by using the page, and they had one root.
   *
   * The engine records where every dynamic obstacle was at each sample
   * — `TrajectoryPoint.obstacles`, ground truth kept for replay and
   * never handed to a planner (HĐ-4). The schema carried it, the canvas
   * could draw it, and the WebSocket dropped it. So a watched episode
   * showed a robot swerving around nothing, on the one screen whose
   * entire purpose is seeing what it was avoiding.
   */
  it("the socket sends the snapshot it already has", () => {
    const ws = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "routers", "ws.py"),
      "utf8",
    );
    expect(ws).toContain('"obstacles"');
    expect(ws).toContain("for o in point.obstacles");
  });

  it("the frame keeps it rather than dropping it on the way in", () => {
    const stream = readFileSync(join(process.cwd(), "src", "lib", "useEpisodeStream.ts"), "utf8");
    expect(stream).toContain("obstacles: message.obstacles");
  });

  it("draws where the traffic was at the playhead, not at t=0", () => {
    /* An obstacle frozen at its starting position would be worse than
       none: it would look like a fact about the episode. */
    expect(PAGE).toContain("stream.currentFrame?.obstacles");
    expect(PAGE).toContain("previewTime={stream.playhead}");
  });

  it("treats an unrecorded list as nothing, never as an empty aisle", () => {
    /* `?? []` rather than a default that claims the way was clear.
       "We did not record it" and "it was clear" are different claims and
       only the second is reassuring. */
    expect(PAGE).toContain("stream.currentFrame?.obstacles ?? []");
  });

  it("shows the declared routes without running anything first", () => {
    /* The map used to arrive only as a side effect of pressing Run, so
       the traffic a deployment declares was invisible until after the
       episode it was meant to inform — the wrong way round for a page
       whose job is to check a deployment before a 300-episode
       comparison commits to it. */
    expect(PAGE).toContain("const prepare = useCallback");
    expect(PAGE).toContain("showTheWorld");
    expect(PAGE).toContain("authoredTraffic={overlayOf(");
  });

  it("stages once, whichever button asked for it", () => {
    /* Both paths go through `prepare`, so "show me" and "run it" cannot
       drift into two different ideas of which map a deployment means. */
    const run = PAGE.slice(PAGE.indexOf("const runOne"), PAGE.indexOf("const visibleTrajectory"));
    expect(run).toContain("await prepare()");
    expect(run).not.toContain("stageTestBenchEpisode(");
  });
});

describe("two views of one scene, and neither replaces the other", () => {
  /** The swap itself moved out of this page.
   *
   * It started here — a pair of buttons in the test bench's own toolbar —
   * and that was the wrong shape: the app draws maps on six surfaces and
   * a toggle per page is six chances to forget one, which is exactly how
   * the raised view came to exist on a single screen for months. It now
   * lives in `MapView`, and `map-view.test.tsx` sweeps the whole app for
   * a screen that bypasses it.
   *
   * What stays this page's business is *feeding* the view: the traffic at
   * the playhead, the mission poses, the layer checkboxes.
   */
  it("draws its map through the shared view rather than a renderer", () => {
    expect(PAGE).toContain("<MapView");
    expect(PAGE).not.toContain("<Scene25D");
    expect(PAGE).not.toContain("<MapCanvas");
  });

  it("hands the raised view the traffic in the shape it takes", () => {
    /* `MapCanvas` wants markers with a nested position, `Scene25D` wants
       flat snapshots. Both are fed from the same frame, because two
       views showing different worlds would be worse than one view. */
    expect(PAGE).toContain("dynamicObstacles={traffic}");
    expect(PAGE).toContain("obstacleSnapshots={stream.currentFrame?.obstacles ?? []}");
  });
});

describe("the conditions table says whether replanning is on", () => {
  /** The gap An hit: the switch existed and nothing on this page said
   *  which way it was set.
   *
   * Whether a candidate may replan changes what happens the moment the
   * robot is blocked — which is the moment this page exists to show. A
   * table of "what the deployment fixed" that omitted it was omitting
   * the condition most likely to explain what you are watching, and left
   * "the robot just sat there" looking like a broken planner rather than
   * a deployment that never allowed a second plan.
   */
  it("lists it beside the other fixed conditions", () => {
    expect(PAGE).toContain("bench.replanning");
    expect(PAGE).toContain("deployment.replanning?.enabled");
  });

  it("says what each state means rather than printing on or off", () => {
    /* "off" alone leaves a reader to guess whether that is a setting or
       a missing feature. */
    expect(EN["bench.replanningOff"]).toContain("local controller alone");
    expect(EN["bench.replanningOn"]).toContain("charged");
    for (const key of ["bench.replanningOn", "bench.replanningOff"]) {
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });

  it("offers no control for it, because the deployment owns it", () => {
    /* Every condition on this page is read, not set — a switch here
       would make what you watch a different episode from the one about
       to be measured. */
    expect(PAGE).not.toContain('set("replanning');
    expect(PAGE).not.toContain("setReplanning");
  });
});

describe("the metrics panel answers whether it replanned", () => {
  /** An switched replanning on, watched a robot sit still, and had no
   *  way to tell whether it never tried or the setting never arrived.
   *
   * The row existed and rendered only when the count was truthy, on the
   * reasoning that a column of zeros on every non-replanning run buries
   * the metrics that matter. The reasoning was fine; the effect was that
   * **"replanned 0 times" and "this platform does not report replans"
   * became the same blank** — and that blank is exactly the question
   * somebody debugging a stuck robot is asking.
   */
  const PANEL = readFileSync(
    join(process.cwd(), "src", "components", "MetricsPanel.tsx"),
    "utf8",
  );

  it("always renders the row rather than hiding a zero", () => {
    expect(PANEL).not.toContain("{metrics.replan_count ? (");
    expect(PANEL).toContain('label={t("metrics.replanCount")}');
  });

  it("distinguishes off, zero, and not recorded", () => {
    /* Three answers, because there are three states: off is not a count,
       and 0 is not silence. */
    expect(PANEL).toContain("replanning === undefined");
    expect(PANEL).toContain("replanning.enabled");
    expect(PANEL).toContain("metrics.replan_count ?? 0");
    for (const key of ["metrics.replanOff", "metrics.replanUnknown"]) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });

  it("takes the rule from the deployment, not from the run", () => {
    /* It is the value the episode was staged with, and it is the one
       that answers "did the setting arrive at all" — which a count read
       off the run cannot. */
    expect(PAGE).toContain("deployment.replanning?.enabled");
    expect(PAGE).toContain("replanning={deployment ?");
  });
});
