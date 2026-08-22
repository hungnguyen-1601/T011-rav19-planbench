/** The trace viewer — the first thing that can look at the evidence.
 *
 * One Parquet file per (candidate, episode) is the sole input the
 * Metrics Engine has (HĐ-5), and every number on a Decision Card is
 * derived from one. Before this component the platform could print
 * "G3: fail, 70% success" and offer no way to open a single episode
 * behind it.
 *
 * What these tests defend is not that it draws — a canvas test would
 * assert pixels nobody checks — but that it draws the things that carry
 * meaning, and does not quietly draw a mirror of the run.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const VIEWER = readFileSync(join(SRC, "components", "TraceViewer.tsx"), "utf8");
const DETAIL = readFileSync(join(SRC, "app", "decisions", "[id]", "page.tsx"), "utf8");

describe("the viewer sits with the evidence it explains", () => {
  it("sits under the comparison it replays, after the conclusion", () => {
    /* **Two positions have been wrong here, in opposite directions.**
       It was second on the page, ahead of everything that said what the
       run decided — a reader arriving for the result met a
       thirty-episode pager first. It then went below the evidence, which
       fixed that and broke something else: watching the two candidates
       drive is how this run gets read, and four screens down it read as
       having gone missing.

       What survives from both: the conclusion and the advice come
       first, and the replay sits directly under the table it replays. */
    expect(DETAIL.indexOf("<TracePanel")).toBeGreaterThan(DETAIL.indexOf("<DecisionSummary"));
    expect(DETAIL.indexOf("<TracePanel")).toBeGreaterThan(DETAIL.indexOf("<CandidateComparison"));
    expect(DETAIL.indexOf("<TracePanel")).toBeLessThan(DETAIL.indexOf("<EvidencePanel"));
  });

  it("is open, and can still be folded away", () => {
    /* A panel that has to be opened every visit reads as one that went
       missing. `<details>` rather than a plain div so the reader who has
       finished with it keeps the choice. */
    expect(DETAIL).toContain('className="panel decision-sample-panel episode-comparison" open');
  });

  it("loads both candidate traces for only the selected episode", () => {
    /* A run holds thirty to three hundred episodes per candidate, each a
       map plus a few hundred poses. */
    expect(DETAIL).toContain("getTrace(run.id, candidate.candidate_id, episode)");
    expect(DETAIL).toContain("Promise.all(candidates.map");
    expect(DETAIL).toContain("episode_context_id");
  });

  it("says what the picture is evidence for", () => {
    const note = (en as Record<string, string>)["trace.note"];
    expect(note).toContain("HĐ-5");
  });
});

describe("what the drawing has to get right", () => {
  it("flips world y for screen y", () => {
    /* Screen y grows downward and world y does not. Without the flip the
       canvas draws a mirror of the run — and a mirrored path still looks
       like a plausible path, which is why this is asserted rather than
       eyeballed. */
    expect(VIEWER).toContain("canvas.height - ((metres - map.origin.y)");
  });

  it("draws the robot to its declared radius, not as a dot", () => {
    /* A path that looks clear at one pixel per cell may not be, once the
       body is drawn at 0.26 m. */
    expect(VIEWER).toContain("trace.robot_radius_m / map.resolution");
  });

  it("colours the path by clearance rather than stroking it flat", () => {
    /* G2 bounds collisions and the safety objective anchors on clearance
       from the robot's *surface*, so the interesting part of a
       trajectory is where it ran close. One colour hides exactly that. */
    expect(VIEWER).toContain("clearanceColour(");
    expect(VIEWER).toContain("trace.clearance_m[index]");
  });

  it("treats zero clearance as the collision boundary", () => {
    /* HĐ-8.2: `clearance_m` is measured from the surface, so 0 is
       contact — not a centre distance with a radius still to subtract. */
    expect(VIEWER).toContain("if (metres <= 0) return");
    const note = (en as Record<string, string>)["trace.colourNote"];
    expect(note).toContain("HĐ-8.2");
  });

  it("marks events on the path", () => {
    /* A collision and an arrival draw the same curve. */
    expect(VIEWER).toContain("trace.events");
    const note = (en as Record<string, string>)["trace.colourNote"];
    expect(note.toLowerCase()).toContain("collision");
  });

  it("unpacks the grid from bits instead of expecting an array", () => {
    /* 480x320 is 300 kB of JSON numbers and 19 kB packed. */
    expect(VIEWER).toContain("atob(bits)");
    expect(VIEWER).toContain("occupied_bits");
  });
});

describe("playback", () => {
  it("shows the whole path first and plays on request", () => {
    /* Opening at step 0 would show an empty map and read as a failed
       load. */
    expect(VIEWER).toContain("useState(trace.x.length - 1)");
  });

  it("resets when a different episode is loaded", () => {
    /* Leaving the slider where the previous episode ended would show a
       partial path for the new one, with nothing saying so. */
    expect(VIEWER).toContain("trace.episode_context_id, trace.candidate_id");
  });

  it("stops the timer when it reaches the end", () => {
    expect(VIEWER).toContain("setPlaying(false)");
    expect(VIEWER).toContain("clearInterval(timer)");
  });

  it("accepts one externally controlled clock and view mode", () => {
    expect(VIEWER).toContain("playbackTime?: number");
    expect(VIEWER).toContain('mode?: "flat" | "raised"');
    expect(VIEWER).toContain("frameIndexAt(timedFrames, playbackTime)");
    expect(DETAIL).toContain("<SharedPlayback");
    // One clock still drives both panels — but which clock depends on
    // the alignment: seconds in time-sync, and in progress-sync the
    // timestamp each run reached the same arc length at, which is a
    // *different* timestamp per side on purpose.
    expect(DETAIL).toContain("playbackTime={at}");
    expect(DETAIL).toContain('syncMode === "progress" ? sideTime(view, scan.time, side) : playback.time');
  });
});

describe("translation", () => {
  it("has every key the viewer asks for, in both locales", () => {
    const keys = new Set([...VIEWER.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    expect(keys.size).toBeGreaterThan(0);
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});

describe("the raised view draws the same room as the flat one", () => {
  it("hands the moving obstacles to the 2.5D scene", () => {
    /* **The raised view was drawing an empty room.** The flat canvas has
       drawn traffic since it arrived — it is the only thing on screen
       that explains a route bending around apparently empty floor — and
       the `Scene25D` call never passed it, so switching to 2.5D deleted
       exactly that. The scene builder wanted them all along: it turns
       each into a cylinder plus the keep-out and caution rings it
       derives from the same functions the flat view quotes. */
    expect(VIEWER).toContain("obstacles={obstaclesNow}");
    expect(VIEWER).toContain("trace.dynamic_obstacles ?? []");
  });

  it("reads each track at the frame on screen, clamped to its own end", () => {
    /* A track is shorter than the trace once it leaves the scenario.
       Reading past its end places an obstacle at `undefined`, which
       projects to the corner of the room rather than to nowhere — the
       same clamp the flat canvas already applies. */
    const snapshot = VIEWER.slice(VIEWER.indexOf("const obstaclesNow"));
    expect(snapshot).toContain("Math.min(visibleStep, track.x.length - 1)");
    expect(snapshot).toContain("if (step < 0) return []");
  });

  it("takes the radius the track declares rather than a constant", () => {
    /* Carts and pallets are not one size, and a fixed radius would draw
       a keep-out ring the planner never had. */
    expect(VIEWER).toContain("radius: track.radius_m");
  });
});

describe("the two 2.5D panels are one camera", () => {
  const SCENE = readFileSync(join(SRC, "components", "Scene25D.tsx"), "utf8");

  it("holds the angle where the pair is held, not inside each scene", () => {
    /* Each scene kept its own, so turning one panel to look behind a
       wall left the reader comparing two rooms until they matched the
       other by hand across three sliders — which nobody gets exactly
       right. It belongs where the scrubber lives: it is a property of
       the comparison, not of either candidate. */
    expect(DETAIL).toContain("const [view25d, setView25d] = useState(");
    expect(DETAIL).toContain("onView25dChange={setView25d}");
    expect(VIEWER).toContain("onViewChange={onView25dChange}");
  });

  it("lets the scene keep its own angle when nobody is listening", () => {
    /* The standalone viewer has no pair to sync with, and a control
       that reports upward to nothing would freeze. */
    expect(SCENE).toContain("const yaw = onViewChange ? yawDeg : localYaw;");
  });

  it("wires Rotate to the axis its label always implied", () => {
    /* It drove `azimuth`, which scales the horizontal half of a fixed
       dimetric fold: the room stretched sideways and never turned. */
    expect(SCENE).toContain("emit({ yawDeg: Number(event.target.value) })");
    expect(SCENE).not.toContain("setAzimuth(");
  });

  it("turns the whole way round rather than through a quadrant", () => {
    /* The old slider ran 5–85° because that was the range in which its
       dimetric fold stayed sane. A yaw has no such limit, and stopping
       at 85 would leave two of the room's four sides unreachable. */
    const rotate = SCENE.slice(SCENE.indexOf("Rotate"), SCENE.indexOf("Tilt"));
    expect(rotate).toContain("min={0}");
    expect(rotate).toContain("max={359}");
  });
});
