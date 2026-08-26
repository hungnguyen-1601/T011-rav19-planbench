/** The placer in the arrangement `/decisions` uses.
 *
 * That page passes no mode and no pointer callbacks, and it has done so
 * since before the deployment form existed. When the component was
 * split into a canvas, a pair of buttons and the pose fields, this
 * wrapper became the thing that puts them back together — so what needs
 * proving is that the old shape still renders, uncontrolled, with all
 * three parts present.
 *
 * The split is checked here rather than only by reading the source
 * because a wrapper that composes three components can be wrong in a
 * way a string search cannot see: a part left out, or a prop that stops
 * reaching the one that needed it.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MissionPlacer } from "@/components/MissionPlacer";
import { emptyBorderedMap } from "@/lib/demoMap";
import type { Pose2D } from "@/lib/types";

const MAP = emptyBorderedMap("test", 20, 15, 0.5);
const START: Pose2D = { x: 1.5, y: 4.5, theta: 0 };
const GOAL: Pose2D = { x: 8.5, y: 4.5, theta: Math.PI / 2 };

function render(overrides: Partial<Parameters<typeof MissionPlacer>[0]> = {}): string {
  return renderToStaticMarkup(
    <MissionPlacer
      map={MAP}
      start={START}
      goal={GOAL}
      onChange={() => {}}
      startNote="where it sets off"
      goalNote="where it has to reach"
      {...overrides}
    />,
  );
}

describe("the arrangement /decisions relies on", () => {
  it("renders the buttons, the map and both pose readouts together", () => {
    const html = render();
    expect(html).toContain("Place the start");
    expect(html).toContain("Place the goal");
    expect(html).toContain('data-testid="map-canvas"');
    expect(html).toContain("where it sets off");
    expect(html).toContain("where it has to reach");
  });

  it("opens placing the start when nobody says otherwise", () => {
    /* Uncontrolled is the mode this page has always used; the
       deployment form is the one that lifts it out. */
    const html = render();
    expect(html).toMatch(/aria-pressed="true"[^>]*>Place the start/);
  });

  it("shows both poses as numbers, in degrees", () => {
    /* The contract stores radians and nobody types 1.5708 for a
       quarter turn. */
    const html = render();
    expect(html).toContain('value="1.5"');
    expect(html).toContain('value="90"');
  });

  it("says a pose is unset rather than drawing it as a row of zeroes", () => {
    /* 0,0 is a coordinate somebody could mean. */
    const html = render({ goal: null });
    expect(html).toContain("Goal: click the map");
    expect(html).not.toContain("where it has to reach");
  });

  it("obeys a mode handed in from outside", () => {
    const html = render({ mode: "goal", onModeChange: () => {} });
    expect(html).toMatch(/aria-pressed="true"[^>]*>Place the goal/);
  });

  it("hands the caption over while somebody else's mode owns the click", () => {
    /* This component has nothing true to say about placing a waypoint,
       so the caller supplies the sentence. */
    const html = render({
      mode: "waypoint",
      onModeChange: () => {},
      modeNote: "Click the map to add a waypoint to cart",
    });
    expect(html).toContain("Click the map to add a waypoint to cart");
  });

  it("disables everything that edits the mission when the page is busy", () => {
    /* Everything that *edits*, which is not everything on screen: the
       flat/raised switch stays live on purpose. It changes how the map
       is drawn and touches no document, so freezing it would stop an
       author looking at what they just filed while it is being filed. */
    const html = render({ disabled: true });
    /* `map-view-control` marks the same exemption the switch above has
       and for the same reason: the grid checkbox decides how the map is
       drawn, not what the document says. Filtered by name rather than by
       shape so a future field cannot slip through by being a checkbox
       too. */
    const inputs = (html.match(/<input[^>]*>/g) ?? []).filter(
      (input) => !input.includes("map-view-control"),
    );
    expect(inputs.length).toBeGreaterThan(4);
    for (const input of inputs) expect(input).toContain("disabled");
    for (const label of ["Place the start", "Place the goal"]) {
      const button = html.match(new RegExp(`<button[^>]*>${label}`))?.[0] ?? "";
      expect(button, `${label} should be disabled`).toContain("disabled");
    }
  });
});
