/** The deployment form, actually rendered.
 *
 * **Everything else about this form is checked by reading its source.**
 * That is how the schema drift guard works, and it has to — a Python
 * test cannot import a React component. But a string search cannot tell
 * a control that renders from one that throws on first paint, and this
 * form had just been rebuilt from a single column into two columns and
 * seven tabbed panels without ever being drawn once in the suite. The
 * traffic editor's own render test found a real defect the first time
 * it ran; this is the same bet on the bigger component.
 *
 * `renderToStaticMarkup`, like the rest of the web tests: no jsdom is
 * installed, so effects do not run. Two consequences worth knowing
 * rather than working around: the container measures 0, so the layout
 * renders in its one-column form, and no map is fetched, so the canvas
 * shows its loading line. Both are real states the form has.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DeploymentForm } from "@/components/DeploymentForm";
import type { ProfileDraft } from "@/lib/deployments";

/** A draft shaped like the one `GET /task-profiles/template` returns. */
function draftOf(overrides: Record<string, unknown> = {}): ProfileDraft {
  return {
    id: "",
    claim_level: "deployment",
    deployment_role: "acceptance",
    robot: {
      type: "differential_drive",
      radius: 0.26,
      max_linear_velocity: 1.0,
      max_angular_velocity: 1.5,
      max_linear_acceleration: 0.8,
      max_angular_acceleration: 2.0,
      control_period: 0.05,
    },
    constraints: {
      success_rate_min: 0.95,
      collision_probability_max: 0.01,
      no_path_rate_max: 0.02,
      goal_tolerance_m: 0.25,
      goal_tolerance_rad: 3.15,
      episode_timeout_s: 120,
      stuck_threshold_s: 10,
      clearance_warning_m: 0.3,
    },
    clearance_preference: 1.0,
    environment: {
      map: "maps/open_hall.pgm",
      map_yaml: "maps/open_hall.yaml",
      sensor_noise: {
        lidar_range_sigma_m: 0.02,
        wheel_slip_fraction: 0.02,
        localization_drift_m: 0.1,
        localization_jump_probability: 0.02,
        lidar_dropout_probability: 0.02,
        odometry_bias_fraction: 0.01,
        command_latency_steps: 2,
      },
      dynamic_obstacles: [],
    },
    replanning: { enabled: false },
    recovery: { enabled: false },
    hardware: {
      target_device: "jetson_orin_nano",
      total_ram_mb: 8192,
      available_ram_mb: 3277,
      ram_budget_breakdown: {
        os_and_middleware_mb: 1024,
        perception_stack_mb: 2048,
        localization_mapping_mb: 1024,
        logging_and_reserve_mb: 819,
      },
    },
    ...overrides,
  } as ProfileDraft;
}

function render(overrides: Partial<Parameters<typeof DeploymentForm>[0]> = {}): string {
  return renderToStaticMarkup(
    <DeploymentForm
      onSubmit={async () => {}}
      busy={false}
      fieldErrors={[]}
      draft={draftOf()}
      onDraftChange={() => {}}
      {...overrides}
    />,
  );
}

describe("before the template arrives", () => {
  it("says it is loading rather than drawing an empty form", () => {
    const html = renderToStaticMarkup(
      <DeploymentForm
        onSubmit={async () => {}}
        busy={false}
        fieldErrors={[]}
        draft={null}
        onDraftChange={() => {}}
      />,
    );
    expect(html).toContain("Loading");
  });
});

describe("what the author sees first", () => {
  it("puts the identity fields above the tabs, not behind one", () => {
    /* They are what the deployment *is* rather than one aspect of it,
       and burying them would make the first thing anybody types the one
       thing they have to go looking for. */
    const html = render();
    const identity = html.indexOf("Deployment id");
    const strip = html.indexOf('role="tablist"');
    expect(identity).toBeGreaterThan(-1);
    expect(strip).toBeGreaterThan(-1);
    expect(identity).toBeLessThan(strip);
  });

  it("opens on the mission, the tab the map beside it is for", () => {
    expect(render()).toMatch(/id="deployment-form-tab-mission"[^>]*aria-selected="true"/);
  });
});

describe("the seven panels", () => {
  const TABS = ["mission", "traffic", "robot", "constraints", "noise", "policies", "hardware"];

  it("offers all of them", () => {
    const html = render();
    for (const tab of TABS) expect(html).toContain(`id="deployment-form-tab-${tab}"`);
  });

  it("keeps every panel mounted, hiding the six not chosen", () => {
    /* The property no source search can see. Unmounting would rebuild
       the noise switches' remembered amplitudes and the chosen vehicle
       every time somebody glanced at another tab. */
    const html = render();
    for (const tab of TABS) expect(html).toContain(`id="deployment-form-panel-${tab}"`);
    expect((html.match(/role="tabpanel"[^>]*hidden/g) ?? []).length).toBe(6);
  });

  it("puts each control on the tab that owns it", () => {
    /* One representative field per tab: the drift guard already
       proves every contract field has a control somewhere in the file,
       so what is left to check is that they render on the right
       panel. */
    const html = render();
    const panel = (tab: string) => {
      const from = html.indexOf(`id="deployment-form-panel-${tab}"`);
      const next = html.indexOf('role="tabpanel"', from + 1);
      return html.slice(from, next === -1 ? undefined : next);
    };
    expect(panel("robot")).toContain("Radius (m)");
    expect(panel("constraints")).toContain("Success min");
    expect(panel("noise")).toContain("LiDAR range");
    expect(panel("policies")).toContain("Let candidates replan");
    expect(panel("hardware")).toContain("Device");
    expect(panel("traffic")).toContain("No moving traffic declared");
  });
});

describe("the footer", () => {
  it("keeps filing and checking in reach whichever tab is open", () => {
    const html = render();
    expect(html).toContain("File it");
    expect(html).toContain("Check with the server");
  });

  it("will not file a deployment with no id and no mission", () => {
    /* `complete` wants an id, a start, a goal and a map. A fresh
       template has none of them, so both buttons are inert — an
       enabled button that silently does nothing reads as a broken
       form. */
    const html = render();
    const buttons = html.match(/<button[^>]*>(File it|Check with the server)<\/button>/g) ?? [];
    expect(buttons).toHaveLength(2);
    for (const button of buttons) expect(button).toContain("disabled");
  });
});

describe("refusals from the server", () => {
  it("counts them on the tab that has to show them", () => {
    const html = render({
      fieldErrors: [
        { path: "robot.radius", message: "Input should be greater than 0" },
        { path: "robot.max_linear_velocity", message: "Input should be greater than 0" },
        { path: "environment", message: "two obstacles share one clock key" },
      ],
    });
    expect(html).toMatch(/id="deployment-form-tab-robot"[\s\S]{0,300}?badge err/);
    expect(html).toContain("2 refused by the server");
    expect(html).toContain("1 refused by the server");
  });

  it("prints an address no tab claims instead of counting it into one", () => {
    /* Guessing a home for it would file the refusal under a heading
       that does not own it, which is the same as hiding it — and
       filing stays blocked meanwhile. */
    const html = render({
      fieldErrors: [{ path: "available_observations", message: "not a known observation" }],
    });
    expect(html).toContain("available_observations: not a known observation");
    expect(html).toContain("1 refused");
  });

  it("says nothing about counts when the document is clean", () => {
    /* The word itself appears in the note about re-filing an id, so
       what is checked is the count — a badge with no refusal behind it
       is a form telling the author something is wrong when nothing
       is. */
    const html = render();
    expect(html).not.toContain("refused by the server");
    expect(html).not.toMatch(/\d+ refused</);
  });
});

describe("while something is in flight", () => {
  it("disables the controls rather than letting the document move under a check", () => {
    /* The answer coming back is about the document that was sent. An
       author who keeps typing turns it into an answer about one that no
       longer exists. */
    const html = render({ busy: true });
    const selects = html.match(/<select[^>]*>/g) ?? [];
    expect(selects.length).toBeGreaterThan(2);
    for (const control of selects) expect(control).toContain("disabled");
  });
});
