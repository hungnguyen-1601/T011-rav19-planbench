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
import { CAUTION_FILL, CAUTION_STROKE, KEEP_OUT_FILL, KEEP_OUT_STROKE } from "@/lib/keepOut";
import type { MapData } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";

export interface Scene25DProps extends SceneOptions {
  map: MapData;
  width?: number;
  height?: number;
  /** Degrees; the control strip writes these back. */
  azimuthDeg?: number;
  elevationDeg?: number;
  /** Degrees about the world z axis — the angle a drag across the canvas
   *  sets, and the only one that turns the room. */
  yawDeg?: number;
  showControls?: boolean;
  /** Draw the cell edges on the floor.
   *
   * **The raised view had no grid and looked like it did.** The floor is
   * one quad per free cell, filled and never stroked, so the faint
   * lattice on it was the anti-aliased seam between neighbours — a
   * rendering artefact that no switch could turn off because nothing
   * had drawn it. Off now closes those seams; on strokes them
   * deliberately, in ink chosen to be seen. */
  showGrid?: boolean;
  /** **Lift the view out of this component.** Two of these sit side by
   *  side showing the same episode, and a reader who turns one to look
   *  behind a wall is comparing two rooms until they turn the other to
   *  match by hand. Given this, the strip stops holding its own state
   *  and reports every change to the owner of the pair. Omitted, the
   *  scene keeps its own — the standalone viewer has nobody to sync
   *  with. */
  onViewChange?: (view: { yawDeg: number; elevationDeg: number; wallHeight: number }) => void;
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
  /* The same mid-grey the flat canvas inks its grid with, and for the
     same reason: it has to separate from whatever is behind it rather
     than from one particular floor. Over this scene's `#1b2029` ground
     it lands near `#4a5460`. */
  gridLine: "rgba(120,132,150,0.35)",
};

export function Scene25D({
  map,
  width = 760,
  height = 520,
  azimuthDeg = 45,
  elevationDeg = 30,
  yawDeg = 0,
  showControls = true,
  showGrid = false,
  onViewChange,
  showPlan = true,
  showTrajectory = true,
  wallHeight = 0.6,
  robotHeight = 0.35,
  showGround = true,
  startPose,
  goalPose,
  robotPose,
  robotRadius = 0.3,
  positionUncertainty = 0,
  plannedPath,
  trajectory,
  obstacles,
}: Scene25DProps) {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [azimuth] = useState(azimuthDeg);
  /* Controlled when the owner is listening, uncontrolled when it is
     not. The local copies are the fallback for the standalone viewer;
     with an `onViewChange` the props win on every render, so the two
     panels cannot drift apart even for a frame. */
  const [localYaw, setLocalYaw] = useState(yawDeg);
  const [localElevation, setLocalElevation] = useState(elevationDeg);
  const [localHeight, setLocalHeight] = useState(wallHeight);
  const yaw = onViewChange ? yawDeg : localYaw;
  const elevation = onViewChange ? elevationDeg : localElevation;
  const height3d = onViewChange ? wallHeight : localHeight;

  /** Where the pointer went down, and the angles it went down at.
   *
   * **Accumulated from the grab, not from the last frame.** Adding each
   * move's delta to the current angle looks identical and drifts: with
   * the value controlled from above, a move that arrives before the
   * parent has re-rendered reads a stale angle, and that error is kept.
   * Measuring the whole gesture from where it started cannot drift, and
   * it is also what makes releasing and re-grabbing feel like picking
   * the same object back up. */
  const grab = useRef<{ x: number; y: number; yaw: number; elevation: number } | null>(null);

  const emit = (next: Partial<{ yawDeg: number; elevationDeg: number; wallHeight: number }>) => {
    const view = { yawDeg: yaw, elevationDeg: elevation, wallHeight: height3d, ...next };
    if (onViewChange) onViewChange(view);
    else {
      setLocalYaw(view.yawDeg);
      setLocalElevation(view.elevationDeg);
      setLocalHeight(view.wallHeight);
    }
  };

  const scene = useMemo(() => {
    const projection = fitProjection(map, width, height, {
      yaw: (yaw * Math.PI) / 180,
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
      positionUncertainty,
      plannedPath,
      trajectory,
      obstacles,
    });
  }, [
    map,
    width,
    height,
    yaw,
    azimuth,
    elevation,
    height3d,
    robotHeight,
    showGround,
    startPose,
    goalPose,
    robotPose,
    robotRadius,
    positionUncertainty,
    plannedPath,
    trajectory,
    obstacles,
  ]);

  /** Turn the room by dragging it, the way a thing on a turntable turns.
   *
   * Across is yaw and down is tilt, which is the gesture every 3D viewer
   * has trained readers on — and it is why the two rotation sliders are
   * gone rather than sitting beside it. A slider and a drag doing one
   * job is two controls for one thing, which this file already refused
   * once when "Rotate" turned out to drive an azimuth that rotated
   * nothing.
   *
   * **Degrees per pixel, chosen so one drag across the canvas is a bit
   * over a full turn.** Faster and the room spins past the angle the
   * reader wanted; slower and looking at the far side takes several
   * strokes. */
  const YAW_PER_PX = 0.5;
  const TILT_PER_PX = 0.4;
  /** Straight down is the useful end; past it the room turns inside out
   *  and the floor paints over the walls. At 0 it is edge-on, where the
   *  room collapses to a line. */
  const clampTilt = (degrees: number) => Math.max(1, Math.min(89, degrees));
  /** A yaw is an angle, not a range: 359° and 1° are two degrees apart,
   *  so it wraps rather than stopping at an end. */
  const wrapYaw = (degrees: number) => ((degrees % 360) + 360) % 360;

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    // Primary button only. A right-drag is the context menu and a
    // middle-drag is autoscroll; taking either is rude.
    if (event.button !== 0) return;
    grab.current = { x: event.clientX, y: event.clientY, yaw, elevation };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const from = grab.current;
    if (!from) return;
    emit({
      yawDeg: wrapYaw(from.yaw + (event.clientX - from.x) * YAW_PER_PX),
      elevationDeg: clampTilt(from.elevation - (event.clientY - from.y) * TILT_PER_PX),
    });
  };

  const endDrag = (event: React.PointerEvent<HTMLCanvasElement>) => {
    grab.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  /** The same two axes for a reader who is not holding a mouse.
   *
   * **This is what let the sliders go.** A canvas nobody can focus is a
   * canvas only a pointer can reach, and dropping the sliders without
   * this would have traded one complaint for a worse one: the room
   * would have become unturnable by keyboard entirely. */
  const onKeyDown = (event: React.KeyboardEvent<HTMLCanvasElement>) => {
    const step = event.shiftKey ? 15 : 5;
    switch (event.key) {
      case "ArrowLeft":
        emit({ yawDeg: wrapYaw(yaw - step) });
        break;
      case "ArrowRight":
        emit({ yawDeg: wrapYaw(yaw + step) });
        break;
      case "ArrowUp":
        emit({ elevationDeg: clampTilt(elevation + step) });
        break;
      case "ArrowDown":
        emit({ elevationDeg: clampTilt(elevation - step) });
        break;
      default:
        return;
    }
    event.preventDefault();
  };

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
      fillFacet(ctx, facet, showGrid);
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

    // The planner's margins, on the floor and under everything else.
    // They are context rather than objects, so neither gets a side wall:
    // extruding one would draw a cylinder, and a cylinder reads as a
    // second thing standing in the room. Faint enough that the obstacle
    // they belong to stays the subject of the picture.
    //
    // Two of them, and the difference matters: the inner ring is
    // forbidden, the outer band is merely expensive. Priced band first,
    // so the forbidden ring lands on top of it.
    const ellipse = (
      ring: (typeof scene.keepOut)[number],
      fill: string,
      stroke: string,
      dash: number[],
    ) => {
      ctx.beginPath();
      ctx.ellipse(
        ring.base.sx,
        ring.base.sy,
        Math.max(2, ring.radiusX),
        Math.max(1.5, ring.radiusY),
        0,
        0,
        Math.PI * 2,
      );
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.setLineDash(dash);
      ctx.lineWidth = 1;
      ctx.strokeStyle = stroke;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    for (const ring of scene.caution) {
      ellipse(ring, CAUTION_FILL, CAUTION_STROKE, [2, 3]);
    }
    for (const ring of scene.keepOut) {
      ellipse(ring, KEEP_OUT_FILL, KEEP_OUT_STROKE, [4, 4]);
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
  // The flags belong in this list or the canvas keeps whatever it last
  // drew: `scene` is memoised on the projection, so toggling a layer
  // changes nothing this effect watches unless the flag is named here.
  }, [scene, width, height, showGrid, showPlan, showTrajectory]);

  return (
    <div className="scene25d">
      <canvas
        ref={canvasRef}
        data-testid="scene-25d"
        className="scene25d-canvas"
        /* A group, not an image: it holds an orientation and changing
           it is the point. `img` would tell a screen reader there is
           nothing here to operate. */
        role="group"
        aria-label={`${t("scene25d.alt")} \u2014 ${t("scene25d.angles", {
          yaw: String(Math.round(yaw)),
          tilt: String(Math.round(elevation)),
        })}`}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
      />
      {showControls ? (
        <div className="scene25d-controls">
          {/* **No Rotate and Tilt sliders.** Both axes live on the
              canvas now — drag it, or focus it and use the arrow keys —
              and a slider beside a drag is two controls for one job.

              What is left is the reading, so a reader can say which
              angle they are looking from and come back to it, plus the
              line that says the picture can be dragged at all. Wall
              height keeps its slider: it is a property of the drawing
              rather than of the camera, and there is no gesture for
              it. */}
          <span className="scene25d-readout">
            {t("scene25d.angles", {
              yaw: String(Math.round(yaw)),
              tilt: String(Math.round(elevation)),
            })}
            {elevation >= 88 ? ` ${t("scene25d.topDown")}` : ""}
          </span>
          <span className="scene25d-hint">{t("scene25d.dragHint")}</span>
          <label>
            Wall height
            <input
              type="range"
              min={0}
              max={20}
              value={Math.round(height3d * 10)}
              onChange={(event) => emit({ wallHeight: Number(event.target.value) / 10 })}
            />
            <span className="muted">{height3d.toFixed(1)} m</span>
          </label>
        </div>
      ) : null}
    </div>
  );
}

function fillFacet(ctx: CanvasRenderingContext2D, facet: Facet, showGrid: boolean): void {
  const fill = FILL[facet.kind][facet.face];
  ctx.fillStyle = fill;
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
    return;
  }

  /* **The floor is always stroked; only the colour changes.**
     Neighbouring quads share an edge, and filling them without a stroke
     leaves an anti-aliased hairline between every pair — a lattice that
     looks like a grid, cannot be switched off, and is not one. Stroking
     in the fill's own colour closes it; stroking in the grid ink draws
     the real thing. One code path, so "grid off" is a floor with no
     lines on it rather than a floor with faint accidental ones. */
  ctx.strokeStyle = showGrid ? COLOR.gridLine : fill;
  ctx.lineWidth = showGrid ? 0.6 : 1;
  ctx.stroke();
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
