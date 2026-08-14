"use client";

/** Canvas 2D renderer for map, plan, trajectory and robot.
 *
 * Rendering only — it never computes metrics or simulation state; those
 * come from the backend (project rule: no simulator logic in the UI).
 */

import { useCallback, useEffect, useRef } from "react";
import { OCCUPIED, UNKNOWN } from "@/lib/demoMap";
import { KEEP_OUT_FILL, KEEP_OUT_STROKE, keepOutRadius } from "@/lib/keepOut";
import { canvasToWorld, fitViewport, type Viewport } from "@/lib/transform";
import type { MapData, Point2D, Pose2D, StaticObstacle, TrajectoryPoint } from "@/lib/types";

/** One moving obstacle, already resolved to a position.
 *
 * The canvas takes a *position*, not a motion law. Evaluating motion in
 * the browser would be a second implementation of the simulator's, and
 * the two would drift; every position drawn here comes from the backend
 * (`POST /scenarios/preview` in the editor, the episode stream in
 * replay), so the picture cannot disagree with the run.
 */
export interface ObstacleMarker {
  name: string;
  radius: number;
  position: Point2D;
}

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
  /** Static obstacles as authored: circles and axis-aligned rectangles.
   *  Pure geometry, so the canvas can draw these itself. */
  staticObstacles?: StaticObstacle[];
  /** Moving obstacles at one instant — see {@link ObstacleMarker}. */
  dynamicObstacles?: ObstacleMarker[];
  /** The instant `dynamicObstacles` describes, in seconds, for the label.
   *  The editor passes the scrubber position; replay passes the playhead. */
  previewTime?: number;
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
  // Static obstacles read as part of the world, like walls; moving ones
  // are warm and outlined, because where they are is a fact about one
  // instant and one seed, not about the map.
  staticObstacle: "#8a94a6",
  dynamicObstacle: "#f0b429",
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
  staticObstacles,
  dynamicObstacles,
  previewTime,
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

    // **Keep-out rings first, so every obstacle is drawn on top of its
    // own ring.** The ring is context; the obstacle is the subject, and
    // a 1.0 m disc painted over a 0.4 m cart puts the reader's eye on
    // the wrong thing.
    //
    // Worth drawing at all because it was invisible and cost a session
    // to diagnose: a robot parked half a metre clear of a cart looks
    // like it is standing in open space, and the reason it cannot replan
    // from there is this ring — which is two and a half times the circle
    // the canvas was drawing.
    const ringFor = (radius: number) => keepOutRadius(radius, map.resolution, robotRadius);
    const drawRing = (worldX: number, worldY: number, radius: number | null) => {
      if (radius === null) return;
      const [x, y] = toCanvas(worldX, worldY);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(2, radius * viewport.scale), 0, Math.PI * 2);
      ctx.fillStyle = KEEP_OUT_FILL;
      ctx.fill();
      // Dashed and thin: a solid ring reads as a wall, which is the one
      // thing this is not — the controller will drive through it, the
      // planner just will not route through it.
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.strokeStyle = KEEP_OUT_STROKE;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    for (const obstacle of staticObstacles ?? []) {
      if (obstacle.type === "circle") {
        drawRing(obstacle.center.x, obstacle.center.y, ringFor(obstacle.radius));
      } else {
        // A rectangle's ring is drawn from its centre at the radius of
        // its circumscribing circle: an exact rounded-rectangle offset
        // would be more faithful and less legible, and the point here is
        // "there is a margin, roughly this big", not a boundary anybody
        // measures off the screen.
        const cx = (obstacle.min_x + obstacle.max_x) / 2;
        const cy = (obstacle.min_y + obstacle.max_y) / 2;
        const half = Math.hypot(obstacle.max_x - obstacle.min_x, obstacle.max_y - obstacle.min_y) / 2;
        drawRing(cx, cy, ringFor(half));
      }
    }
    for (const obstacle of dynamicObstacles ?? []) {
      drawRing(obstacle.position.x, obstacle.position.y, ringFor(obstacle.radius));
    }

    // Obstacles go under the plan and trajectory: the question the
    // picture answers is where the path runs relative to them.
    if (staticObstacles) {
      ctx.fillStyle = COLOR.staticObstacle;
      for (const obstacle of staticObstacles) {
        if (obstacle.type === "circle") {
          const [x, y] = toCanvas(obstacle.center.x, obstacle.center.y);
          ctx.beginPath();
          ctx.arc(x, y, Math.max(2, obstacle.radius * viewport.scale), 0, Math.PI * 2);
          ctx.fill();
        } else {
          const [x, y] = toCanvas(obstacle.min_x, obstacle.max_y);
          ctx.fillRect(
            x,
            y,
            (obstacle.max_x - obstacle.min_x) * viewport.scale,
            (obstacle.max_y - obstacle.min_y) * viewport.scale,
          );
        }
      }
    }

    if (dynamicObstacles) {
      for (const obstacle of dynamicObstacles) {
        const [x, y] = toCanvas(obstacle.position.x, obstacle.position.y);
        const r = Math.max(3, obstacle.radius * viewport.scale);
        ctx.fillStyle = "rgba(240, 180, 41, 0.25)";
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = COLOR.dynamicObstacle;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = COLOR.dynamicObstacle;
        ctx.font = "11px ui-sans-serif, system-ui";
        ctx.fillText(obstacle.name, x + r + 4, y - r - 2);
      }
      if (dynamicObstacles.length > 0 && previewTime !== undefined) {
        // The instant is part of the picture: two obstacles that never
        // meet at t=0 may well meet at t=7, and a snapshot with no clock
        // on it invites the reader to take it for the whole episode.
        ctx.fillStyle = COLOR.dynamicObstacle;
        ctx.font = "11px ui-sans-serif, system-ui";
        ctx.fillText(`t = ${previewTime.toFixed(1)}s`, 8, 14);
      }
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
      const r = Math.max(4, radius * viewport.scale);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.stroke();
      // Heading arrow: theta is part of the pose the simulator will use,
      // so the picture must show it — a number field alone leaves the
      // author guessing which way the robot actually faces. World theta
      // is counter-clockwise from +x; canvas y grows downward, hence -sin.
      const len = Math.max(16, r * 2.2);
      const tipX = x + Math.cos(pose.theta) * len;
      const tipY = y - Math.sin(pose.theta) * len;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(tipX, tipY);
      ctx.stroke();
      const head = 6;
      const angle = Math.atan2(tipY - y, tipX - x);
      ctx.beginPath();
      ctx.moveTo(tipX, tipY);
      ctx.lineTo(tipX - head * Math.cos(angle - Math.PI / 6), tipY - head * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(tipX - head * Math.cos(angle + Math.PI / 6), tipY - head * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
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
    staticObstacles,
    dynamicObstacles,
    previewTime,
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
