/** One grid switch, obeyed by both views, on every canvas.
 *
 * The 2.5D view had no grid and looked like it did: its floor is one
 * quad per free cell, filled and never stroked, so the faint lattice on
 * it was the anti-aliased seam between neighbours. Nothing could switch
 * that off because nothing had drawn it.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");
const VIEW = readFileSync(join(SRC, "components", "MapView.tsx"), "utf8");
const SCENE = readFileSync(join(SRC, "components", "Scene25D.tsx"), "utf8");
const BENCH = readFileSync(join(SRC, "app", "simulate", "page.tsx"), "utf8");
const FORM = readFileSync(join(SRC, "components", "DeploymentForm.tsx"), "utf8");

describe("the raised view obeys the same switch as the flat one", () => {
  it("takes a grid flag at all", () => {
    /* It used to be withheld here on the reasoning that raising the
       cells *is* the grid. True of the walls, never of the floor. */
    expect(SCENE).toContain("showGrid?: boolean;");
    expect(VIEW).toContain("showGrid={showGrid}");
  });

  it("draws the floor lines rather than leaving them to anti-aliasing", () => {
    /* One code path for both states, so "grid off" is a floor with no
       lines on it rather than one with faint accidental ones. */
    expect(SCENE).toContain("ctx.strokeStyle = showGrid ? COLOR.gridLine : fill;");
    expect(SCENE).toContain("gridLine:");
  });

  it("redraws when the flag changes", () => {
    /* `scene` is memoised on the projection, so toggling a layer
       changes nothing the draw effect watches unless the flag is named
       in its dependencies. */
    expect(SCENE).toContain("[scene, width, height, showGrid, showPlan, showTrajectory]");
  });

  it("sends the flag to the flat canvas from the same place", () => {
    /* Both views read one value or they are two answers to one
       question. */
    expect(VIEW).toContain("<MapCanvas {...canvas} showGrid={showGrid} />");
  });
});

describe("every canvas can turn its grid off", () => {
  it("carries its own switch when the page has not brought one", () => {
    /* The scenario library, the scenario editor, the map painter and
       the decision preview all had a grid on with no way to reach it:
       `MapCanvas` defaults it true and nothing above them offered a
       control. */
    expect(VIEW).toContain("const [ownGrid, setOwnGrid] = useState(true)");
    expect(VIEW).toContain('className="map-view-grid"');
  });

  it("stands down when the page controls the flag", () => {
    /* Two checkboxes for one flag are two controls that can disagree on
       screen while agreeing in state. */
    expect(VIEW).toContain("const controlled = canvas.showGrid !== undefined;");
    expect(VIEW).toContain("{controlled ? null : (");
    // The two pages that bring their own.
    expect(BENCH).toContain("showGrid={showGrid}");
    expect(FORM).toContain("showGrid={showGrid}");
  });

  it("marks the switch as a view control, not a field", () => {
    /* It decides how the map is drawn, not what the document says — the
       same exemption the flat/raised buttons already have from being
       frozen while a form is busy. */
    expect(VIEW).toContain('className="map-view-control"');
  });
});
