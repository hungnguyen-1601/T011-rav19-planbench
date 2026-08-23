"use client";

/** Canvas 2D renderer for map, plan, trajectory and robot.
 *
 * Rendering only — it never computes metrics or simulation state; those
 * come from the backend (project rule: no simulator logic in the UI).
 */

import { useCallback, useEffect, useRef } from "react";
import { OCCUPIED, UNKNOWN } from "@/lib/demoMap";
import { pointerRouting } from "@/lib/pointerRouting";
import {
  CAUTION_FILL,
  CAUTION_STROKE,
  KEEP_OUT_FILL,
  KEEP_OUT_STROKE,
  cautionRadius,
  keepOutRadius,
} from "@/lib/keepOut";
import { canvasToWorld, fitViewport, type Viewport } from "@/lib/transform";
import type { TrafficOverlay } from "@/lib/trafficOverlay";
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
  /** Safety envelope in metres, from `safetyEnvelope(sensor_noise)`.
   *
   * Zero is the truthful default: a view with no deployment behind it
   * shows a scenario, and a scenario declares no localisation error. */
  positionUncertainty?: number;
  plannedPath?: Point2D[];
  trajectory?: TrajectoryPoint[];
  robotPose?: Pose2D | null;
  collisionPoint?: Point2D | null;
  /** Static obstacles as authored: circles and axis-aligned rectangles.
   *  Pure geometry, so the canvas can draw these itself. */
  staticObstacles?: StaticObstacle[];
  /** Moving obstacles at one instant — see {@link ObstacleMarker}. */
  dynamicObstacles?: ObstacleMarker[];
  /** The traffic *as declared*, drawn from the document rather than
   *  from a simulated instant.
   *
   * A different question from `dynamicObstacles`, and drawn in a
   * different colour for that reason: this is the route somebody wrote
   * and can still grab, while those are where the backend says the
   * obstacles are at *t*. Preview markers are never interactive; only
   * these carry handles. */
  authoredTraffic?: TrafficOverlay;
  /** The instant `dynamicObstacles` describes, in seconds, for the label.
   *  The editor passes the scrubber position; replay passes the playhead. */
  previewTime?: number;
  /* **Off by default, everywhere.** The grid is a measuring aid: useful
     when somebody is judging a clearance in cells, noise the rest of the
     time, and it sat on top of the one thing these canvases exist to show.
     Defaulting it on also meant four screens drew it with no control to
     reach, which is how it went unnoticed for as long as it did. Turning
     it on is now a thing a reader does, not a thing they undo. */
  showGrid?: boolean;
  showPlan?: boolean;
  showTrajectory?: boolean;
  /** Legacy gesture props: a click on press, a drag per move, and the
   *  drag *ends when the pointer leaves the canvas* — MapPainter's
   *  stroke stops at the edge because of that. Kept working untouched
   *  for every existing consumer; see `pointerRouting` for how they
   *  yield to the new lifecycle below. */
  onWorldClick?: (x: number, y: number, event: React.MouseEvent<HTMLCanvasElement>) => void;
  onWorldDrag?: (x: number, y: number) => void;
  /** The full pointer lifecycle, for a consumer that drags handles.
   *
   * Passing any of these turns pointer capture on — the drag then
   * survives leaving the canvas, and `up`/`cancel` always arrive to
   * finish it. Passing `onWorldPointerDown` silences `onWorldClick`;
   * passing `onWorldPointerMove` silences `onWorldDrag` — one event,
   * one owner, never both. */
  onWorldPointerDown?: (point: Point2D, info: WorldPointerInfo) => void;
  onWorldPointerMove?: (point: Point2D, info: WorldPointerInfo) => void;
  onWorldPointerUp?: (point: Point2D, info: WorldPointerInfo) => void;
  /** The browser took the pointer away (gesture interruption, capture
   *  loss). The point carried here may be garbage — flush the last
   *  trusted move coordinate instead of this one. */
  onWorldPointerCancel?: (point: Point2D, info: WorldPointerInfo) => void;
  /** Carries `worldPerPixel` like the others: a double-click has to
   *  find what is under it, and finding it means the same pixel
   *  tolerance in world units that a press uses. */
  onWorldDoubleClick?: (point: Point2D, worldPerPixel: number) => void;
}

/** What a world-space pointer event knows beyond its position. */
export interface WorldPointerInfo {
  pointerId: number;
  /** Metres per screen pixel at the current viewport — what turns a
   *  pixel tolerance ("within 8px of the handle") into world units. */
  worldPerPixel: number;
  event: React.PointerEvent<HTMLCanvasElement>;
}

const COLOR = {
  occupied: "#5b6c7f",
  unknown: "#33383f",
  /* **Mid-grey, because the floor is not a fixed colour.** The canvas
     is cleared to transparent and free cells are skipped, so the floor
     is whatever `--canvas-bg` paints behind it: `#0b0d11` in the dark
     theme and `#eef1f5` in the light one. This was white at 4.5% alpha
     — correct on the dark floor it was written against, and literally
     invisible on the light one, which is why the Grid checkbox appeared
     to do nothing at all.

     A mid-grey with a real alpha reads on both: it lands near `#c5cbd4`
     over the light floor and near `#333a44` over the dark one. That is
     the same trick `occupied` already uses to survive both themes, and
     the reason every other colour here got away with being a constant
     while this one did not — it was the only one parked at an extreme
     of the lightness range. */
  gridLine: "rgba(120,132,150,0.35)",
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
  // The authored route is a third kind of statement: not the world
  // (grey), not where something is at an instant (amber), but what the
  // author has written down and can still take hold of. Teal because it
  // has to be told apart from the amber snapshot at a glance — those
  // two describe the same obstacle and only one of them is editable.
  authored: "#5ad1c8",
};

export function MapCanvas({
  map,
  width = 760,
  height = 560,
  startPose,
  goalPose,
  goalTolerance = 0.3,
  robotRadius = 0.3,
  positionUncertainty = 0,
  plannedPath,
  trajectory,
  robotPose,
  collisionPoint,
  staticObstacles,
  dynamicObstacles,
  authoredTraffic,
  previewTime,
  showGrid = false,
  showPlan = true,
  showTrajectory = true,
  onWorldClick,
  onWorldDrag,
  onWorldPointerDown,
  onWorldPointerMove,
  onWorldPointerUp,
  onWorldPointerCancel,
  onWorldDoubleClick,
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
    // like it is standing in open space, and the reason it could not
    // replan from there was not on screen anywhere.
    //
    // **Two rings, because there are two different claims.** The inner
    // one is forbidden — inside it the controller refuses to drive. The
    // outer one is merely *expensive*: a planner will pay to avoid it
    // and will cross it when the alternative costs more. Drawing them
    // as one disc, which is what this did before the gradient existed,
    // makes ground the robot may legally stand on look like a wall.
    const hardFor = (radius: number) =>
      keepOutRadius(radius, robotRadius, positionUncertainty);
    const cautionFor = (radius: number) =>
      cautionRadius(radius, map.resolution, robotRadius, positionUncertainty);
    const disc = (
      worldX: number,
      worldY: number,
      radius: number | null,
      fill: string,
      stroke: string,
      dash: number[],
    ) => {
      if (radius === null) return;
      const [x, y] = toCanvas(worldX, worldY);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(2, radius * viewport.scale), 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      // Never solid: a solid ring reads as a wall, and neither of these
      // is one. Dashed for the hard boundary, dotted for the priced
      // band, so which is which survives a screenshot.
      ctx.setLineDash(dash);
      ctx.lineWidth = 1;
      ctx.strokeStyle = stroke;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    const drawRing = (worldX: number, worldY: number, radius: number) => {
      // Priced band first, so the forbidden ring sits on top of it.
      disc(worldX, worldY, cautionFor(radius), CAUTION_FILL, CAUTION_STROKE, [2, 3]);
      disc(worldX, worldY, hardFor(radius), KEEP_OUT_FILL, KEEP_OUT_STROKE, [4, 4]);
    };
    for (const obstacle of staticObstacles ?? []) {
      if (obstacle.type === "circle") {
        drawRing(obstacle.center.x, obstacle.center.y, obstacle.radius);
      } else {
        // A rectangle's ring is drawn from its centre at the radius of
        // its circumscribing circle: an exact rounded-rectangle offset
        // would be more faithful and less legible, and the point here is
        // "there is a margin, roughly this big", not a boundary anybody
        // measures off the screen.
        const cx = (obstacle.min_x + obstacle.max_x) / 2;
        const cy = (obstacle.min_y + obstacle.max_y) / 2;
        const half = Math.hypot(obstacle.max_x - obstacle.min_x, obstacle.max_y - obstacle.min_y) / 2;
        drawRing(cx, cy, half);
      }
    }
    for (const obstacle of dynamicObstacles ?? []) {
      drawRing(obstacle.position.x, obstacle.position.y, obstacle.radius);
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

    // **The traffic as written, under the traffic as simulated.** Both
    // describe the same obstacles, so when a preview is on screen the
    // amber snapshot sits on top: that is the answer to "where is it at
    // t", and the teal underneath is the route it was given. Drawn from
    // stored points only — no motion law is evaluated here; see
    // `lib/trafficOverlay`.
    for (const shape of authoredTraffic?.shapes ?? []) {
      ctx.globalAlpha = shape.selected ? 1 : 0.45;
      ctx.strokeStyle = COLOR.authored;
      ctx.fillStyle = COLOR.authored;
      ctx.lineWidth = shape.selected ? 2 : 1.5;

      // The bound a random walk declares, not a position it reaches.
      if (shape.wanderRadius !== null && shape.home) {
        const [cx, cy] = toCanvas(shape.home.x, shape.home.y);
        ctx.setLineDash([3, 4]);
        ctx.beginPath();
        ctx.arc(cx, cy, Math.max(2, shape.wanderRadius * viewport.scale), 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      const polyline = (points: Point2D[], dash: number[]) => {
        if (points.length < 2) return;
        ctx.setLineDash(dash);
        ctx.beginPath();
        points.forEach((point, index) => {
          const [x, y] = toCanvas(point.x, point.y);
          if (index === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.setLineDash([]);
      };
      polyline(shape.path, []);
      // Dashed, because the author never placed a point on it: it is
      // the consequence of the loop flag rather than part of the route.
      if (shape.closingEdge) polyline(shape.closingEdge, [4, 4]);

      if (shape.heading) {
        const [fx, fy] = toCanvas(shape.heading.from.x, shape.heading.from.y);
        const [tx, ty] = toCanvas(shape.heading.to.x, shape.heading.to.y);
        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.lineTo(tx, ty);
        ctx.stroke();
        const angle = Math.atan2(ty - fy, tx - fx);
        const head = 7;
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(tx - head * Math.cos(angle - Math.PI / 6), ty - head * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(tx - head * Math.cos(angle + Math.PI / 6), ty - head * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
      }

      // The body, hollow: a filled disc here would compete with the
      // preview's for the eye, and this one is not where the obstacle
      // is — it is where its route begins.
      if (shape.home && shape.radius !== null) {
        const [x, y] = toCanvas(shape.home.x, shape.home.y);
        ctx.beginPath();
        ctx.arc(x, y, Math.max(3, shape.radius * viewport.scale), 0, Math.PI * 2);
        ctx.stroke();
      }

      for (const grip of shape.handles) {
        const [x, y] = toCanvas(grip.at.x, grip.at.y);
        ctx.beginPath();
        ctx.arc(x, y, shape.selected ? 4 : 3, 0, Math.PI * 2);
        ctx.fill();
        if (grip.label) {
          // Ordinals, so a route that crosses itself can still be read
          // in the order it is driven.
          ctx.font = "10px ui-sans-serif, system-ui";
          ctx.fillText(grip.label, x + 6, y - 5);
        }
      }

      if (shape.home) {
        const [x, y] = toCanvas(shape.home.x, shape.home.y);
        ctx.font = "11px ui-sans-serif, system-ui";
        ctx.fillText(shape.name, x + 8, y + 14);
      }
      ctx.globalAlpha = 1;
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
    positionUncertainty,
    plannedPath,
    trajectory,
    robotPose,
    collisionPoint,
    staticObstacles,
    dynamicObstacles,
    authoredTraffic,
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

  /* Which generation of props owns each gesture — see `pointerRouting`.
     Capture is only taken when the new lifecycle is in use: the legacy
     consumers end a drag by leaving the canvas, and capturing would
     quietly keep their stroke alive past the border. */
  const routing = pointerRouting({
    hasPointerDown: onWorldPointerDown !== undefined,
    hasPointerMove: onWorldPointerMove !== undefined,
    hasPointerUp: onWorldPointerUp !== undefined,
    hasPointerCancel: onWorldPointerCancel !== undefined,
  });

  const infoOf = (event: React.PointerEvent<HTMLCanvasElement>): WorldPointerInfo => ({
    pointerId: event.pointerId,
    worldPerPixel: 1 / viewport.scale,
    event,
  });

  return (
    <canvas
      ref={canvasRef}
      data-testid="map-canvas"
      onPointerDown={(event) => {
        const point = pointerWorld(event);
        if (routing.capture) event.currentTarget.setPointerCapture(event.pointerId);
        onWorldPointerDown?.(point, infoOf(event));
        // The legacy drag arms on press whether or not a click handler
        // is also given — that is what the mouse-event version did.
        if (routing.legacyDrag) draggingRef.current = true;
        if (routing.legacyClick) onWorldClick?.(point.x, point.y, event);
      }}
      onPointerMove={(event) => {
        const point = pointerWorld(event);
        onWorldPointerMove?.(point, infoOf(event));
        if (routing.legacyDrag && draggingRef.current && onWorldDrag) {
          onWorldDrag(point.x, point.y);
        }
      }}
      onPointerUp={(event) => {
        draggingRef.current = false;
        onWorldPointerUp?.(pointerWorld(event), infoOf(event));
      }}
      onPointerCancel={(event) => {
        draggingRef.current = false;
        onWorldPointerCancel?.(pointerWorld(event), infoOf(event));
      }}
      onPointerLeave={() => {
        // Legacy lifecycle only: leaving ends the drag. Under capture
        // this never fires mid-drag, because the capture holds the
        // pointer target on the canvas until up or cancel.
        draggingRef.current = false;
      }}
      onDoubleClick={(event) => {
        onWorldDoubleClick?.(pointerWorld(event), 1 / viewport.scale);
      }}
    />
  );
}
