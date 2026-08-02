import { describe, expect, it } from "vitest";
import {
  DEFAULT_PROJECTION,
  buildScene,
  depthOf,
  fitProjection,
  project,
  type Projection,
} from "../scene25d";
import type { MapData } from "../types";

const PROJECTION: Projection = {
  ...DEFAULT_PROJECTION,
  scale: 10,
  offsetX: 100,
  offsetY: 200,
};

function makeMap(cells: number[], width = 3, height = 3): MapData {
  return {
    name: "test",
    width,
    height,
    resolution: 1,
    origin: { x: 0, y: 0, theta: 0 },
    cells,
  };
}

const FREE_3X3 = makeMap(Array(9).fill(0));

describe("project", () => {
  it("puts the world origin at the projection offset", () => {
    expect(project(PROJECTION, 0, 0, 0)).toEqual({ sx: 100, sy: 200 });
  });

  it("sends +z upwards on screen", () => {
    const ground = project(PROJECTION, 1, 1, 0);
    const raised = project(PROJECTION, 1, 1, 1);
    expect(raised.sy).toBeLessThan(ground.sy);
    expect(raised.sx).toBe(ground.sx);
  });

  it("separates the two world axes horizontally in opposite directions", () => {
    const alongX = project(PROJECTION, 1, 0, 0);
    const alongY = project(PROJECTION, 0, 1, 0);
    expect(alongX.sx).toBeGreaterThan(100);
    expect(alongY.sx).toBeLessThan(100);
  });

  it("moves both axes down-screen by the same amount at equal distance", () => {
    // Both axes recede from the camera, so +x and +y each add depth.
    const alongX = project(PROJECTION, 1, 0, 0);
    const alongY = project(PROJECTION, 0, 1, 0);
    expect(alongX.sy).toBeCloseTo(alongY.sy, 10);
    expect(alongX.sy).toBeLessThan(200);
  });

  it("collapses to a top-down view at elevation zero", () => {
    const flat = { ...PROJECTION, elevation: 0 };
    expect(project(flat, 3, 5, 0).sy).toBe(200);
  });

  it("is linear in the scale factor", () => {
    const doubled = project({ ...PROJECTION, scale: 20, offsetX: 0, offsetY: 0 }, 2, 3, 1);
    const single = project({ ...PROJECTION, scale: 10, offsetX: 0, offsetY: 0 }, 2, 3, 1);
    expect(doubled.sx).toBeCloseTo(single.sx * 2, 10);
    expect(doubled.sy).toBeCloseTo(single.sy * 2, 10);
  });
});

describe("depthOf", () => {
  it("orders cells by distance from the camera, not by screen y", () => {
    // The whole point: a tall wall's top face sits high on screen but
    // still belongs behind anything in front of it.
    expect(depthOf(0, 0)).toBeLessThan(depthOf(1, 0));
    expect(depthOf(1, 0)).toBe(depthOf(0, 1));
    expect(depthOf(2, 2)).toBeGreaterThan(depthOf(1, 1));
  });
});

describe("fitProjection", () => {
  it("centres the map in the canvas", () => {
    const projection = fitProjection(FREE_3X3, 400, 300);
    const scene = buildScene(FREE_3X3, projection, { showGround: true });
    const midX = (scene.bounds.minX + scene.bounds.maxX) / 2;
    const midY = (scene.bounds.minY + scene.bounds.maxY) / 2;
    expect(midX).toBeCloseTo(200, 6);
    expect(midY).toBeCloseTo(150, 6);
  });

  it("keeps the whole map inside the canvas", () => {
    const projection = fitProjection(FREE_3X3, 400, 300, { padding: 20 });
    const { bounds } = buildScene(FREE_3X3, projection);
    expect(bounds.minX).toBeGreaterThanOrEqual(19.9);
    expect(bounds.maxX).toBeLessThanOrEqual(380.1);
    expect(bounds.minY).toBeGreaterThanOrEqual(19.9);
    expect(bounds.maxY).toBeLessThanOrEqual(280.1);
  });

  it("leaves room for extruded walls when a wall height is given", () => {
    const flat = fitProjection(FREE_3X3, 400, 300, { wallHeight: 0 });
    const tall = fitProjection(FREE_3X3, 400, 300, { wallHeight: 2 });
    // Taller content in the same canvas has to be drawn smaller.
    expect(tall.scale).toBeLessThan(flat.scale);
  });

  it("respects a non-square canvas", () => {
    const wide = fitProjection(FREE_3X3, 800, 200);
    const { bounds } = buildScene(FREE_3X3, wide);
    expect(bounds.maxY - bounds.minY).toBeLessThanOrEqual(200);
  });

  it("survives a degenerate map without dividing by zero", () => {
    const single = makeMap([0], 1, 1);
    const projection = fitProjection(single, 200, 200);
    expect(Number.isFinite(projection.scale)).toBe(true);
  });
});

describe("buildScene", () => {
  it("emits one ground quad per free cell", () => {
    const scene = buildScene(FREE_3X3, PROJECTION);
    expect(scene.facets).toHaveLength(9);
    expect(scene.facets.every((facet) => facet.kind === "ground")).toBe(true);
    expect(scene.facets.every((facet) => facet.points.length === 4)).toBe(true);
  });

  it("omits the floor when the ground is hidden", () => {
    expect(buildScene(FREE_3X3, PROJECTION, { showGround: false }).facets).toHaveLength(0);
  });

  it("extrudes an occupied cell into three visible faces", () => {
    const map = makeMap([0, 0, 0, 0, 100, 0, 0, 0, 0]);
    const scene = buildScene(map, PROJECTION, { showGround: false });
    expect(scene.facets).toHaveLength(3);
    expect(scene.facets.map((facet) => facet.face).sort()).toEqual(["left", "right", "top"]);
  });

  it("draws unknown space flat rather than as a wall", () => {
    // Unknown is absence of information; extruding it would read as an
    // obstacle that is not known to be there.
    const map = makeMap([0, 0, 0, 0, -1, 0, 0, 0, 0]);
    const scene = buildScene(map, PROJECTION, { showGround: false });
    expect(scene.facets).toHaveLength(1);
    expect(scene.facets[0].face).toBe("top");
    expect(scene.facets[0].kind).toBe("unknown");
  });

  it("raises the top face above the ground by the wall height", () => {
    const map = makeMap([100], 1, 1);
    const scene = buildScene(map, PROJECTION, { showGround: false, wallHeight: 1 });
    const top = scene.facets.find((facet) => facet.face === "top")!;
    const flat = buildScene(map, PROJECTION, { showGround: false, wallHeight: 0 }).facets[0];
    expect(top.points[0].sy).toBeLessThan(flat.points[0].sy);
  });

  it("sorts facets back to front", () => {
    const scene = buildScene(FREE_3X3, PROJECTION);
    const depths = scene.facets.map((facet) => facet.depth);
    expect([...depths].sort((a, b) => a - b)).toEqual(depths);
  });

  it("projects trajectory and plan into screen space", () => {
    const scene = buildScene(FREE_3X3, PROJECTION, {
      plannedPath: [
        { x: 0, y: 0 },
        { x: 1, y: 1 },
      ],
      trajectory: [
        { time: 0, x: 0, y: 0, theta: 0, linear_velocity: 0, angular_velocity: 0 },
        { time: 1, x: 2, y: 0, theta: 0, linear_velocity: 1, angular_velocity: 0 },
      ],
    });
    expect(scene.plan).toHaveLength(2);
    expect(scene.plan[0]).toEqual(project(PROJECTION, 0, 0, 0));
    expect(scene.trajectory[1]).toEqual(project(PROJECTION, 2, 0, 0));
  });

  it("leaves markers null when no poses are supplied", () => {
    const scene = buildScene(FREE_3X3, PROJECTION);
    expect(scene.start).toBeNull();
    expect(scene.goal).toBeNull();
    expect(scene.robot).toBeNull();
    expect(scene.obstacles).toEqual([]);
  });

  it("builds one obstacle marker per snapshot, positioned like the robot marker", () => {
    const scene = buildScene(FREE_3X3, PROJECTION, {
      obstacles: [
        { name: "person-1", x: 1, y: 1, radius: 0.3 },
        { name: "person-2", x: 2, y: 0, radius: 0.4 },
      ],
    });
    expect(scene.obstacles).toHaveLength(2);
    const [first, second] = scene.obstacles;
    expect(first.top).toEqual(project(PROJECTION, 1, 1, 0.35));
    expect(first.radiusX).toBeGreaterThan(0);
    expect(first.radiusY).toBeGreaterThan(0);
    expect(second.top).toEqual(project(PROJECTION, 2, 0, 0.35));
  });

  it("builds a robot marker with a raised top and a heading tip", () => {
    const scene = buildScene(FREE_3X3, PROJECTION, {
      robotPose: { x: 1, y: 1, theta: 0 },
      robotRadius: 0.5,
      robotHeight: 0.4,
    });
    const robot = scene.robot!;
    expect(robot.top.sy).toBeLessThan(robot.base.sy);
    // theta = 0 points along +x, which goes right on screen.
    expect(robot.heading.sx).toBeGreaterThan(robot.top.sx);
    expect(robot.radiusX).toBeGreaterThan(0);
    expect(robot.radiusY).toBeGreaterThan(0);
  });

  it("foreshortens the footprint circle into an ellipse", () => {
    const scene = buildScene(FREE_3X3, PROJECTION, {
      robotPose: { x: 1, y: 1, theta: Math.PI / 2 },
      robotRadius: 0.5,
    });
    const robot = scene.robot!;
    // Equal radii would mean the ground plane is not tilted at all.
    expect(robot.radiusX).toBeCloseTo(robot.radiusY, 6);
    expect(robot.radiusX).toBeLessThan(0.5 * PROJECTION.scale);
  });

  it("handles a map whose origin is not at zero", () => {
    const shifted: MapData = { ...FREE_3X3, origin: { x: -2, y: 3, theta: 0 } };
    const scene = buildScene(shifted, PROJECTION);
    expect(scene.facets[0].points[0]).toEqual(project(PROJECTION, -2, 3, 0));
  });
});
