/** World <-> canvas coordinate transforms (pure, unit-tested).
 *
 * World: metres, y up. Canvas: pixels, y down. The map's origin cell
 * (row 0, col 0) sits at the world origin corner.
 */

import type { MapData } from "./types";

export interface Viewport {
  scale: number; // pixels per metre
  offsetX: number; // canvas x of world origin.x
  offsetY: number; // canvas y of world origin.y (bottom of the map)
}

export function fitViewport(
  map: Pick<MapData, "width" | "height" | "resolution" | "origin">,
  canvasWidth: number,
  canvasHeight: number,
  padding = 10,
): Viewport {
  const worldWidth = map.width * map.resolution;
  const worldHeight = map.height * map.resolution;
  const scale = Math.min(
    (canvasWidth - 2 * padding) / worldWidth,
    (canvasHeight - 2 * padding) / worldHeight,
  );
  return {
    scale,
    offsetX: padding - map.origin.x * scale,
    offsetY: canvasHeight - padding + map.origin.y * scale,
  };
}

export function worldToCanvas(
  viewport: Viewport,
  x: number,
  y: number,
): { cx: number; cy: number } {
  return { cx: viewport.offsetX + x * viewport.scale, cy: viewport.offsetY - y * viewport.scale };
}

export function canvasToWorld(
  viewport: Viewport,
  cx: number,
  cy: number,
): { x: number; y: number } {
  return { x: (cx - viewport.offsetX) / viewport.scale, y: (viewport.offsetY - cy) / viewport.scale };
}

/** Grid cell (row, col) containing a world point, or null when outside. */
export function worldToCell(
  map: Pick<MapData, "width" | "height" | "resolution" | "origin">,
  x: number,
  y: number,
): { row: number; col: number } | null {
  const col = Math.floor((x - map.origin.x) / map.resolution);
  const row = Math.floor((y - map.origin.y) / map.resolution);
  if (row < 0 || row >= map.height || col < 0 || col >= map.width) {
    return null;
  }
  return { row, col };
}
