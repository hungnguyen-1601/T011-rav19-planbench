/** The grid layer, and why its colour is not a free choice.
 *
 * No jsdom and no canvas in this repo, so what is checked is the thing
 * that was actually wrong: a constant that only worked against one of
 * the two floors this canvas is drawn on.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");
const CANVAS = readFileSync(join(SRC, "components", "MapCanvas.tsx"), "utf8");
const CSS = readFileSync(join(SRC, "app", "globals.css"), "utf8");

/** `rgba(r,g,b,a)` as numbers, from the colour table. */
function ink(name: string): [number, number, number, number] {
  const hit = CANVAS.match(new RegExp(String.raw`${name}:\s*"rgba\(([^)]+)\)"`));
  if (!hit) throw new Error(`${name} is not an rgba constant`);
  const parts = hit[1].split(",").map((value) => Number(value.trim()));
  return [parts[0], parts[1], parts[2], parts[3]];
}

/** Composite an rgba ink over an opaque background, per channel. */
function over(colour: [number, number, number, number], background: [number, number, number]) {
  const [r, g, b, a] = colour;
  return [
    r * a + background[0] * (1 - a),
    g * a + background[1] * (1 - a),
    b * a + background[2] * (1 - a),
  ] as [number, number, number];
}

const DARK_FLOOR: [number, number, number] = [0x0b, 0x0d, 0x11];
const LIGHT_FLOOR: [number, number, number] = [0xee, 0xf1, 0xf5];

describe("the grid has to be visible on the floor it is drawn on", () => {
  it("is drawn on whichever floor the theme paints", () => {
    /* The canvas is cleared to transparent and free cells are skipped,
       so the floor is `--canvas-bg` showing through — two very different
       colours, not one. */
    expect(CANVAS).toContain("ctx.clearRect(0, 0, width, height)");
    expect(CSS).toContain("--canvas-bg: #0b0d11;");
    expect(CSS).toContain("--canvas-bg: #eef1f5;");
  });

  it("is not white, which was invisible on the light floor", () => {
    /* `rgba(255,255,255,0.045)` was correct against the dark floor it
       was written for and did nothing at all on the light one — the
       Grid checkbox appeared to be broken. */
    const [r, g, b] = ink("gridLine");
    expect([r, g, b]).not.toEqual([255, 255, 255]);
  });

  it("separates from both floors by enough to see", () => {
    /* The real requirement, checked as a number rather than by eye: a
       faint line still has to differ from what is behind it. */
    const colour = ink("gridLine");
    for (const [name, floor] of [
      ["dark", DARK_FLOOR],
      ["light", LIGHT_FLOOR],
    ] as const) {
      const drawn = over(colour, floor);
      const gap = Math.max(...drawn.map((value, index) => Math.abs(value - floor[index])));
      expect(gap, `${name} floor separation`).toBeGreaterThan(20);
    }
  });

  it("still refuses to draw a grid too fine to be one", () => {
    /* Below roughly six pixels a cell, the lines merge into a wash and
       the map reads as being a different colour rather than as being
       gridded. */
    expect(CANVAS).toContain("showGrid && cell >= 6");
  });
});
