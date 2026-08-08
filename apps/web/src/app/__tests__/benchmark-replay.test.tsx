import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** F08 — playback of saved episodes on the benchmark detail page.
 *
 * The test environment is Node without jsdom, so like the chart tests
 * these are source-level assertions: they pin the wiring that makes
 * replay a playback rather than a still image, and the invariants a
 * refactor is most likely to lose.
 */

const APP = join(__dirname, "..");
const PAGE = readFileSync(join(APP, "benchmarks", "[id]", "page.tsx"), "utf8");
const HOOK = readFileSync(join(APP, "..", "lib", "useTrajectoryPlayback.ts"), "utf8");

describe("the replay panel plays back the saved trajectory", () => {
  it("uses the playback hook instead of pinning the last frame", () => {
    expect(PAGE).toContain("useTrajectoryPlayback");
    // The robot pose comes from the playhead, never pinned to the last
    // frame the way the old still image was.
    expect(PAGE).not.toMatch(/robotPose=\{\s*replay\.trajectory\[/);
    expect(PAGE).toContain("robotPose={playback.frame}");
  });

  it("has a scrubber, play/pause and speed control", () => {
    expect(PAGE).toContain('type="range"');
    expect(PAGE).toContain("playback.toggle");
    expect(PAGE).toContain("playback.seek");
    expect(PAGE).toContain("playback.setSpeed");
    expect(PAGE).toContain('t("simulate.pause")');
  });

  it("only draws the past: trajectory is truncated at the playhead", () => {
    expect(PAGE).toContain("slice(0, playback.frameIndex + 1)");
  });

  it("draws the recorded obstacle snapshot of the current frame", () => {
    expect(PAGE).toContain("playback.frame?.obstacles");
    expect(PAGE).toContain("dynamicObstacles={obstacleMarkers}");
  });

  it("marks the collision on the timeline", () => {
    expect(PAGE).toContain("detail.collisionAt");
  });

  it("marks every replan on the timeline, read from the events", () => {
    // A replan leaves no trace in the trajectory samples — that is why
    // the engine emits an event for it — so the marker must come from
    // `replay.events` and not from anything inferred about the path.
    expect(PAGE).toContain('event.type === "replan"');
    expect(PAGE).toContain("detail.replanAt");
    expect(PAGE).toContain("replanTimes.map");
  });
});

describe("the playback hook", () => {
  it("is separate from the live-simulation stream hook", () => {
    expect(HOOK).not.toContain("new WebSocket");
    expect(HOOK).not.toMatch(/import.*useEpisodeStream/);
    const SIMULATE = readFileSync(join(APP, "simulate", "page.tsx"), "utf8");
    expect(SIMULATE).not.toContain("useTrajectoryPlayback");
  });

  it("never shows a state the simulator did not produce", () => {
    // Frame selection is the last sample at or before the playhead —
    // no interpolation between samples.
    expect(HOOK).toContain("frameAt");
    expect(HOOK).not.toContain("lerp");
  });

  it("advances in simulation time scaled by speed and clamps at the end", () => {
    expect(HOOK).toContain("requestAnimationFrame");
    expect(HOOK).toContain("* speed");
    expect(HOOK).toContain("setPlaying(false)");
  });
});
