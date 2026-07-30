import { describe, expect, it } from "vitest";
import { canvasToWorld, fitViewport, worldToCanvas, worldToCell } from "../transform";

const MAP = { width: 10, height: 8, resolution: 0.5, origin: { x: 0, y: 0, theta: 0 } };

describe("fitViewport", () => {
  it("fits the world into the canvas with padding", () => {
    // world 5 x 4 m into 520 x 420 px with 10 px padding -> scale limited by x: 500/5 = 100
    const viewport = fitViewport(MAP, 520, 420, 10);
    expect(viewport.scale).toBe(100);
    expect(viewport.offsetX).toBe(10);
    expect(viewport.offsetY).toBe(410);
  });

  it("accounts for a non-zero origin", () => {
    const shifted = { ...MAP, origin: { x: -2, y: -1, theta: 0 } };
    const viewport = fitViewport(shifted, 520, 420, 10);
    // world origin sits at padding + 2 m to the right of the canvas left edge
    expect(viewport.offsetX).toBe(10 + 2 * viewport.scale);
    expect(viewport.offsetY).toBe(410 - 1 * viewport.scale);
  });
});

describe("worldToCanvas / canvasToWorld", () => {
  const viewport = fitViewport(MAP, 520, 420, 10);

  it("flips the y axis", () => {
    const origin = worldToCanvas(viewport, 0, 0);
    const above = worldToCanvas(viewport, 0, 1);
    expect(above.cy).toBeLessThan(origin.cy);
    expect(above.cx).toBe(origin.cx);
  });

  it("round-trips", () => {
    for (const [x, y] of [
      [0, 0],
      [1.25, 3.5],
      [4.9, 0.1],
    ]) {
      const { cx, cy } = worldToCanvas(viewport, x, y);
      const back = canvasToWorld(viewport, cx, cy);
      expect(back.x).toBeCloseTo(x, 9);
      expect(back.y).toBeCloseTo(y, 9);
    }
  });
});

describe("worldToCell", () => {
  it("maps world points to row/col", () => {
    expect(worldToCell(MAP, 0.25, 0.25)).toEqual({ row: 0, col: 0 });
    expect(worldToCell(MAP, 1.1, 0.3)).toEqual({ row: 0, col: 2 });
    expect(worldToCell(MAP, 0.1, 1.6)).toEqual({ row: 3, col: 0 });
  });

  it("returns null outside the map", () => {
    expect(worldToCell(MAP, -0.1, 1)).toBeNull();
    expect(worldToCell(MAP, 5.0, 1)).toBeNull(); // width 10 * 0.5 = 5.0 is past the last column
    expect(worldToCell(MAP, 1, 4.0)).toBeNull();
  });
});
