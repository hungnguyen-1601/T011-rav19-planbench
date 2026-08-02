"use client";

/** 2.5D view of a map, plan, trajectory and robot.
 *
 * Rendering only. Every polygon comes from `lib/scene25d`, which is pure
 * and unit-tested; this file decides colours and strokes and nothing
 * else. No simulation quantity is computed here (project rule: no
 * simulator logic in the UI).
 *
 * The renderer is Canvas 2D rather than WebGL. For an extruded
 * occupancy grid the scene is a few thousand convex quads with a total
 * depth order, which the painter's algorithm handles exactly — and it
 * adds no dependency. Swapping in a WebGL renderer later means
 * replacing this file alone: the scene it consumes stays the same.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  DEFAULT_PROJECTION,
  buildScene,
  fitProjection,
  type Facet,
  type FacetKind,
  type SceneOptions,
} from "@/lib/scene25d";
import type { MapData } from "@/lib/types";

export interface Scene25DProps extends SceneOptions {
  map: MapData;
  width?: number;
  height?: number;
  /** Degrees; the control strip writes these back. */
  azimuthDeg?: number;
  elevationDeg?: number;
  showControls?: boolean;
  showPlan?: boolean;
  showTrajectory?: boolean;
}

/** Face shading: one base colour per cell kind, dimmed per face. */
const FILL: Record<FacetKind, { top: string; left: string; right: string }> = {
  ground: { top: "#1b2029", left: "#151a22", right: "#11151c" },
  occupied: { top: "#7d90a6", left: "#54637a", right: "#3f4c60" },
  unknown: { top: "#33383f", left: "#2a2e35", right: "#22262c" },
};

const COLOR = {
  plan: "#4c9aff",
  trajectory: "#3fb950",
  start: "#3fb950",
  goal: "#d24d9a",
  robot: "#e6e9ef",
  robotSide: "#9aa3b2",
  heading: "#f0b429",
  outline: "rgba(0,0,0,0.25)",
  obstacle: "#ff6b6b",
  obstacleSide: "#c0454a",
};

export function Scene25D({
  map,
  width = 760,
  height = 520,
  azimuthDeg = 45,
  elevationDeg = 30,
  showControls = true,
  showPlan = true,
  showTrajectory = true,
  wallHeight = 0.6,
  robotHeight = 0.35,
  showGround = true,
  startPose,
  goalPose,
  robotPose,
  robotRadius = 0.3,
  plannedPath,
  trajectory,
  obstacles,
}: Scene25DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [azimuth, setAzimuth] = useState(azimuthDeg);
  const [elevation, setElevation] = useState(elevationDeg);
  const [height3d, setHeight3d] = useState(wallHeight);

  const scene = useMemo(() => {
    const projection = fitProjection(map, width, height, {
      azimuth: (azimuth * Math.PI) / 180,
      elevation: (elevation * Math.PI) / 180,
      wallHeight: height3d,
    });
    return buildScene(map, projection, {
      wallHeight: height3d,
      robotHeight,
      showGround,
      startPose,
      goalPose,
      robotPose,
      robotRadius,
      plannedPath,
      trajectory,
      obstacles,
    });
  }, [
    map,
    width,
    height,
    azimuth,
    elevation,
    height3d,
    robotHeight,
    showGround,
    startPose,
    goalPose,
    robotPose,
    robotRadius,
    plannedPath,
    trajectory,
    obstacles,
  ]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // Facets arrive back-to-front, so a plain sequential fill resolves
    // occlusion without a depth buffer.
    for (const facet of scene.facets) {
      fillFacet(ctx, facet);
    }

    if (showPlan && scene.plan.length > 1) {
      ctx.strokeStyle = COLOR.plan;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      strokePolyline(ctx, scene.plan);
      ctx.setLineDash([]);
    }

    if (showTrajectory && scene.trajectory.length > 1) {
      ctx.strokeStyle = COLOR.trajectory;
      ctx.lineWidth = 2.5;
      strokePolyline(ctx, scene.trajectory);
    }

    if (scene.start) marker(ctx, scene.start, COLOR.start, "start");
    if (scene.goal) marker(ctx, scene.goal, COLOR.goal, "goal");

    if (scene.robot) {
      const { base, top, heading, radiusX, radiusY } = scene.robot;
      // A short column so the robot reads as standing on the floor
      // rather than painted onto it.
      ctx.strokeStyle = COLOR.robotSide;
      ctx.lineWidth = Math.max(2, radiusX * 0.6);
      ctx.beginPath();
      ctx.moveTo(base.sx, base.sy);
      ctx.lineTo(top.sx, top.sy);
      ctx.stroke();

      ctx.fillStyle = COLOR.robot;
      ctx.beginPath();
      ctx.ellipse(top.sx, top.sy, Math.max(2, radiusX), Math.max(1.5, radiusY), 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = COLOR.heading;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(top.sx, top.sy);
      ctx.lineTo(heading.sx, heading.sy);
      ctx.stroke();
    }

    for (const obstacle of scene.obstacles) {
      const { base, top, radiusX, radiusY } = obstacle;
      ctx.strokeStyle = COLOR.obstacleSide;
      ctx.lineWidth = Math.max(2, radiusX * 0.6);
      ctx.beginPath();
      ctx.moveTo(base.sx, base.sy);
      ctx.lineTo(top.sx, top.sy);
      ctx.stroke();

      ctx.fillStyle = COLOR.obstacle;
      ctx.beginPath();
      ctx.ellipse(top.sx, top.sy, Math.max(2, radiusX), Math.max(1.5, radiusY), 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [scene, width, height, showPlan, showTrajectory]);

  return (
    <div className="scene25d">
      <canvas ref={canvasRef} data-testid="scene-25d" />
      {showControls ? (
        <div className="scene25d-controls">
          <label>
            Rotate
            <input
              type="range"
              min={5}
              max={85}
              value={azimuth}
              onChange={(event) => setAzimuth(Number(event.target.value))}
            />
            <span className="muted">{azimuth}°</span>
          </label>
          <label>
            Tilt
            <input
              type="range"
              min={0}
              max={89}
              value={elevation}
              onChange={(event) => setElevation(Number(event.target.value))}
            />
            <span className="muted">
              {elevation}°{elevation >= 88 ? " (top-down)" : ""}
            </span>
          </label>
          <label>
            Wall height
            <input
              type="range"
              min={0}
              max={20}
              value={Math.round(height3d * 10)}
              onChange={(event) => setHeight3d(Number(event.target.value) / 10)}
            />
            <span className="muted">{height3d.toFixed(1)} m</span>
          </label>
        </div>
      ) : null}
    </div>
  );
}

function fillFacet(ctx: CanvasRenderingContext2D, facet: Facet): void {
  ctx.fillStyle = FILL[facet.kind][facet.face];
  ctx.beginPath();
  facet.points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.sx, point.sy);
    else ctx.lineTo(point.sx, point.sy);
  });
  ctx.closePath();
  ctx.fill();
  if (facet.kind === "occupied") {
    // Hairline seams stop adjacent walls from merging into one blob.
    ctx.strokeStyle = COLOR.outline;
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }
}

function strokePolyline(
  ctx: CanvasRenderingContext2D,
  points: { sx: number; sy: number }[],
): void {
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.sx, point.sy);
    else ctx.lineTo(point.sx, point.sy);
  });
  ctx.stroke();
}

function marker(
  ctx: CanvasRenderingContext2D,
  point: { sx: number; sy: number },
  color: string,
  label: string,
): void {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(point.sx, point.sy, 9, 5, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.font = "11px ui-sans-serif, system-ui";
  ctx.fillText(label, point.sx + 11, point.sy - 6);
}
