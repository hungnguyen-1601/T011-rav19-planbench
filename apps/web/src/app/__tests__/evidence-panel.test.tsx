/** The evidence panel, checked the way this repository can check UI.
 *
 * No jsdom here (see `vitest.config.ts`), so a component with a fetch in
 * an effect cannot be driven through its states. What *can* be checked
 * is everything that would still be wrong if the markup were perfect:
 * the panel is mounted where it was argued to belong, every translation
 * key it names exists in both locales, and a 409 is handled as a state
 * rather than as an error.
 *
 * The decisions themselves — which block to draw, how a verdict reads —
 * live in `lib/evidence.ts` and are tested directly there.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const PANEL = readFileSync(join(SRC, "components", "EvidencePanel.tsx"), "utf8");
const DETAIL = readFileSync(join(SRC, "app", "decisions", "[id]", "page.tsx"), "utf8");
const CLIENT = readFileSync(join(SRC, "lib", "decisions.ts"), "utf8");
const AUTH = readFileSync(join(SRC, "lib", "auth.ts"), "utf8");

describe("where the evidence sits", () => {
  it("comes after the result and the replay", () => {
    // The page opens on what the run concluded and what it looked like;
    // the evidence explains that, and the gate table — a list of
    // eliminations — closes the argument rather than opening it.
    //
    // This order is a product decision, not something derivable from
    // the code. What *is* derivable is the pair below it.
    const comparison = DETAIL.indexOf("<CandidateComparison run={run} />");
    const trace = DETAIL.indexOf("<TracePanel run={run} />");
    const evidence = DETAIL.indexOf("<EvidencePanel run={run} />");
    expect(comparison).toBeGreaterThan(-1);
    expect(trace).toBeGreaterThan(comparison);
    expect(evidence).toBeGreaterThan(trace);
    // The gate table it used to precede is gone; the verdicts live
    // on the candidate cards at the top of the page now.
    expect(DETAIL).not.toContain("<GateTable");
  });

  it("keeps the headline immediately above the evidence it qualifies", () => {
    // `ExplanationHeader`'s whole contract. A qualifier below the thing
    // it qualifies has already been scrolled past — so this holds
    // wherever the pair ends up, and it is the reason they move
    // together.
    const headline = DETAIL.indexOf("<ExplanationHeader run={run} />");
    const evidence = DETAIL.indexOf("<EvidencePanel run={run} />");
    expect(headline).toBeGreaterThan(-1);
    expect(headline).toBeLessThan(evidence);
    // *Immediately* above, and checked as such: nothing else may be
    // rendered between them. Asserting only "before" would let a
    // section slide in and push the caveats off the reader's screen
    // while the test stayed green.
    const between = DETAIL.slice(headline + "<ExplanationHeader run={run} />".length, evidence);
    expect(between).not.toMatch(/<[A-Z]/);
  });

  it("leaves the sample notice above everything it qualifies", () => {
    // "This run was stopped before it finished" is true of every number
    // on the page, so it cannot sit below any of them.
    //
    // Was `<SampleBanner>`, which drew the notice *and* three figures
    // for the sample size. The size moved into the page head as one
    // line; only the notice still has to be positioned, and the reason
    // it has to be positioned is unchanged.
    const notice = DETAIL.indexOf("<SampleNotice run={run} />");
    expect(notice).toBeGreaterThan(-1);
    expect(notice).toBeLessThan(DETAIL.indexOf("<CandidateComparison run={run} />"));
  });
});

describe("a run with no packet", () => {
  it("reads a 409 as a state rather than as a failure", () => {
    // A run scored before the packet builder existed has no evidence.
    // Showing an error box would tell a reader something broke.
    expect(PANEL).toContain("caught.status === 409");
    expect(PANEL).toContain("evidence.unavailable");
  });

  it("catches the error type `authFetch` actually throws", () => {
    // The first version checked `ApiError`, which `authFetch` never
    // throws — so every 409 fell through to the red box while this
    // file's other assertion (the string `caught.status === 409` is
    // present) passed happily. Checking the source for a substring
    // proves the substring, not the behaviour.
    expect(PANEL).toContain("caught instanceof FieldError");
    expect(PANEL).not.toContain("instanceof ApiError");
    expect(AUTH).toContain("throw new FieldError(message, details, raw, response.status)");
  });

  it("carries the status on the error rather than leaving it in the message", () => {
    // Same rule as a checker's failure code: a state is told apart from
    // a fault by a number, not by matching prose that changes whenever
    // somebody improves a sentence.
    expect(AUTH).toMatch(/public status: number/);
  });

  it("keeps the two ways of having no decomposition apart", () => {
    // "This run ranked nobody" and "the panel plan withholds it" are
    // different sentences, and the component picks between them.
    expect(PANEL).toContain("evidence.noComparison");
    expect(PANEL).toContain("evidence.comparisonWithheld");
  });
});

describe("what the panel promises", () => {
  it("says out loud that nothing here is a conclusion", () => {
    // No analyst has passed the gate, so the packet carries evidence
    // and no claims. The badge is what stops a reader supplying the
    // inference silently.
    expect(PANEL).toContain("evidence.noClaimsYet");
  });

  it("shows what could not be built instead of hiding a thin packet", () => {
    expect(PANEL).toContain("evidence.omissions.title");
    expect(PANEL).toContain("evidence.gaps.title");
  });

  it("prints an interval beside every contribution", () => {
    // A bar chart without intervals invites reading the height alone.
    expect(PANEL).toContain("evidence.waterfall.ci");
    expect(PANEL).toContain("bar.ci95[0]");
  });

  it("reports sightings as a fraction, never as a percentage", () => {
    // "3%" hides that it was one episode out of thirty.
    expect(PANEL).toMatch(/episodes_seen\}\s*\/\s*\{item\.episodes_total/);
    expect(PANEL).not.toContain("episodes_seen / item.episodes_total");
  });
});

describe("translation keys", () => {
  const keys = [...PANEL.matchAll(/t\(\s*"(evidence\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);
  const dynamic = [
    "supports_component_specific_attribution",
    "rules_out_component_specific_attribution",
    "interaction_not_isolated",
    "insufficient_contrast",
  ].map((verdict) => `evidence.lattice.verdict.${verdict}`);

  it("names at least the blocks this panel is made of", () => {
    expect(keys.length).toBeGreaterThan(8);
  });

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    // A missing key renders as the key itself, which looks like a bug
    // in the data rather than in the translation file.
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });

  it.each(dynamic)("%s exists for every lattice verdict", (key) => {
    // Composed at runtime from the verdict, so no static scan would
    // catch a missing one.
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});

describe("the client", () => {
  it("asks the route that serves a packet built during scoring", () => {
    expect(CLIENT).toContain("/decisions/${runId}/explanation");
  });

  it("types the decomposition as nullable, because a run may rank nobody", () => {
    expect(CLIENT).toMatch(/waterfall: PacketWaterfall \| null/);
  });
});

/** Traffic on the trace canvas.
 *
 * The map is static and the trace records only the robot, so a route
 * that bent around a cart was bending around nothing. The positions
 * come from the server; what this file can check is that the browser
 * asks for them, draws them at the instant being shown, and never
 * recomputes them itself.
 */
describe("dynamic obstacles on the canvas", () => {
  const VIEWER = readFileSync(join(SRC, "components", "TraceViewer.tsx"), "utf8");

  it("draws whatever tracks the payload carries", () => {
    expect(VIEWER).toContain("trace.dynamic_obstacles");
    expect(VIEWER).toContain("context.arc");
  });

  it("draws them at the step being shown, not at the end of the episode", () => {
    // A cart parked at its final position for the whole replay would
    // explain nothing about a bend that happened at t = 3 s.
    expect(VIEWER).toMatch(/Math\.min\(visibleStep, track\.x\.length - 1\)/);
  });

  it("puts the obstacle under the robot and over the path", () => {
    // Over the path because it is what the path was avoiding; under the
    // robot because the robot is the subject of the picture.
    const path = VIEWER.indexOf("clearanceColour(");
    const obstacles = VIEWER.indexOf("trace.dynamic_obstacles");
    const robot = VIEWER.indexOf("The robot at the current step");
    expect(obstacles).toBeGreaterThan(path);
    expect(obstacles).toBeLessThan(robot);
  });

  it("keeps the motion model on the server", () => {
    // `position_at` is the one implementation, seed shift included. A
    // second copy here would drift the first time either was fixed —
    // the same argument that keeps progress-sync server-side.
    expect(VIEWER).not.toContain("seed_time_offset");
    expect(VIEWER).not.toMatch(/WaypointMotion|SuddenStop|position_at/);
  });

  it("survives a payload that predates the field", () => {
    // `?? []` rather than a required read: an older API answering this
    // page should draw one fewer thing, not throw.
    expect(VIEWER).toContain("trace.dynamic_obstacles ?? []");
  });

  it("says on the canvas what the amber circles are", () => {
    expect(en["trace.colourNote"]).toContain("Amber circles");
    expect(vi["trace.colourNote"]).toContain("hổ phách");
  });
});

/** The planned route on the trace canvas.
 *
 * Nothing persisted a plan's polyline before the planning-input sidecar:
 * the metrics kept its length and threw the shape away. The canvas could
 * show where the robot went and not what it had been asked to do — and
 * the gap between those two is most of what a replan is.
 */
describe("planned routes on the canvas", () => {
  const VIEWER = readFileSync(join(SRC, "components", "TraceViewer.tsx"), "utf8");
  const CLIENT2 = readFileSync(join(SRC, "lib", "decisions.ts"), "utf8");

  it("draws the plan in force at the step being shown", () => {
    expect(VIEWER).toContain("routeAt(trace.planned_routes ?? []");
  });

  it("draws it under the driven path, where the two can be compared", () => {
    // An intention behind a measurement. On top it would compete with
    // the trajectory that actually happened.
    //
    // Anchored on the comment above the drawing loop, not on
    // `clearanceColour(` — that name's first occurrence is the
    // function's own definition near the top of the file, so the first
    // version of this compared the plan against a declaration and
    // failed for a reason that had nothing to do with layering.
    const planned = VIEWER.indexOf("routeAt(trace.planned_routes");
    const driven = VIEWER.indexOf("Segment by segment, because the colour is the clearance");
    expect(driven).toBeGreaterThan(-1);
    expect(planned).toBeLessThan(driven);
  });

  it("dashes it, because it is an intention and not a measurement", () => {
    expect(VIEWER).toContain("setLineDash");
  });

  it("does not pick the active plan in the component", () => {
    // `routeAt` is where the replacement rule lives, so it can be tested
    // without a DOM. A loop here would put it back out of reach.
    expect(VIEWER).not.toMatch(/from_index\s*<=/);
  });

  it("types a refused replan as an empty route rather than a missing one", () => {
    // "The robot had no plan at that step" is a state worth drawing as
    // nothing, and it is not the same as "this run kept no plans".
    expect(CLIENT2).toContain("points: { x: number; y: number }[]");
    expect(CLIENT2).toContain("planned_routes: PlannedRoute[]");
  });

  it("says on the canvas what the dashed line is", () => {
    // No longer "dashed grey": the line takes a different colour at
    // every replan, so naming one colour would describe the first plan
    // and mislead about the rest.
    expect(en["trace.colourNote"]).toContain("dashed line");
    expect(en["trace.colourNote"]).not.toContain("dashed grey");
    expect(vi["trace.colourNote"]).toContain("nét đứt");
  });

  it("says the colour change means a replan", () => {
    // Otherwise the reader sees four colours and reads them as four
    // kinds of plan rather than four plans.
    expect(en["trace.colourNote"]).toContain("changes colour at every replan");
    expect(vi["trace.colourNote"]).toContain("đổi màu mỗi lần replan");
  });
});
