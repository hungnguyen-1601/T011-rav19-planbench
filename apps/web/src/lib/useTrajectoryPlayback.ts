"use client";

/** Client-side playback over a *saved* trajectory (F08).
 *
 * The live simulation page streams frames over a WebSocket and owns its
 * playhead server-side; a stored episode is the opposite case — every
 * frame is already in memory, so playback is purely presentational.
 * This hook is deliberately separate from `useEpisodeStream`: coupling
 * the two would make the WS hook carry a mode it never uses, and a bug
 * in replay must not be able to touch live simulation.
 *
 * The clock advances with `requestAnimationFrame` in *simulation* time:
 * `playhead += wallDelta × speed`, clamped to the episode duration.
 * Playback never interpolates between frames — the robot is drawn at
 * the last recorded sample ≤ playhead, so the picture only ever shows
 * states the simulator actually produced.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TrajectoryPoint } from "./types";

export interface TrajectoryPlayback {
  /** Current position of the clock, seconds of simulation time. */
  playhead: number;
  /** Episode length in seconds (time of the last sample; 0 when empty). */
  duration: number;
  playing: boolean;
  speed: number;
  /** Index into the trajectory of the sample being shown, -1 when empty. */
  frameIndex: number;
  /** The sample being shown, null when the trajectory is empty. */
  frame: TrajectoryPoint | null;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (time: number) => void;
  setSpeed: (speed: number) => void;
}

/** Last index whose time ≤ t (binary search; -1 when none). */
function frameAt(trajectory: TrajectoryPoint[], t: number): number {
  let low = 0;
  let high = trajectory.length - 1;
  let found = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (trajectory[mid].time <= t + 1e-9) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return found;
}

export function useTrajectoryPlayback(trajectory: TrajectoryPoint[]): TrajectoryPlayback {
  const duration = trajectory.length > 0 ? trajectory[trajectory.length - 1].time : 0;
  // Start at the end, paused: the full picture first (same information
  // the static view used to show), then play restarts from zero.
  const [playhead, setPlayhead] = useState(duration);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);

  // A new episode resets the clock — keeping the old playhead would show
  // a frame from one run on the map of another.
  useEffect(() => {
    setPlaying(false);
    setPlayhead(duration);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trajectory]);

  useEffect(() => {
    if (!playing) {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastTickRef.current = null;
      return;
    }
    const tick = (now: number) => {
      const last = lastTickRef.current ?? now;
      lastTickRef.current = now;
      const delta = ((now - last) / 1000) * speed;
      setPlayhead((current) => {
        const next = current + delta;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastTickRef.current = null;
    };
  }, [playing, speed, duration]);

  const play = useCallback(() => {
    if (duration <= 0) return;
    // Play at the end means "watch it again".
    setPlayhead((current) => (current >= duration - 1e-9 ? 0 : current));
    setPlaying(true);
  }, [duration]);

  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => {
    if (playing) pause();
    else play();
  }, [playing, play, pause]);

  const seek = useCallback(
    (time: number) => {
      setPlayhead(Math.min(Math.max(time, 0), duration));
    },
    [duration],
  );

  const frameIndex = useMemo(() => frameAt(trajectory, playhead), [trajectory, playhead]);
  const frame = frameIndex >= 0 ? trajectory[frameIndex] : null;

  return { playhead, duration, playing, speed, frameIndex, frame, play, pause, toggle, seek, setSpeed };
}
