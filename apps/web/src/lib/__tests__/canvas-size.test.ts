/** How big the map is drawn, and when the form stops being two columns.
 *
 * The failure this guards is quiet: `MapCanvas` maps a press to world
 * coordinates assuming its drawing surface and its CSS box are the same
 * size. Stretch the element without telling the component and every
 * click lands somewhere other than the pointer — while the map still
 * looks perfectly right.
 */

import { describe, expect, it } from "vitest";

import {
  CANVAS_MIN_SIDE_BY_SIDE_PX,
  COLUMN_GAP_PX,
  MAX_CANVAS_WIDTH_PX,
  PANEL_MIN_PX,
  SIDE_BY_SIDE_MIN_PX,
  canvasSize,
  sideBySide,
} from "@/lib/canvasSize";

describe("fitting the canvas to its column", () => {
  it("takes the room it is given", () => {
    expect(canvasSize(600, 0.75).width).toBe(600);
  });

  it("stops widening past the point extra pixels buy detail", () => {
    expect(canvasSize(2000, 0.75).width).toBe(MAX_CANVAS_WIDTH_PX);
  });

  it("shrinks to a phone rather than overflowing it", () => {
    /* An earlier draft floored the canvas at 480 px, which is a
       statement about the *layout* and made a 390 px screen scroll
       sideways. */
    expect(canvasSize(390, 0.75).width).toBe(390);
  });

  it("draws full size for the frame before it has been measured", () => {
    /* A container reports 0 until the observer first fires. Drawing at
       zero would divide by it in the viewport maths. */
    expect(canvasSize(0, 0.75).width).toBe(MAX_CANVAS_WIDTH_PX);
    expect(canvasSize(Number.NaN, 0.75).width).toBe(MAX_CANVAS_WIDTH_PX);
  });

  it("keeps the map's proportions", () => {
    expect(canvasSize(600, 0.5).height).toBe(300);
  });

  it("refuses to draw a corridor as a sliver or a tower as a wall", () => {
    /* A 30:1 aisle to scale is a few pixels tall and unusable; a very
       tall map would push the controls off the screen. */
    expect(canvasSize(600, 0.02).height).toBe(270);
    expect(canvasSize(600, 40).height).toBe(720);
  });

  it("falls back to a sane shape for a map that has not loaded", () => {
    expect(canvasSize(600, Number.NaN).height).toBe(450);
    expect(canvasSize(600, 0).height).toBe(450);
  });
});

describe("when the panel may sit beside the map", () => {
  it("derives the threshold from the two minimums rather than a round number", () => {
    expect(SIDE_BY_SIDE_MIN_PX).toBe(CANVAS_MIN_SIDE_BY_SIDE_PX + PANEL_MIN_PX + COLUMN_GAP_PX);
  });

  it("splits exactly at the width where both fit", () => {
    expect(sideBySide(SIDE_BY_SIDE_MIN_PX)).toBe(true);
    expect(sideBySide(SIDE_BY_SIDE_MIN_PX - 1)).toBe(false);
  });

  it("stacks on a phone", () => {
    expect(sideBySide(390)).toBe(false);
  });

  it("treats an unmeasured container as too narrow rather than guessing wide", () => {
    /* One column is the safe first paint: it fits either way, and the
       observer corrects it a frame later. */
    expect(sideBySide(0)).toBe(false);
    expect(sideBySide(Number.NaN)).toBe(false);
  });
});
