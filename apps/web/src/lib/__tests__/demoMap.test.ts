import { describe, expect, it } from "vitest";
import { FREE, OCCUPIED, defaultScenario, emptyBorderedMap, warehouseMap } from "../demoMap";

describe("emptyBorderedMap", () => {
  const map = emptyBorderedMap("m", 6, 5, 0.5);

  it("has the requested dimensions", () => {
    expect(map.cells).toHaveLength(30);
    expect(map.width).toBe(6);
    expect(map.height).toBe(5);
  });

  it("walls the border and frees the interior", () => {
    for (let col = 0; col < map.width; col += 1) {
      expect(map.cells[col]).toBe(OCCUPIED);
      expect(map.cells[(map.height - 1) * map.width + col]).toBe(OCCUPIED);
    }
    for (let row = 0; row < map.height; row += 1) {
      expect(map.cells[row * map.width]).toBe(OCCUPIED);
      expect(map.cells[row * map.width + map.width - 1]).toBe(OCCUPIED);
    }
    expect(map.cells[1 * map.width + 1]).toBe(FREE);
  });
});

describe("warehouseMap", () => {
  const map = warehouseMap();

  it("keeps a free aisle through the shelves", () => {
    for (const row of [12, 13, 14, 22, 23, 24]) {
      expect(map.cells[row * map.width + 22]).toBe(FREE); // aisle
      expect(map.cells[row * map.width + 10]).toBe(OCCUPIED); // shelf
    }
  });
});

describe("defaultScenario", () => {
  it("places start and goal inside the map and apart", () => {
    const map = emptyBorderedMap("m", 40, 30, 0.25);
    const scenario = defaultScenario(map);
    expect(scenario.start_pose.x).toBeGreaterThan(0);
    expect(scenario.goal_pose.x).toBeLessThan(map.width * map.resolution);
    expect(scenario.goal_pose.y).toBeLessThan(map.height * map.resolution);
    expect(scenario.start_pose).not.toEqual(scenario.goal_pose);
    expect(scenario.simulation_dt).toBeLessThan(scenario.timeout_seconds);
  });
});
