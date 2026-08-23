/** Reading a preview's tracks at a moment, and moving that moment on.
 *
 * The rules worth being wrong about are all here rather than in the
 * component: where an obstacle is between two samples, what happens
 * past the end of a track, and whether a reply with no track still
 * draws.
 */

import { describe, expect, it } from "vitest";

import { advance, obstacleAt, playableSeconds, trafficAt } from "@/lib/previewPlayback";
import type { ScenarioPreview } from "@/lib/types";

const TRACK = [
  { x: 0, y: 0 },
  { x: 2, y: 0 },
  { x: 4, y: 0 },
];
const FALLBACK = { x: 99, y: 99 };

describe("where an obstacle is at a moment", () => {
  it("lands on a sample exactly", () => {
    expect(obstacleAt(TRACK, 1, 1, FALLBACK)).toEqual({ x: 2, y: 0 });
  });

  it("interpolates between two samples rather than snapping", () => {
    /* Snapping to the nearest sample makes a cart cross the room in
       visible jerks at exactly the moment somebody is judging whether
       it clips the start pose. */
    expect(obstacleAt(TRACK, 1, 0.5, FALLBACK)).toEqual({ x: 1, y: 0 });
    expect(obstacleAt(TRACK, 1, 1.25, FALLBACK)).toEqual({ x: 2.5, y: 0 });
  });

  it("stops where the track stops rather than vanishing", () => {
    /* The track ends because sampling ended, not because the cart
       did. */
    expect(obstacleAt(TRACK, 1, 99, FALLBACK)).toEqual({ x: 4, y: 0 });
  });

  it("never reads before the start", () => {
    expect(obstacleAt(TRACK, 1, -5, FALLBACK)).toEqual({ x: 0, y: 0 });
  });

  it("falls back to the still frame when there is no track", () => {
    /* A reply asked for one instant, and a reply from a server that
       predates playback, both look like this. Neither may draw
       nothing. */
    expect(obstacleAt([], 1, 3, FALLBACK)).toBe(FALLBACK);
    expect(obstacleAt(TRACK, 0, 3, FALLBACK)).toBe(FALLBACK);
  });
});

describe("the whole preview at a moment", () => {
  const preview = (over: Partial<ScenarioPreview> = {}): ScenarioPreview =>
    ({
      time: 0,
      seed: 0,
      valid: true,
      errors: [],
      duration: 2,
      step: 1,
      dynamic_obstacles: [
        { name: "cart", radius: 0.4, position: FALLBACK, track: TRACK },
      ],
      ...over,
    }) as ScenarioPreview;

  it("moves every obstacle to the playhead", () => {
    expect(trafficAt(preview(), 0.5)[0].position).toEqual({ x: 1, y: 0 });
  });

  it("keeps the radius and the name, which do not move", () => {
    const drawn = trafficAt(preview(), 1)[0];
    expect(drawn).toMatchObject({ name: "cart", radius: 0.4 });
  });

  it("draws the still frame from a reply that carries no track", () => {
    const still = preview({
      duration: 0,
      step: 0,
      dynamic_obstacles: [{ name: "cart", radius: 0.4, position: FALLBACK }],
    } as Partial<ScenarioPreview>);
    expect(trafficAt(still, 7)[0].position).toBe(FALLBACK);
  });

  it("draws nothing at all without a preview", () => {
    expect(trafficAt(null, 3)).toEqual([]);
  });

  it("reports nothing playable when the reply is a single frame", () => {
    /* How the caller knows to offer no scrubber, rather than one that
       cannot move. */
    expect(playableSeconds(preview({ duration: 0 }))).toBe(0);
    expect(playableSeconds(null)).toBe(0);
  });
});

describe("moving the playhead", () => {
  it("counts real seconds rather than a fixed step per frame", () => {
    expect(advance(1, 0.25, 10)).toEqual({ seconds: 1.25, running: true });
  });

  it("stops at the end instead of looping", () => {
    /* An author watching for one moment — the instant a cart reaches
       the doorway — loses track of whether they have seen it once the
       picture starts over with no cue for where the repeat began. */
    expect(advance(9.9, 0.5, 10)).toEqual({ seconds: 10, running: false });
  });

  it("never runs past the end even on a long frame", () => {
    /* A backgrounded tab hands back one frame a second. */
    expect(advance(0, 60, 10).seconds).toBe(10);
  });
});
