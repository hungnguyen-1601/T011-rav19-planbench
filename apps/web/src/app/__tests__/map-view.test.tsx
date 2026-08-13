/** Every map in the app can be seen flat or raised.
 *
 * **The gap An found by using it.** The raised view (`Scene25D`) shipped
 * early and exactly one screen used it — the scenario library. Every
 * other map was flat, including the two that most want a sense of the
 * space: the test bench, where you watch a robot try a doorway, and the
 * deployment form, where you place a mission in one.
 *
 * The first attempt added a toggle to the test bench alone. That is the
 * mechanism that produced the inconsistency in the first place — N
 * surfaces, N chances to forget — so the swap moved into `MapView`, which
 * every map-drawing surface now goes through. This file's last test is
 * the one that matters: it walks the app and fails on a screen that draws
 * a map any other way.
 *
 * **Neither view replaces the other.** Top-down is where a coordinate is
 * read, a tolerance circle is measured and a cell is clicked; raised is
 * where "will it fit through there" is felt. So both are always offered
 * and the pages do not choose for the reader.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const VIEW = readFileSync(join(SRC, "components", "MapView.tsx"), "utf8");
const TRACE = readFileSync(join(SRC, "components", "TraceViewer.tsx"), "utf8");

/** Every `.tsx` under `src`, so a new page is covered the day it lands. */
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return entry === "__tests__" ? [] : sources(path);
    return path.endsWith(".tsx") ? [path] : [];
  });
}

describe("one component owns the swap", () => {
  it("offers both modes and remembers which is showing", () => {
    expect(VIEW).toContain('useState<MapViewMode>(initialMode)');
    expect(VIEW).toContain('mode === "raised"');
    expect(VIEW).toContain("<Scene25D");
    expect(VIEW).toContain("<MapCanvas");
  });

  it("opens flat unless a screen asks otherwise", () => {
    /* Every screen was flat before this component. A default of raised
       would trade the precise view for the evocative one everywhere at
       once, which is not a change anybody asked for. */
    expect(VIEW).toContain('initialMode = "flat"');
  });

  it("obeys the same layer checkboxes in both views", () => {
    /* A path hidden in one view and drawn in the other is two answers to
       one question. */
    expect(VIEW).toContain("canvas.showPlan === false ? [] : canvas.plannedPath");
    expect(VIEW).toContain("canvas.showTrajectory === false ? [] : canvas.trajectory");
  });

  it("says where editing happens instead of eating the clicks", () => {
    /* The raised projection has no inverse: a screen pixel maps to a ray
       through the scene, not to a cell. Accepting clicks and dropping
       them reads as a broken canvas. */
    expect(VIEW).toContain("canvas.onWorldClick !== undefined");
    expect(VIEW).toContain("mapView.editInFlat");
    expect((en as Record<string, string>)["mapView.editInFlat"]).toContain("inverse projection");
    expect(vi).toHaveProperty("mapView.editInFlat");
  });
});

describe("the trace viewer swaps too, and says what the swap costs", () => {
  it("offers both modes", () => {
    expect(TRACE).toContain('useState<"flat" | "raised">("flat")');
    expect(TRACE).toContain("<Scene25D");
  });

  it("names the thing the raised view cannot show", () => {
    /* Colouring the path by clearance is why this viewer has its own
       drawing code at all. Losing it silently would make the two views
       look interchangeable when they are not. */
    expect(TRACE).toContain("trace.flatHasClearance");
    expect((en as Record<string, string>)["trace.flatHasClearance"]).toContain("clearance");
  });

  it("builds the raised map from the trace's own grid", () => {
    expect(TRACE).toContain("cells: Array.from(cells,");
  });
});

describe("no screen draws a map any other way", () => {
  it("routes every map through MapView, or through a viewer that swaps", () => {
    /* The guard for the actual mistake: adding the toggle page by page.
       `MapCanvas` and `Scene25D` are the two renderers, and only
       `MapView` — plus `TraceViewer`, which owns its own swap for the
       clearance colouring — may reach for them directly. */
    const allowed = new Set(
      ["components/MapView.tsx", "components/MapCanvas.tsx", "components/Scene25D.tsx",
       "components/TraceViewer.tsx"].map((path) => join(SRC, ...path.split("/"))),
    );
    const offenders = sources(SRC)
      .filter((path) => !allowed.has(path))
      .filter((path) => {
        const text = readFileSync(path, "utf8");
        return text.includes("<MapCanvas") || text.includes("<Scene25D");
      })
      .map((path) => path.replace(SRC, ""));
    expect(offenders).toEqual([]);
  });

  it("finds the surfaces it claims to be checking", () => {
    /* An empty sweep would make the assertion above vacuously true. */
    const users = sources(SRC).filter((path) => readFileSync(path, "utf8").includes("<MapView"));
    expect(users.length).toBeGreaterThanOrEqual(5);
  });
});
