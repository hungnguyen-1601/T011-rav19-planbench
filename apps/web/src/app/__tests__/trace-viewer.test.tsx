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
  it("is placed under the gate table, above the recommendation", () => {
    /* A row saying "G3: fail" is a claim about episodes; the next thing
       a reader should be able to do is open one. Below the card instead,
       a trajectory becomes an illustration of a conclusion rather than
       the thing the conclusion came from. */
    expect(DETAIL.indexOf("<TracePanel")).toBeGreaterThan(DETAIL.indexOf("<GateTable"));
    expect(DETAIL.indexOf("<TracePanel")).toBeLessThan(DETAIL.indexOf("<Outcome"));
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
