"use client";

/** One episode's trajectory, drawn on the map it was driven on.
 *
 * **This is the evidence, and until now nothing could look at it.** One
 * Parquet file per (candidate, episode) is the sole input the Metrics
 * Engine has (HĐ-5); every number on a Decision Card comes out of it. A
 * platform that computes a gate verdict from a file nobody can open is
 * asking to be believed.
 *
 * What it draws, and why each part is there rather than decorative:
 *
 * - **The occupancy grid**, so a path that hugs a wall looks like one.
 * - **Clearance as colour along the path.** G2 bounds collisions and the
 *   safety objective anchors on clearance from the robot's *surface*, so
 *   the interesting part of a trajectory is where it ran close, not
 *   where it went. A single-colour line hides exactly that.
 * - **Events where they happened.** A collision and an arrival are the
 *   same shape of curve; only the marker tells them apart.
 * - **Start and goal**, because a path is otherwise a squiggle that
 *   might have been going the other way.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { useTranslation } from "@/lib/i18n";
import type { TracePayload } from "@/lib/decisions";

/** Cells to pixels, keeping the aspect ratio and fitting the box. */
function fit(map: TracePayload["map"], maxWidth: number, maxHeight: number): number {
  return Math.max(0.5, Math.min(maxWidth / map.width, maxHeight / map.height));
}

/** Unpack the base64 bit grid the API sends.
 *
 * One bit per cell rather than one JSON number: the reference hall is
 * 480x320, which is 300 kB of text as an array and 19 kB packed.
 */
function unpack(bits: string, count: number): Uint8Array {
  const binary = atob(bits);
  const cells = new Uint8Array(count);
  for (let index = 0; index < count; index += 1) {
    cells[index] = (binary.charCodeAt(index >> 3) >> (index & 7)) & 1;
  }
  return cells;
}

/** Clearance to a colour ramp.
 *
 * Zero is the collision boundary — `clearance_m` is measured from the
 * robot's surface (HĐ-8.2), so it is not a distance to a centre with a
 * radius still to subtract. Below one radius is where a run is spending
 * its safety margin, and that band is what the colour is for.
 */
function clearanceColour(metres: number, radius: number): string {
  if (!Number.isFinite(metres)) return "#94a3b8";
  if (metres <= 0) return "#dc2626";
  const ratio = Math.min(1, metres / Math.max(radius, 1e-6));
  // Red at the boundary through amber to blue at a full radius of room.
  const hue = 0 + ratio * 210;
  return `hsl(${hue.toFixed(0)}, 80%, 45%)`;
}

export function TraceViewer({ trace }: { trace: TracePayload }) {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [step, setStep] = useState(trace.x.length - 1);
  const [playing, setPlaying] = useState(false);

  const cells = useMemo(
    () => unpack(trace.map.occupied_bits, trace.map.width * trace.map.height),
    [trace.map.occupied_bits, trace.map.width, trace.map.height],
  );

  // A new trace is a new episode: start showing the whole path again
  // rather than leaving the slider where the previous one ended.
  useEffect(() => {
    setStep(trace.x.length - 1);
    setPlaying(false);
  }, [trace.episode_context_id, trace.candidate_id, trace.x.length]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setStep((current) => {
        if (current >= trace.x.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 30);
    return () => clearInterval(timer);
  }, [playing, trace.x.length]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const { map } = trace;
    const scale = fit(map, 720, 420);
    canvas.width = Math.round(map.width * scale);
    canvas.height = Math.round(map.height * scale);

    // World metres to canvas pixels. Screen y grows downward and world y
    // does not, so the flip is not optional — without it the drawing is
    // a mirror of the run.
    const toX = (metres: number) => ((metres - map.origin.x) / map.resolution) * scale;
    const toY = (metres: number) =>
      canvas.height - ((metres - map.origin.y) / map.resolution) * scale;

    context.fillStyle = "#f8fafc";
    context.fillRect(0, 0, canvas.width, canvas.height);

    context.fillStyle = "#334155";
    for (let row = 0; row < map.height; row += 1) {
      for (let column = 0; column < map.width; column += 1) {
        if (!cells[row * map.width + column]) continue;
        context.fillRect(
          column * scale,
          canvas.height - (row + 1) * scale,
          Math.ceil(scale),
          Math.ceil(scale),
        );
      }
    }

    for (const mission of trace.missions) {
      context.strokeStyle = "#0ea5e9";
      context.lineWidth = 2;
      context.beginPath();
      context.arc(toX(mission.start.x), toY(mission.start.y), 7, 0, Math.PI * 2);
      context.stroke();
      context.strokeStyle = "#16a34a";
      context.beginPath();
      context.arc(toX(mission.goal.x), toY(mission.goal.y), 7, 0, Math.PI * 2);
      context.stroke();
    }

    // Segment by segment, because the colour is the clearance and a
    // single stroked path could only carry one.
    context.lineWidth = 2.5;
    context.lineCap = "round";
    for (let index = 1; index <= step && index < trace.x.length; index += 1) {
      context.strokeStyle = clearanceColour(
        trace.clearance_m[index] ?? Number.NaN,
        trace.robot_radius_m,
      );
      context.beginPath();
      context.moveTo(toX(trace.x[index - 1]), toY(trace.y[index - 1]));
      context.lineTo(toX(trace.x[index]), toY(trace.y[index]));
      context.stroke();
    }

    for (const event of trace.events) {
      if (event.index > step) continue;
      context.fillStyle = "#dc2626";
      context.beginPath();
      context.arc(toX(trace.x[event.index]), toY(trace.y[event.index]), 5, 0, Math.PI * 2);
      context.fill();
    }

    // The robot at the current step, to its declared radius rather than
    // a dot — a path that "looks clear" at one pixel per cell may not be.
    if (step < trace.x.length) {
      const radius = (trace.robot_radius_m / map.resolution) * scale;
      context.strokeStyle = "#111827";
      context.lineWidth = 2;
      context.beginPath();
      context.arc(toX(trace.x[step]), toY(trace.y[step]), Math.max(radius, 2), 0, Math.PI * 2);
      context.stroke();
      context.beginPath();
      context.moveTo(toX(trace.x[step]), toY(trace.y[step]));
      context.lineTo(
        toX(trace.x[step] + Math.cos(trace.theta[step]) * trace.robot_radius_m * 1.8),
        toY(trace.y[step] + Math.sin(trace.theta[step]) * trace.robot_radius_m * 1.8),
      );
      context.stroke();
    }
  }, [trace, cells, step]);

  const clearance = trace.clearance_m[step];
  const latency = trace.planner_latency_ms[step];

  return (
    <div>
      <canvas ref={canvasRef} style={{ maxWidth: "100%", border: "1px solid var(--border)" }} />

      <div className="row" style={{ alignItems: "center", gap: 12, marginTop: 8 }}>
        <button type="button" onClick={() => setPlaying((current) => !current)}>
          {playing ? t("trace.pause") : t("trace.play")}
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(0, trace.x.length - 1)}
          value={step}
          onChange={(event) => {
            setPlaying(false);
            setStep(Number(event.target.value));
          }}
          style={{ flex: 1 }}
        />
        <span className="muted">
          {step + 1}/{trace.x.length} · {(trace.t[step] ?? 0).toFixed(1)} s
        </span>
      </div>

      <div className="stat-grid" style={{ marginTop: 12 }}>
        <Figure
          label={t("trace.clearance")}
          value={Number.isFinite(clearance) ? `${clearance.toFixed(3)} m` : "—"}
        />
        <Figure
          label={t("trace.latency")}
          value={Number.isFinite(latency) ? `${latency.toFixed(2)} ms` : "—"}
        />
        <Figure label={t("trace.duration")} value={`${(trace.t.at(-1) ?? 0).toFixed(1)} s`} />
        <Figure
          label={t("trace.outcome")}
          value={trace.events.at(-1)?.event ?? t("trace.noEvent")}
        />
      </div>

      <p className="muted" style={{ marginTop: 8 }}>
        {t("trace.colourNote")}
      </p>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <span className="stat-card-head">{label}</span>
      <span className="stat-card-value">{value}</span>
    </div>
  );
}
