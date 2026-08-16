/** The traffic editor, actually rendered.
 *
 * Everything else about this feature is tested either as data
 * (`lib/traffic`, `lib/sequencer`) or as a string search over the
 * source. Neither notices a component that throws the first time it is
 * drawn, and until this file existed the editor had never been rendered
 * once in the suite — a switch over the four motion laws, a hint with
 * four branches and a dozen translation keys, all of it unexecuted.
 *
 * `renderToStaticMarkup`, like the rest of the web tests: no jsdom and
 * no testing-library are installed, so this covers first render and not
 * clicking. What each control *does* is covered as data in
 * `lib/__tests__/traffic.test.ts`; what a click on the canvas does is
 * still only covered by hand (see the checklist in
 * docs/antongduy/reports/2026-08-15/).
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TrafficEditor } from "@/components/TrafficEditor";
import { blankMotion } from "@/lib/traffic";
import type { DynamicObstacle, Motion, WaypointMotion } from "@/lib/types";

const ANCHOR = { x: 2, y: 3 };

function obstacle(overrides: Partial<DynamicObstacle> = {}): DynamicObstacle {
  return {
    name: "crossing-amr",
    radius: 0.4,
    seed_time_offset: 45,
    seed_offset: 0,
    motion: {
      kind: "waypoint",
      waypoints: [
        { x: 20, y: 3 },
        { x: 20, y: 21 },
      ],
      speed: 0.8,
      loop: false,
      ping_pong: true,
    },
    ...overrides,
  };
}

function render(
  overrides: Partial<Parameters<typeof TrafficEditor>[0]> = {},
): string {
  return renderToStaticMarkup(
    <TrafficEditor
      obstacles={[obstacle()]}
      onChange={() => {}}
      selectedIndex={null}
      placement={null}
      onSelect={() => {}}
      onPlacementToggle={() => {}}
      onAdd={() => {}}
      onRemove={() => {}}
      onKindChange={() => {}}
      errors={[]}
      {...overrides}
    />,
  );
}

describe("an empty block", () => {
  it("says there is no traffic rather than showing nothing", () => {
    /* With no traffic *and* no noise a deterministic planner replays one
       episode per seed. Silence here reads as "this section does not
       apply to me". */
    const html = render({ obstacles: [] });
    expect(html).toContain("No moving traffic declared");
    expect(html).toContain("Add an obstacle");
  });

  it("still explains what traffic is for", () => {
    expect(render({ obstacles: [] })).toContain("one obstacle set is what makes two candidates");
  });
});

describe("one obstacle", () => {
  it("shows what it is and how fast", () => {
    const html = render();
    expect(html).toContain('value="crossing-amr"');
    expect(html).toContain('value="0.4"');
    expect(html).toContain('value="0.8"');
  });

  it("offers all four motion laws, not the two the mirror used to have", () => {
    const html = render();
    for (const label of [
      "Along waypoints",
      "Back and forth",
      "Random walk",
      "Straight, then stops",
    ]) {
      expect(html).toContain(label);
    }
  });

  it("marks the law this obstacle actually uses as the selected one", () => {
    const html = render();
    expect(html).toMatch(/<select[^>]*>[\s\S]*?<option value="waypoint" selected/);
  });
});

describe("each law shows its own fields and no others", () => {
  const laws: [Motion["kind"], string[], string[]][] = [
    ["waypoint", ["Waypoints", "Loop", "Ping-pong", "Speed (m/s)"], ["Period (s)", "Stops at (s)"]],
    ["periodic", ["Period (s)", "Phase (rad)"], ["Speed (m/s)", "Waypoints"]],
    [
      "random_walk",
      ["Heading held (s)", "Max distance from origin (m)", "Heading sequence"],
      ["Period (s)", "Waypoints"],
    ],
    ["sudden_stop", ["Stops at (s)", "Heading (°)"], ["Period (s)", "Waypoints"]],
  ];

  it.each(laws)("%s", (kind, present, absent) => {
    /* Rendered per law rather than as every field with the inapplicable
       ones greyed out: a disabled `period` box beside a waypoint route
       reads as a number that exists and happens to be unavailable, and
       it is neither. */
    const html = render({ obstacles: [obstacle({ motion: blankMotion(kind, ANCHOR) })] });
    for (const label of present) expect(html, `${kind} should show ${label}`).toContain(label);
    for (const label of absent) expect(html, `${kind} should not show ${label}`).not.toContain(label);
  });

  it("gives a sudden stop no end point to place", () => {
    /* That motion has a start, a direction and a stopping time. A button
       offering an "end" would be offering a field the contract does not
       have. */
    const html = render({ obstacles: [obstacle({ motion: blankMotion("sudden_stop", ANCHOR) })] });
    expect(html).toContain("Point the heading");
    expect(html).not.toContain("Place the end");
  });
});

describe("the seed head start", () => {
  it("offers one full cycle, with the number on the button", () => {
    // 2 x 18 m at 0.8 m/s, the shipped crossing deployment's own 45 s.
    expect(render()).toContain("Suggest (45s)");
  });

  it("tells a random walk it needs none, instead of the opposite", () => {
    /* The falsehood this replaced: every case with no number to suggest
       was told the offset "still has to be above zero". A random walk is
       the one motion the server lets sit at zero. */
    const html = render({
      obstacles: [obstacle({ motion: blankMotion("random_walk", ANCHOR) })],
    });
    expect(html).toContain("Zero is legal here");
    expect(html).not.toContain("still has to be above zero");
  });

  it("tells a route driven once that the number is theirs to choose", () => {
    const once: WaypointMotion = {
      ...(blankMotion("waypoint", ANCHOR) as WaypointMotion),
      loop: false,
      ping_pong: false,
    };
    const html = render({ obstacles: [obstacle({ motion: once })] });
    expect(html).toContain("no cycle to derive an offset from");
    expect(html).not.toContain("Suggest (");
  });

  it("asks for the missing numbers rather than claiming either", () => {
    const unfinished: WaypointMotion = {
      ...(blankMotion("waypoint", ANCHOR) as WaypointMotion),
      speed: Number.NaN,
    };
    const html = render({ obstacles: [obstacle({ motion: unfinished })] });
    expect(html).toContain("Fill in the route and the speed");
    /* And the missing number reaches the input as the empty box it
       already looks like. `value={NaN}` renders empty anyway and warns,
       which is how this was found — the warning was the only thing that
       distinguished it from a field nobody has filled in yet.

       What this does *not* prove is the typing itself: no DOM here, so
       the mapping from a cleared box to `NaN` is checked where it lives,
       in `numberFromInput` (lib/__tests__/traffic.test.ts). */
    expect(html).not.toContain('value="NaN"');
  });

  it("keeps the two seed numbers apart", () => {
    /* One picks *which* sequence of headings a walker gets; the other
       shifts *when* an obstacle's clock starts. Two obstacles can differ
       in either axis independently, so one label for both would be a
       lie. */
    const html = render({
      obstacles: [obstacle({ motion: blankMotion("random_walk", ANCHOR) })],
    });
    expect(html).toContain("Heading sequence");
    expect(html).toContain("Clock spread");
  });
});

describe("refusals from the server", () => {
  it("shows a rule addressed to the whole block", () => {
    /* Every traffic rule is a model validator on `EnvironmentSpec`, so
       pydantic addresses it to `environment`. Without a line for that
       path all five are invisible and filing is blocked with no reason
       given. */
    const html = render({
      errors: [{ path: "environment", message: "dynamic obstacle names must be unique" }],
    });
    expect(html).toContain("dynamic obstacle names must be unique");
  });

  it("puts a field constraint beside the obstacle it names", () => {
    const html = render({
      obstacles: [obstacle({ name: "first" }), obstacle({ name: "second" })],
      errors: [
        {
          path: "environment.dynamic_obstacles.1.radius",
          message: "Input should be greater than 0",
        },
      ],
    });
    expect(html).toContain("radius: Input should be greater than 0");
  });

  it("shows an address it does not recognise rather than dropping it", () => {
    /* An unrecognised path is still a reason somebody's document was
       refused. Filtering it away is how a refused deployment blocks
       filing while showing nothing. */
    const html = render({
      errors: [{ path: "environment.map", message: "map file not found" }],
    });
    expect(html).toContain("map file not found");
  });

  it("says nothing at all when the last check passed", () => {
    expect(render()).not.toContain("notice warn");
  });
});

describe("while something else is in flight", () => {
  it("disables every control", () => {
    const html = render({ disabled: true });
    const inputs = html.match(/<(input|select|button)[^>]*>/g) ?? [];
    expect(inputs.length).toBeGreaterThan(5);
    for (const control of inputs) expect(control).toContain("disabled");
  });
});

describe("placing points on the map", () => {
  it("lights the button for the field the next click belongs to", () => {
    const html = render({ placement: { index: 0, mode: "waypoint" } });
    expect(html).toContain('aria-pressed="true"');
  });

  it("presses nothing while the mission owns the click", () => {
    expect(render()).not.toContain('aria-pressed="true"');
  });
});

describe("selection without placement", () => {
  it("highlights the selected row even when the map places nothing", () => {
    /* The state the old `{index, mode}` selection could not express: an
       obstacle clicked on its body is focused, and no click is pending.
       The row must show it, or a click on the map appears to do
       nothing. */
    const html = render({ selectedIndex: 0 });
    expect(html).toContain('aria-current="true"');
    expect(html).not.toContain('aria-pressed="true"');
  });

  it("highlights nothing when nothing is selected", () => {
    expect(render()).not.toContain('aria-current="true"');
  });
});
