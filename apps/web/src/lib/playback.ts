/** Client-side playback clock over a recorded trajectory (pure logic).
 *
 * Frames arrive from the WebSocket in bulk (server streams fast); the
 * UI paces them locally so pause/resume/speed work without renegotiating
 * the socket.
 */

import type { TrajectoryPoint } from "./types";

/** Index of the last frame with time <= playbackTime (-1 before start). */
export function frameIndexAt(frames: readonly { time: number }[], playbackTime: number): number {
  let low = 0;
  let high = frames.length - 1;
  let result = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (frames[mid].time <= playbackTime) {
      result = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return result;
}

export interface PlaybackState {
  playing: boolean;
  /** Simulation-time position of the playhead, seconds. */
  time: number;
  speed: number;
}

export const initialPlayback: PlaybackState = { playing: false, time: 0, speed: 1 };

/** Advance the playhead by realDelta seconds of wall time. */
export function tick(
  state: PlaybackState,
  realDeltaSeconds: number,
  duration: number,
): PlaybackState {
  if (!state.playing) {
    return state;
  }
  const time = state.time + realDeltaSeconds * state.speed;
  if (time >= duration) {
    return { ...state, time: duration, playing: false };
  }
  return { ...state, time };
}

export function trajectoryDuration(trajectory: readonly TrajectoryPoint[]): number {
  return trajectory.length > 0 ? trajectory[trajectory.length - 1].time : 0;
}
