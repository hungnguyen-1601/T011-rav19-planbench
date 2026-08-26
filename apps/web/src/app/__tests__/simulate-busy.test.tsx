/** What the test bench shows while an episode is being computed.
 *
 * `runOne` awaits the whole simulation before the socket opens, so the
 * press is followed by a wait in which nothing moves: the canvas holds
 * the world as it was and the status badge is the only hint. From the
 * outside that is a stalled application. These pin the two things that
 * say otherwise, and the one property that makes the overlay honest —
 * it *covers* the map rather than replacing it, because the map
 * underneath is still the answer to "did it take the deployment I
 * chose".
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(process.cwd(), "src");
const PAGE = readFileSync(join(ROOT, "app", "simulate", "page.tsx"), "utf8");
const CSS = readFileSync(join(ROOT, "app", "globals.css"), "utf8");
const EN = JSON.parse(readFileSync(join(ROOT, "lib", "i18n", "locales", "en.json"), "utf8"));
const VI = JSON.parse(readFileSync(join(ROOT, "lib", "i18n", "locales", "vi.json"), "utf8"));

describe("the wait after Run has a face", () => {
  it("shows the overlay exactly while the page is busy", () => {
    // `busy` is the state `runOne` sets before it awaits and clears in
    // its `finally` — the same window as the freeze, including the
    // branch where the episode fails.
    expect(PAGE).toContain("{busy ? (");
    expect(PAGE).toContain('className="simulate-map-busy"');
  });

  it("names the wait rather than only spinning", () => {
    expect(PAGE).toContain('t("bench.simulating")');
    expect(EN["bench.simulating"]).toBeTruthy();
    expect(VI["bench.simulating"]).toBeTruthy();
  });

  it("announces itself to a screen reader", () => {
    // A spinner is nothing to somebody who cannot see it, and the whole
    // point of the overlay is telling a person the app has not died.
    const overlay = PAGE.slice(PAGE.indexOf('className="simulate-map-busy"'));
    expect(overlay.slice(0, 200)).toContain('role="status"');
    expect(overlay.slice(0, 200)).toContain('aria-live="polite"');
    expect(overlay).toContain('aria-hidden="true"');
  });

  it("covers the map instead of unmounting it", () => {
    // If the overlay replaced the canvas, MapView would remount when it
    // cleared — a fresh canvas, and the deployment's world gone from
    // the screen for the length of the wait.
    const map = PAGE.indexOf("<MapView");
    const overlay = PAGE.indexOf('className="simulate-map-busy"');
    expect(map).toBeGreaterThan(-1);
    expect(overlay).toBeGreaterThan(map);
    expect(PAGE).not.toContain("busy ? (\n            <div className=\"simulate-map-busy\"");
  });

  it("dims everything except the canvas, and stops it taking clicks", () => {
    expect(PAGE).toContain('busy ? " is-simulating" : ""');
    const rule = ".simulate-workspace.is-simulating > *:not(.simulate-map-panel)";
    expect(CSS).toContain(rule);
    // Looking unavailable while still accepting a click is worse than
    // not looking unavailable at all.
    const block = CSS.slice(CSS.indexOf(rule));
    expect(block.slice(0, 200)).toContain("pointer-events: none");
  });

  it("keeps the overlay positioned against the map panel", () => {
    // `position: absolute` with no positioned ancestor escapes to the
    // page and covers whatever it lands on.
    const panel = CSS.slice(CSS.indexOf(".simulate-map-panel {"));
    expect(panel.slice(0, 120)).toContain("position: relative");
  });

  it("eases the spin for a reader who asked for less motion", () => {
    const reduced = CSS.slice(CSS.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(reduced).toContain("simulate-map-busy-spinner");
  });
});

describe("the assistant button on hover", () => {
  it("darkens the mark rather than only the ground", () => {
    // Deepening the background alone left the mark `--accent-contrast`
    // — white — so the one part the pointer is aimed at was the one
    // part that did not change.
    const hover = CSS.slice(CSS.indexOf(".agent-dock-launcher:hover"));
    const block = hover.slice(0, hover.indexOf("}"));
    expect(block).toContain("color:");
    expect(block).toContain("#000");
  });

  it("treats keyboard focus the same as hover", () => {
    // Reaching the button by keyboard should show the same affordance
    // as reaching it by pointer.
    expect(CSS).toContain(".agent-dock-launcher:focus-visible");
  });

  it("gives the pale ground enough accent to be a colour", () => {
    // At 12% of `--panel` the ground was the page, and the button read
    // as having gone see-through rather than as pale — the reader said
    // so. The accent share is what stops it.
    const hover = CSS.slice(CSS.indexOf(".agent-dock-launcher:hover"));
    const block = hover.slice(0, hover.indexOf("}"));
    expect(block).toContain("var(--accent) 32%");
    expect(block).not.toContain("var(--panel)");
  });

  it("draws the ring at full strength, so the button has an edge", () => {
    // A 55%-transparent border over the page is half of what made it
    // look see-through.
    const hover = CSS.slice(CSS.indexOf(".agent-dock-launcher:hover"));
    const block = hover.slice(0, hover.indexOf("}"));
    expect(block).toContain("border-color: var(--accent);");
  });

  it("thickens the mark, which is strokes rather than a filled shape", () => {
    // `Icon` draws `fill=none stroke=currentColor`, so on a pale ground
    // the whole button is four thin lines.
    expect(CSS).toContain(".agent-dock-launcher:hover svg");
    expect(CSS).toContain("stroke-width: 2.4;");
  });});
