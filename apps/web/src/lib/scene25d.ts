/** 2.5D scene construction: a 2D occupancy grid seen at an angle.
 *
 * "2.5D" here means what the spec means by it — the world is genuinely
 * planar (x, y, theta), and the third dimension is presentation only:
 * walls are extruded to a fixed height so occupancy is readable as
 * volume rather than as flat colour. No simulation quantity is derived
 * from height, and nothing here feeds back into the physics.
 *
 * Everything is pure geometry, deliberately separated from any renderer.
 * The projection and the depth ordering are the parts that are easy to
 * get subtly wrong, so they are unit-tested here; a renderer then just
 * draws the polygons it is handed. That split is also what makes a
 * WebGL renderer a drop-in later: it would consume the same scene.
 *
 * Axonometric projection, with world y running "into" the screen:
 *
 *   screen.x =  (x - y) * cos(azimuth) * scale
 *   screen.y = -(x + y) * sin(elevation) * scale - z * scale
 *
 * so +z is up on screen, and a taller wall reaches further up.
 */

import { cautionRadius, keepOutRadius } from "./keepOut";
import type { MapData, ObstacleSnapshot, Point2D, Pose2D, TrajectoryPoint } from "./types";

export const OCCUPIED_VALUE = 100;
export const UNKNOWN_VALUE = -1;

export interface Projection {
  /** Radians. 0 looks straight down the x axis; π/4 is isometric-ish. */
  azimuth: number;
  /** Radians above the ground plane. π/2 collapses to a top-down view. */
  elevation: number;
  /** Pixels per metre before projection. */
  scale: number;
  /** Screen-space translation applied last. */
  offsetX: number;
  offsetY: number;
}

export interface ScreenPoint {
  sx: number;
  sy: number;
}

/** A projected polygon, ready to fill. */
export interface Facet {
  points: ScreenPoint[];
  /** "top" | "left" | "right" — the renderer shades by face. */
  face: FacetFace;
  /** Larger draws later (painter's algorithm). */
  depth: number;
  kind: FacetKind;
}

export type FacetFace = "top" | "left" | "right";
export type FacetKind = "ground" | "occupied" | "unknown";

export interface Scene25D {
  facets: Facet[];
  /** Projected trajectory, already in screen space. */
  trajectory: ScreenPoint[];
  plan: ScreenPoint[];
  start: ScreenPoint | null;
  goal: ScreenPoint | null;
  robot: RobotMarker | null;
  /** Dynamic obstacles at this frame — see docs/KNOWN_LIMITATIONS.md:
   * drawn after every facet, so they are never occluded by a wall. */
  obstacles: ObstacleMarker[];
  /** The planner's keep-out around each of those, as a flat footprint on
   *  the ground plane.
   *
   * Flat rather than extruded on purpose: raising it would draw a
   * cylinder, and a cylinder reads as a second object standing there.
   * This is a margin the planner will not route through, not a thing
   * the robot can hit — the controller drives through it every time it
   * squeezes past something. */
  keepOut: ObstacleMarker[];
  /** The priced band beyond the boundary — passable, not forbidden. */
  caution: ObstacleMarker[];
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
}

export interface RobotMarker {
  base: ScreenPoint;
  top: ScreenPoint;
  /** Tip of the heading indicator, projected on the robot's top face. */
  heading: ScreenPoint;
  /** Projected horizontal radius, in pixels. */
  radiusX: number;
  /** Projected vertical radius of the (foreshortened) footprint circle. */
  radiusY: number;
}

/** Same projected footprint as RobotMarker, minus heading — obstacles
 * carry no orientation. */
export interface ObstacleMarker {
  base: ScreenPoint;
  top: ScreenPoint;
  radiusX: number;
  radiusY: number;
}

export const DEFAULT_PROJECTION: Omit<Projection, "offsetX" | "offsetY" | "scale"> = {
  azimuth: Math.PI / 4,
  elevation: Math.PI / 6,
};

/** Project a world point (metres, z up) into screen pixels. */
export function project(projection: Projection, x: number, y: number, z = 0): ScreenPoint {
  const { azimuth, elevation, scale, offsetX, offsetY } = projection;
  return {
    sx: offsetX + (x - y) * Math.cos(azimuth) * scale,
    sy: offsetY - (x + y) * Math.sin(elevation) * scale - z * scale,
  };
}

/**
 * Depth key for painter's-algorithm ordering.
 *
 * Under this projection a cell is occluded only by cells with a larger
 * `x + y`, so that sum totally orders the scene. Sorting by projected
 * `sy` instead would be wrong: a tall wall's top face has a small `sy`
 * yet still belongs behind whatever stands in front of it.
 */
export function depthOf(x: number, y: number): number {
  return x + y;
}

/** A projection that fits the whole map into a canvas, with padding. */
export function fitProjection(
  map: Pick<MapData, "width" | "height" | "resolution" | "origin">,
  canvasWidth: number,
  canvasHeight: number,
  options: { azimuth?: number; elevation?: number; padding?: number; wallHeight?: number } = {},
): Projection {
  const azimuth = options.azimuth ?? DEFAULT_PROJECTION.azimuth;
  const elevation = options.elevation ?? DEFAULT_PROJECTION.elevation;
  const padding = options.padding ?? 24;
  const wallHeight = options.wallHeight ?? 0;

  const x0 = map.origin.x;
  const y0 = map.origin.y;
  const x1 = x0 + map.width * map.resolution;
  const y1 = y0 + map.height * map.resolution;

  // Unit projection (scale 1, no offset) of the eight box corners.
  const unit: Projection = { azimuth, elevation, scale: 1, offsetX: 0, offsetY: 0 };
  const corners: ScreenPoint[] = [];
  for (const x of [x0, x1]) {
    for (const y of [y0, y1]) {
      corners.push(project(unit, x, y, 0));
      corners.push(project(unit, x, y, wallHeight));
    }
  }
  const xs = corners.map((point) => point.sx);
  const ys = corners.map((point) => point.sy);
  const spanX = Math.max(...xs) - Math.min(...xs) || 1;
  const spanY = Math.max(...ys) - Math.min(...ys) || 1;
  const scale = Math.min(
    (canvasWidth - 2 * padding) / spanX,
    (canvasHeight - 2 * padding) / spanY,
  );

  // Centre the projected bounding box in the canvas.
  const centreX = (Math.max(...xs) + Math.min(...xs)) / 2;
  const centreY = (Math.max(...ys) + Math.min(...ys)) / 2;
  return {
    azimuth,
    elevation,
    scale,
    offsetX: canvasWidth / 2 - centreX * scale,
    offsetY: canvasHeight / 2 - centreY * scale,
  };
}

export interface SceneOptions {
  wallHeight?: number;
  robotHeight?: number;
  /** Draw the free-space floor. Off gives a wireframe-ish look. */
  showGround?: boolean;
  startPose?: Pose2D;
  goalPose?: Pose2D;
  robotPose?: Pose2D | null;
  robotRadius?: number;
  /** Safety envelope in metres, from `safetyEnvelope(sensor_noise)`. */
  positionUncertainty?: number;
  plannedPath?: Point2D[];
  trajectory?: TrajectoryPoint[];
  obstacles?: ObstacleSnapshot[];
}

/**
 * Build the drawable scene for one map.
 *
 * Cells are emitted back-to-front. Free cells contribute one flat ground
 * quad; occupied and unknown cells contribute a top face plus the two
 * side faces that can face the camera under this fixed azimuth — the
 * other two are always hidden, so drawing them would be wasted work.
 */
export function buildScene(
  map: MapData,
  projection: Projection,
  options: SceneOptions = {},
): Scene25D {
  const wallHeight = options.wallHeight ?? 0.6;
  const robotHeight = options.robotHeight ?? 0.35;
  const showGround = options.showGround ?? true;
  const cell = map.resolution;
  const facets: Facet[] = [];

  for (let row = 0; row < map.height; row += 1) {
    for (let col = 0; col < map.width; col += 1) {
      const value = map.cells[row * map.width + col];
      const x = map.origin.x + col * cell;
      const y = map.origin.y + row * cell;
      const depth = depthOf(x, y);

      if (value === OCCUPIED_VALUE || value === UNKNOWN_VALUE) {
        const kind: FacetKind = value === OCCUPIED_VALUE ? "occupied" : "unknown";
        // Unknown space is shown flat: it is absence of information, and
        // extruding it would read as an obstacle that is not there.
        const height = kind === "occupied" ? wallHeight : 0;
        facets.push(...boxFacets(projection, x, y, cell, height, kind, depth));
      } else if (showGround) {
        facets.push({
          points: quad(projection, x, y, cell, 0),
          face: "top",
          depth,
          kind: "ground",
        });
      }
    }
  }

  facets.sort((a, b) => a.depth - b.depth);

  const projectPoint = (point: { x: number; y: number }) =>
    project(projection, point.x, point.y, 0);

  return {
    facets,
    trajectory: (options.trajectory ?? []).map(projectPoint),
    plan: (options.plannedPath ?? []).map(projectPoint),
    start: options.startPose ? projectPoint(options.startPose) : null,
    goal: options.goalPose ? projectPoint(options.goalPose) : null,
    robot: options.robotPose
      ? robotMarker(projection, options.robotPose, options.robotRadius ?? 0.3, robotHeight)
      : null,
    obstacles: (options.obstacles ?? []).map((o) =>
      obstacleMarker(projection, o.x, o.y, o.radius, robotHeight),
    ),
    // Same numbers the flat view quotes, from the same functions — two
    // hand-typed copies of an inflation radius is how the controller's
    // keep-out and the planner's came to differ by 0.30 m to begin with.
    keepOut: (options.obstacles ?? []).flatMap((o) => {
      const radius = keepOutRadius(o.radius, options.robotRadius, options.positionUncertainty);
      return radius === null ? [] : [obstacleMarker(projection, o.x, o.y, radius, 0)];
    }),
    // The band beyond the boundary: passable, and charged for. A
    // separate list rather than a wider `keepOut`, because the renderer
    // has to be able to draw them differently — one is a refusal and the
    // other is a price, and a reader who cannot tell them apart is back
    // to the picture that made a stuck robot inexplicable.
    caution: (options.obstacles ?? []).flatMap((o) => {
      const radius = cautionRadius(
        o.radius,
        map.resolution,
        options.robotRadius,
        options.positionUncertainty,
      );
      return radius === null ? [] : [obstacleMarker(projection, o.x, o.y, radius, 0)];
    }),
    bounds: sceneBounds(facets),
  };
}

function quad(
  projection: Projection,
  x: number,
  y: number,
  size: number,
  z: number,
): ScreenPoint[] {
  return [
    project(projection, x, y, z),
    project(projection, x + size, y, z),
    project(projection, x + size, y + size, z),
    project(projection, x, y + size, z),
  ];
}

function boxFacets(
  projection: Projection,
  x: number,
  y: number,
  size: number,
  height: number,
  kind: FacetKind,
  depth: number,
): Facet[] {
  if (height <= 0) {
    return [{ points: quad(projection, x, y, size, 0), face: "top", depth, kind }];
  }
  const top = quad(projection, x, y, size, height);
  // The two faces that can point at the camera: the +x wall and the +y
  // wall. Under a fixed azimuth in (0, π/2) the other two are always
  // occluded by the cell itself.
  const right: ScreenPoint[] = [
    project(projection, x + size, y, 0),
    project(projection, x + size, y + size, 0),
    project(projection, x + size, y + size, height),
    project(projection, x + size, y, height),
  ];
  const left: ScreenPoint[] = [
    project(projection, x, y + size, 0),
    project(projection, x + size, y + size, 0),
    project(projection, x + size, y + size, height),
    project(projection, x, y + size, height),
  ];
  return [
    { points: left, face: "left", depth, kind },
    { points: right, face: "right", depth, kind },
    { points: top, face: "top", depth, kind },
  ];
}

function robotMarker(
  projection: Projection,
  pose: Pose2D,
  radius: number,
  height: number,
): RobotMarker {
  const base = project(projection, pose.x, pose.y, 0);
  const top = project(projection, pose.x, pose.y, height);
  const heading = project(
    projection,
    pose.x + Math.cos(pose.theta) * radius * 1.8,
    pose.y + Math.sin(pose.theta) * radius * 1.8,
    height,
  );
  // A circle on the ground plane projects to an ellipse; these are the
  // projected semi-axes along the two world axes.
  const edgeX = project(projection, pose.x + radius, pose.y, height);
  const edgeY = project(projection, pose.x, pose.y + radius, height);
  return {
    base,
    top,
    heading,
    radiusX: Math.hypot(edgeX.sx - top.sx, edgeX.sy - top.sy),
    radiusY: Math.hypot(edgeY.sx - top.sx, edgeY.sy - top.sy),
  };
}

function obstacleMarker(
  projection: Projection,
  x: number,
  y: number,
  radius: number,
  height: number,
): ObstacleMarker {
  const base = project(projection, x, y, 0);
  const top = project(projection, x, y, height);
  const edgeX = project(projection, x + radius, y, height);
  const edgeY = project(projection, x, y + radius, height);
  return {
    base,
    top,
    radiusX: Math.hypot(edgeX.sx - top.sx, edgeX.sy - top.sy),
    radiusY: Math.hypot(edgeY.sx - top.sx, edgeY.sy - top.sy),
  };
}

function sceneBounds(facets: Facet[]): Scene25D["bounds"] {
  if (facets.length === 0) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const facet of facets) {
    for (const point of facet.points) {
      if (point.sx < minX) minX = point.sx;
      if (point.sx > maxX) maxX = point.sx;
      if (point.sy < minY) minY = point.sy;
      if (point.sy > maxY) maxY = point.sy;
    }
  }
  return { minX, minY, maxX, maxY };
}
