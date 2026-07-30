"use client";

/** Canvas 2D renderer for map, plan, trajectory and robot.
 *
 * Rendering only — it never computes metrics or simulation state; those
 * come from the backend (project rule: no simulator logic in the UI).
 */

import { useCallback, useEffect, useRef } from "react";
import { OCCUPIED, UNKNOWN } from "@/lib/demoMap";
import { canvasToWorld, fitViewport, type Viewport } from "@/lib/transform";
import type { MapData, Point2D, Pose2D, TrajectoryPoint } from "@/lib/types";

export interface MapCanvasProps {
  map: MapData;
  width?: number;
  height?: number;
  startPose?: Pose2D;
  goalPose?: Pose2D;
  goalTolerance?: number;
  robotRadius?: number;
  plannedPath?: Point2D[];
  trajectory?: TrajectoryPoint[];
  robotPose?: Pose2D | null;
  collisionPoint?: Point2D | null;
  showGrid?: boolean;
  showPlan?: boolean;
  showTrajectory?: boolean;
  onWorldClick?: (x: number, y: number, event: React.MouseEvent<HTMLCanvasElement>) => void;
  onWorldDrag?: (x: number, y: number) => void;
}

const COLOR = {
  occupied: "#5b6c7f",
  unknown: "#33383f",
  gridLine: "rgba(255,255,255,0.045)",
  plan: "#4c9aff",
  trajectory: "#3fb950",
  robot: "#e6e9ef",
  heading: "#f0b429",
  start: "#3fb950",
  goal: "#d24d9a",
  collision: "#f85149",
};

export function MapCanvas({
  map,
  width = 760,
  height = 560,
  startPose,
  goalPose,
  goalTolerance = 0.3,
  robotRadius = 0.3,
  plannedPath,
  trajectory,
  robotPose,
  collisionPoint,
  showGrid = true,
  showPlan = true,
  showTrajectory = true,
  onWorldClick,
  onWorldDrag,
}: MapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const draggingRef = useRef(false);

  const viewport: Viewport = fitViewport(map, width, height);

  const toCanvas = useCallback(
    (x: number, y: number): [number, number] => [
      viewport.offsetX + x * viewport.scale,
      viewport.offsetY - y * viewport.scale,
    ],
    [viewport.offsetX, viewport.offsetY, viewport.scale],
  );

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

    const cell = map.resolution * viewport.scale;

    // Occupancy cells (row 0 is the bottom row in world space).
    for (let row = 0; row < map.height; row += 1) {
      for (let col = 0; col < map.width; col += 1) {
        const value = map.cells[row * map.width + col];
        if (value === 0) continue;
        const [cx, cy] = toCanvas(
          map.origin.x + col * map.resolution,
          map.origin.y + (row + 1) * map.resolution,
        );
        ctx.fillStyle = value === OCCUPIED ? COLOR.occupied : value === UNKNOWN ? COLOR.unknown : "transparent";
        ctx.fillRect(cx, cy, cell + 0.5, cell + 0.5);
      }
    }

    // Map background border.
    const [bx, by] = toCanvas(map.origin.x, map.origin.y + map.height * map.resolution);
    ctx.strokeStyle = "#2a2f3a";
    ctx.lineWidth = 1;
    ctx.strokeRect(bx, by, map.width * cell, map.height * cell);

    if (showGrid && cell >= 6) {
      ctx.strokeStyle = COLOR.gridLine;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let col = 0; col <= map.width; col += 1) {
        const [x, y0] = toCanvas(map.origin.x + col * map.resolution, map.origin.y);
        const [, y1] = toCanvas(0, map.origin.y + map.height * map.resolution);
        ctx.moveTo(x, y0);
        ctx.lineTo(x, y1);
      }
      for (let row = 0; row <= map.height; row += 1) {
        const [x0, y] = toCanvas(map.origin.x, map.origin.y + row * map.resolution);
        const [x1] = toCanvas(map.origin.x + map.width * map.resolution, 0);
        ctx.moveTo(x0, y);
        ctx.lineTo(x1, y);
      }
      ctx.stroke();
    }

    if (showPlan && plannedPath && plannedPath.length > 1) {
      ctx.strokeStyle = COLOR.plan;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      plannedPath.forEach((point, index) => {
        const [x, y] = toCanvas(point.x, point.y);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COLOR.plan;
      for (const point of plannedPath) {
        const [x, y] = toCanvas(point.x, point.y);
        ctx.beginPath();
        ctx.arc(x, y, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (showTrajectory && trajectory && trajectory.length > 1) {
      ctx.strokeStyle = COLOR.trajectory;
      ctx.lineWidth = 2;
      ctx.beginPath();
      trajectory.forEach((point, index) => {
        const [x, y] = toCanvas(point.x, point.y);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    const marker = (pose: Pose2D, color: string, radius: number, label: string) => {
      const [x, y] = toCanvas(pose.x, pose.y);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(4, radius * viewport.scale), 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.font = "11px ui-sans-serif, system-ui";
      ctx.fillText(label, x + 8, y - 8);
    };

    if (startPose) marker(startPose, COLOR.start, robotRadius, "start");
    if (goalPose) marker(goalPose, COLOR.goal, goalTolerance, "goal");

    if (robotPose) {
      const [x, y] = toCanvas(robotPose.x, robotPose.y);
      const r = Math.max(3, robotRadius * viewport.scale);
      ctx.fillStyle = COLOR.robot;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = COLOR.heading;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(robotPose.theta) * r * 1.9, y - Math.sin(robotPose.theta) * r * 1.9);
      ctx.stroke();
    }

    if (collisionPoint) {
      const [x, y] = toCanvas(collisionPoint.x, collisionPoint.y);
      ctx.strokeStyle = COLOR.collision;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(x - 7, y - 7);
      ctx.lineTo(x + 7, y + 7);
      ctx.moveTo(x + 7, y - 7);
      ctx.lineTo(x - 7, y + 7);
      ctx.stroke();
    }
  }, [
    map,
    width,
    height,
    startPose,
    goalPose,
    goalTolerance,
    robotRadius,
    plannedPath,
    trajectory,
    robotPose,
    collisionPoint,
    showGrid,
    showPlan,
    showTrajectory,
    toCanvas,
    viewport.scale,
  ]);

  const pointerWorld = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return canvasToWorld(viewport, event.clientX - rect.left, event.clientY - rect.top);
  };

  return (
    <canvas
      ref={canvasRef}
      data-testid="map-canvas"
      onMouseDown={(event) => {
        draggingRef.current = true;
        const { x, y } = pointerWorld(event);
        onWorldClick?.(x, y, event);
      }}
      onMouseMove={(event) => {
        if (!draggingRef.current || !onWorldDrag) return;
        const { x, y } = pointerWorld(event);
        onWorldDrag(x, y);
      }}
      onMouseUp={() => {
        draggingRef.current = false;
      }}
      onMouseLeave={() => {
        draggingRef.current = false;
      }}
    />
  );
}
