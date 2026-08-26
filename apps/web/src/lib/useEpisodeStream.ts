"use client";

/** Receive an episode over WebSocket and pace its display locally.
 *
 * The socket delivers the episode recorded by the backend (see D16 in
 * docs/architecture.md); the client keeps a playhead so pause, resume,
 * speed and scrub work without renegotiating the connection.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";
import { frameIndexAt, trajectoryDuration } from "./playback";
import type { EpisodeMetrics, Point2D, TrajectoryPoint, WsMessage } from "./types";

export type StreamPhase = "idle" | "connecting" | "streaming" | "complete" | "error";

export interface EpisodeStream {
  phase: StreamPhase;
  frames: TrajectoryPoint[];
  planPath: Point2D[];
  metrics: EpisodeMetrics | null;
  status: string | null;
  reason: string | null;
  error: string | null;
  playing: boolean;
  playhead: number; // simulation seconds
  duration: number;
  speed: number;
  currentFrame: TrajectoryPoint | null;
  connect: (simulationId: string) => void;
  play: () => void;
  pause: () => void;
  stop: () => void;
  reset: () => void;
  seek: (time: number) => void;
  setSpeed: (speed: number) => void;
}

export function useEpisodeStream(): EpisodeStream {
  const [phase, setPhase] = useState<StreamPhase>("idle");
  const [frames, setFrames] = useState<TrajectoryPoint[]>([]);
  const [planPath, setPlanPath] = useState<Point2D[]>([]);
  const [metrics, setMetrics] = useState<EpisodeMetrics | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [speed, setSpeed] = useState(1);

  const socketRef = useRef<WebSocket | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);
  const framesRef = useRef<TrajectoryPoint[]>([]);
  const speedRef = useRef(1);

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  const closeSocket = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
  }, []);

  useEffect(
    () => () => {
      closeSocket();
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [closeSocket],
  );

  const connect = useCallback(
    (simulationId: string) => {
      closeSocket();
      framesRef.current = [];
      setFrames([]);
      setPlanPath([]);
      setMetrics(null);
      setStatus(null);
      setReason(null);
      setError(null);
      setPlayhead(0);
      setPhase("connecting");

      // pace=false: receive the whole episode promptly, pace it locally.
      const socket = new WebSocket(wsUrl(simulationId, false));
      socketRef.current = socket;

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data as string) as WsMessage;
        switch (message.type) {
          case "start":
            setPlanPath(message.plan_path);
            setPhase("streaming");
            setPlaying(true);
            lastTickRef.current = null;
            break;
          case "state": {
            const frame: TrajectoryPoint = {
              time: message.time,
              x: message.x,
              y: message.y,
              theta: message.theta,
              linear_velocity: message.linear_velocity,
              angular_velocity: message.angular_velocity,
              obstacles: message.obstacles,
            };
            framesRef.current = [...framesRef.current, frame];
            setFrames(framesRef.current);
            break;
          }
          case "result":
            setMetrics(message.metrics);
            setStatus(message.status);
            setReason(message.reason);
            setPhase("complete");
            break;
          case "error":
            setError(`${message.code}: ${message.message}`);
            setPhase("error");
            setPlaying(false);
            break;
        }
      };
      socket.onerror = () => {
        setError("WebSocket connection failed");
        setPhase("error");
        setPlaying(false);
      };
    },
    [closeSocket],
  );

  const duration = trajectoryDuration(frames);

  // Local playhead clock.
  useEffect(() => {
    if (!playing) {
      lastTickRef.current = null;
      return;
    }
    const step = (timestamp: number) => {
      const previous = lastTickRef.current;
      lastTickRef.current = timestamp;
      if (previous !== null) {
        const deltaSeconds = (timestamp - previous) / 1000;
        setPlayhead((current) => {
          const available = trajectoryDuration(framesRef.current);
          const next = current + deltaSeconds * speedRef.current;
          if (next >= available) {
            return available;
          }
          return next;
        });
      }
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [playing]);

  // Stop automatically once the playhead reaches the end of a complete episode.
  useEffect(() => {
    if (phase === "complete" && playing && duration > 0 && playhead >= duration) {
      setPlaying(false);
    }
  }, [phase, playing, playhead, duration]);

  const index = frameIndexAt(frames, playhead);
  const currentFrame = index >= 0 ? frames[index] : (frames[0] ?? null);

  return {
    phase,
    frames,
    planPath,
    metrics,
    status,
    reason,
    error,
    playing,
    playhead,
    duration,
    speed,
    currentFrame,
    connect,
    play: () => setPlaying(true),
    pause: () => setPlaying(false),
    stop: () => {
      setPlaying(false);
      closeSocket();
    },
    reset: () => {
      setPlayhead(0);
      setPlaying(false);
    },
    seek: (time: number) => setPlayhead(Math.max(0, Math.min(time, duration))),
    setSpeed,
  };
}
