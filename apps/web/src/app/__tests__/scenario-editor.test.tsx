/** The scenario editor surface (plan 2.3).
 *
 * What has to hold: the browser never decides a scenario is valid, it
 * never evaluates motion laws, it cannot set the evaluation split or a
 * difficulty, and an edit invalidates the verdict shown on screen.
 *
 * Source-level, matching the other page tests: these pages sit behind an
 * effect and a fetch, so a first paint shows only a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { NAV_SECTIONS } from "../../lib/navigation";

const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");

const LIST = read("app", "scenarios", "page.tsx");
const EDITOR = read("app", "scenarios", "[id]", "page.tsx");
const CANVAS = read("components", "MapCanvas.tsx");
const TYPES = read("lib", "types.ts");

describe("validation belongs to the engine, not the browser", () => {
  it("asks the backend to validate", () => {
    expect(EDITOR).toContain("/scenarios/validate");
  });

  it("renders the errors the engine returned rather than its own", () => {
    expect(EDITOR).toContain("validation.errors.map");
    expect(EDITOR).toContain("scenarios.invalid");
  });

  it("says a scenario is unvalidated until the backend has spoken", () => {
    expect(EDITOR).toContain("scenarios.notValidatedYet");
  });

  it("drops the verdict whenever the scenario changes", () => {
    // A stale "valid" badge next to moved geometry is the one failure
    // this flow exists to prevent.
    expect(EDITOR).toContain("setValidation(null)");
  });
});

describe("motion is never evaluated in the browser", () => {
  it("gets obstacle positions from the preview endpoint", () => {
    expect(EDITOR).toContain("/scenarios/preview");
  });

  it("passes the seed, because traffic timing depends on it", () => {
    expect(EDITOR).toContain("seed: draft.random_seed");
    expect(en["scenarios.previewHint"]).toContain("seed");
  });

  it("takes resolved positions on the canvas, not motion laws", () => {
    expect(CANVAS).toContain("ObstacleMarker");
    expect(CANVAS).toContain("position: Point2D");
    expect(CANVAS).not.toContain("Math.cos(2 * Math.PI");
  });

  it("labels which instant the drawing shows", () => {
    expect(CANVAS).toContain("previewTime");
    expect(CANVAS).toContain("t = ");
  });
});

describe("the canvas is reused rather than duplicated", () => {
  it("draws both obstacle kinds through MapCanvas", () => {
    expect(EDITOR).toContain("<MapCanvas");
    expect(EDITOR).toContain("staticObstacles=");
    expect(EDITOR).toContain("dynamicObstacles=");
  });

  it("handles circles and rectangles", () => {
    expect(CANVAS).toContain('obstacle.type === "circle"');
    expect(CANVAS).toContain("obstacle.max_x");
  });
});

describe("the author cannot decide the evaluation protocol", () => {
  it("says the split is not editable here", () => {
    expect(EDITOR).toContain("scenarios.protocolNotice");
    expect(en["scenarios.protocolNotice"]).toContain("reviewed protocol change");
  });

  it("never posts a split", () => {
    expect(EDITOR).not.toContain("split:");
  });

  it("says difficulty is unmeasured until a calibration covers it", () => {
    expect(en["scenarios.protocolNotice"]).toContain("difficulty");
  });

  it("shows the split read-only in the list", () => {
    expect(LIST).toContain("SplitBadge");
    expect(LIST).toContain("item.split");
  });
});

describe("placing things on the map", () => {
  it("offers a tool per element the MVP supports", () => {
    for (const tool of ["start", "goal", "circle", "rectangle", "waypoint"]) {
      expect(en[`scenarios.place.${tool}` as keyof typeof en]).toBeTruthy();
      expect(vi[`scenarios.place.${tool}` as keyof typeof vi]).toBeTruthy();
    }
  });

  it("says what the next click will do", () => {
    expect(EDITOR).toContain("scenarios.mode.");
  });

  it("edits headings explicitly rather than by dragging", () => {
    expect(EDITOR).toContain("scenarios.startHeading");
    expect(EDITOR).toContain("scenarios.goalHeading");
  });

  it("needs two waypoints before a moving obstacle can be added", () => {
    expect(EDITOR).toContain("pendingWaypoints.length < 2");
  });
});

describe("seeded traffic is not left as a silent default", () => {
  it("defaults a new moving obstacle to a non-zero seed spread", () => {
    expect(EDITOR).toContain("seed_time_offset: 10");
  });

  it("warns when an obstacle would replay identically on every seed", () => {
    expect(EDITOR).toContain("scenarios.zeroOffsetWarning");
    expect(en["scenarios.zeroOffsetWarning"]).toContain("no new evidence");
  });
});

describe("the editor is reachable and typed", () => {
  it("has a sidebar entry that requires a session", () => {
    const items = NAV_SECTIONS.flatMap((section) => section.items);
    const entry = items.find((item) => item.href === "/scenarios");
    expect(entry).toBeTruthy();
    expect(entry?.session).toBe(true);
  });

  it("types obstacles instead of leaving them unknown", () => {
    expect(TYPES).toContain("static_obstacles?: StaticObstacle[]");
    expect(TYPES).toContain("dynamic_obstacles?: DynamicObstacle[]");
    expect(TYPES).not.toContain("static_obstacles?: unknown[]");
  });
});

describe("both locales carry the new strings", () => {
  const keys = [
    "nav.scenarios",
    "scenarios.title",
    "scenarios.subtitle",
    "scenarios.create",
    "scenarios.editorSubtitle",
    "scenarios.protocolNotice",
    "scenarios.staticObstacles",
    "scenarios.dynamicObstacles",
    "scenarios.seedOffsetHint",
    "scenarios.zeroOffsetWarning",
    "scenarios.previewHint",
    "scenarios.validate",
    "scenarios.valid",
    "scenarios.invalid",
    "scenarios.notValidatedYet",
    "scenarios.save",
    "scenarios.empty.title",
  ];

  it.each(keys)("%s is translated in English and Vietnamese", (key) => {
    expect((en as Record<string, string>)[key]).toBeTruthy();
    expect((vi as Record<string, string>)[key]).toBeTruthy();
  });

  it("keeps the placeholders in both languages", () => {
    expect(en["scenarios.protocolNotice"]).toContain("{split}");
    expect(vi["scenarios.protocolNotice"]).toContain("{split}");
    expect(en["scenarios.obstacleCount"]).toContain("{dynamic}");
    expect(vi["scenarios.obstacleCount"]).toContain("{dynamic}");
  });

  it("does not leave the Vietnamese explanation as the English one", () => {
    expect(vi["scenarios.previewHint"]).not.toEqual(en["scenarios.previewHint"]);
    expect(vi["scenarios.seedOffsetHint"]).not.toEqual(en["scenarios.seedOffsetHint"]);
  });
});
