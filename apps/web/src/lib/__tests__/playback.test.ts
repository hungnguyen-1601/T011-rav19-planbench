import { describe, expect, it } from "vitest";
import { frameIndexAt, initialPlayback, tick, trajectoryDuration } from "../playback";
import type { TrajectoryPoint } from "../types";

const frames = [0, 0.05, 0.1, 0.15, 0.2].map((time) => ({ time }));

describe("frameIndexAt", () => {
  it("returns -1 before the first frame", () => {
    expect(frameIndexAt(frames, -0.01)).toBe(-1);
  });

  it("finds the last frame at or before the playhead", () => {
    expect(frameIndexAt(frames, 0)).toBe(0);
    expect(frameIndexAt(frames, 0.07)).toBe(1);
    expect(frameIndexAt(frames, 0.1)).toBe(2);
    expect(frameIndexAt(frames, 5)).toBe(4);
  });

  it("handles an empty list", () => {
    expect(frameIndexAt([], 1)).toBe(-1);
  });
});

describe("tick", () => {
  it("does nothing while paused", () => {
    const state = { ...initialPlayback, playing: false, time: 1 };
    expect(tick(state, 0.5, 10)).toBe(state);
  });

  it("advances by real time scaled by speed", () => {
    const state = { playing: true, time: 1, speed: 2 };
    expect(tick(state, 0.5, 10).time).toBeCloseTo(2, 9);
  });

  it("clamps at the end and stops playing", () => {
    const state = { playing: true, time: 9.9, speed: 1 };
    const next = tick(state, 1, 10);
    expect(next.time).toBe(10);
    expect(next.playing).toBe(false);
  });
});

describe("trajectoryDuration", () => {
  it("is the last frame time", () => {
    const trajectory = [
      { time: 0, x: 0, y: 0, theta: 0, linear_velocity: 0, angular_velocity: 0 },
      { time: 1.5, x: 1, y: 0, theta: 0, linear_velocity: 1, angular_velocity: 0 },
    ] satisfies TrajectoryPoint[];
    expect(trajectoryDuration(trajectory)).toBe(1.5);
  });

  it("is zero for an empty trajectory", () => {
    expect(trajectoryDuration([])).toBe(0);
  });
});
