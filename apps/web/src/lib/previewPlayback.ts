/** Reading a preview's tracks at a moment, and moving that moment on.
 *
 * **The preview used to be one still frame.** An author typed a number
 * into `Time`, pressed Preview, and saw where the traffic stood at that
 * second — which answers "is the cart in my way at t = 12" and not
 * "where is it heading", the question somebody placing a start pose
 * actually has. Finding out meant typing 0, then 5, then 10, pressing
 * the button each time, and holding the difference in their head.
 *
 * So the backend now returns the whole route in one reply and this
 * plays it back. What it does **not** do is evaluate a motion law: every
 * position here was computed by the same `position_at` the simulator
 * runs. A second implementation in the browser would drift from it, and
 * a preview that disagrees with the episode is worse than no preview —
 * the author would place a start clear of a cart that is somewhere else
 * when the run happens.
 */

import type { Point2D } from "@/lib/types";

/** The part of a preview that can be played back.
 *
 * **Narrower than either reply that satisfies it, on purpose.** The
 * scenario editor's preview carries a validation verdict and the library
 * one carries the map it was built from; neither matters to "where is
 * the traffic at t". Naming only the fields that do lets both feed these
 * helpers without a cast, and stops a future field on one of them from
 * looking like something playback depends on. */
export interface PlayableTraffic {
  dynamic_obstacles: {
    name: string;
    radius: number;
    position: Point2D;
    track?: Point2D[];
  }[];
  duration?: number;
  step?: number;
}

/** Where an obstacle is at `seconds`, off its sampled track.
 *
 * **Interpolated, not snapped.** The track is sampled every `step`
 * seconds — a fifth of a second by default — and snapping to the nearest
 * sample makes a cart cross the room in visible jerks at exactly the
 * moment somebody is judging whether it clips the start pose. Straight
 * lines between samples are honest here: the samples are dense relative
 * to how fast these obstacles turn, so the line and the law differ by
 * less than the width of the dot being drawn.
 *
 * Falls back to the still frame when there is no track, which is what a
 * preview asked for without a duration carries.
 */
export function obstacleAt(
  track: readonly Point2D[],
  step: number,
  seconds: number,
  fallback: Point2D,
): Point2D {
  if (track.length === 0 || step <= 0) return fallback;
  if (track.length === 1) return track[0];

  const exact = Math.max(0, seconds) / step;
  const index = Math.floor(exact);
  // Past the end the obstacle stops where the track stops, rather than
  // vanishing. The track ends because sampling ended, not because the
  // cart did.
  if (index >= track.length - 1) return track[track.length - 1];

  const from = track[index];
  const to = track[index + 1];
  const fraction = exact - index;
  return {
    x: from.x + (to.x - from.x) * fraction,
    y: from.y + (to.y - from.y) * fraction,
  };
}

/** Every obstacle in a preview, at one moment. */
export function trafficAt(
  preview: PlayableTraffic | null,
  seconds: number,
): { name: string; radius: number; position: Point2D }[] {
  if (!preview) return [];
  return preview.dynamic_obstacles.map((obstacle) => ({
    name: obstacle.name,
    radius: obstacle.radius,
    position: obstacleAt(obstacle.track ?? [], preview.step ?? 0, seconds, obstacle.position),
  }));
}

/** How long a preview can be played for.
 *
 * Zero when the reply carries no track, which is how the caller knows to
 * offer no scrubber rather than one that cannot move.
 */
export function playableSeconds(preview: PlayableTraffic | null): number {
  return preview?.duration ?? 0;
}

/** The next playhead position, and whether playback has run out.
 *
 * Split from the timer so the wrap-around rule is testable. **It stops
 * at the end rather than looping**: a loop makes an author watching for
 * one moment — the instant a cart reaches the doorway — lose track of
 * whether they have seen it yet, and there is no cue for where the
 * repeat begins.
 */
export function advance(
  seconds: number,
  elapsed: number,
  duration: number,
): { seconds: number; running: boolean } {
  const next = seconds + elapsed;
  if (next >= duration) return { seconds: duration, running: false };
  return { seconds: next, running: true };
}
