/** Builders for the seed map/scenario offered in the UI.
 *
 * These are *starting points a user can edit*, not benchmark fixtures —
 * benchmark scenarios come from the backend.
 */

import type { MapData, Scenario } from "./types";

export const FREE = 0;
export const OCCUPIED = 100;
export const UNKNOWN = -1;

export function emptyBorderedMap(
  name: string,
  width = 40,
  height = 30,
  resolution = 0.25,
): MapData {
  const cells = new Array<number>(width * height).fill(FREE);
  for (let col = 0; col < width; col += 1) {
    cells[col] = OCCUPIED;
    cells[(height - 1) * width + col] = OCCUPIED;
  }
  for (let row = 0; row < height; row += 1) {
    cells[row * width] = OCCUPIED;
    cells[row * width + width - 1] = OCCUPIED;
  }
  return {
    name,
    width,
    height,
    resolution,
    origin: { x: 0, y: 0, theta: 0 },
    cells,
  };
}

/** Bordered map with two shelf rows and a central aisle. */
export function warehouseMap(name = "warehouse-demo"): MapData {
  const map = emptyBorderedMap(name, 48, 36, 0.25);
  const cells = [...map.cells];
  for (const row of [12, 13, 14, 22, 23, 24]) {
    for (let col = 8; col < 40; col += 1) {
      if (col >= 20 && col <= 25) continue; // aisle
      cells[row * map.width + col] = OCCUPIED;
    }
  }
  return { ...map, cells };
}

export function defaultScenario(map: MapData, name = "demo-scenario"): Scenario {
  const worldWidth = map.width * map.resolution;
  const worldHeight = map.height * map.resolution;
  return {
    name,
    description: "Created in the PlanBench web UI",
    robot: {
      radius: 0.3,
      max_linear_velocity: 1.0,
      max_angular_velocity: 2.0,
      max_linear_acceleration: 1.0,
      max_angular_acceleration: 3.0,
    },
    start_pose: { x: 1.5, y: 1.5, theta: 0 },
    goal_pose: { x: worldWidth - 1.5, y: worldHeight - 1.5, theta: 0 },
    goal_tolerance: 0.3,
    timeout_seconds: 120,
    simulation_dt: 0.05,
    static_obstacles: [],
  };
}
