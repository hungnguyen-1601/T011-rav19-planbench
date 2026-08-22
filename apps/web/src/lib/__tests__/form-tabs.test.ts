/** Where each server refusal is shown, and the one case that cannot be
 * worked out from the path.
 *
 * The reason this file exists rather than a `startsWith` at the call
 * site: every traffic rule the contract states is a model validator on
 * `EnvironmentSpec`, so all of them arrive addressed to a bare
 * `environment` — indistinguishable by path from a noise amplitude or
 * the closing speed, which live under the same prefix and have controls
 * on other tabs. Guessing there would put a refusal behind a tab nobody
 * opens, which is the same as hiding it.
 */

import { describe, expect, it } from "vitest";

import { FORM_TABS, firstTabWithError, routeError, tallyErrors } from "@/lib/formTabs";

const at = (path: string) => ({ path, message: "refused" });

describe("routing a refusal to its tab", () => {
  it("sends each field to the tab holding its control", () => {
    expect(routeError("robot.radius")).toBe("robot");
    expect(routeError("constraints.goal_tolerance_rad")).toBe("constraints");
    expect(routeError("clearance_preference")).toBe("constraints");
    expect(routeError("hardware.ram_budget_breakdown.perception_stack_mb")).toBe("hardware");
    expect(routeError("missions.0.probability")).toBe("mission");
  });

  it("splits the environment block by which control owns the field", () => {
    expect(routeError("environment.sensor_noise.lidar_range_sigma_m")).toBe("noise");
    expect(routeError("environment.v_obstacle_max")).toBe("policies");
    expect(routeError("environment.dynamic_obstacles.2.radius")).toBe("traffic");
  });

  it("sends a bare `environment` to Traffic, where those rules live", () => {
    /* Unique names, a seed head start, a full period, a declared
       closing speed, a shared clock: all five are model validators, so
       pydantic addresses them here with nothing after. Pinned on the
       server side in tests/api/test_api_profile_validation.py — if the
       backend ever addresses them more precisely, that test and this
       one move together. */
    expect(routeError("environment")).toBe("traffic");
  });

  it("keeps the identity fields off the tabs entirely", () => {
    /* They sit above the strip, because they are what the deployment
       *is* rather than one aspect of it. */
    for (const path of ["id", "claim_level", "deployment_role"]) {
      expect(routeError(path)).toBe("identity");
    }
  });

  it("calls an address it does not know unmapped rather than nearly-right", () => {
    expect(routeError("available_observations")).toBe("unmapped");
    expect(routeError("something_new_in_the_schema")).toBe("unmapped");
  });

  it("prefers the more specific prefix, whatever the order of the table", () => {
    // `environment.sensor_noise` and `environment` both match; the
    // longer one is the one with a control.
    expect(routeError("environment.sensor_noise")).toBe("noise");
  });

  it("does not mistake a longer name for a nested field", () => {
    /* `recovery` owns `recovery.max_forgets`; it must not swallow a
       field that merely starts with the same letters. */
    expect(routeError("recovery_budget")).toBe("unmapped");
    expect(routeError("recovery.max_forgets")).toBe("policies");
  });
});

describe("counting them for the badges", () => {
  it("adds up per tab and keeps the unmapped ones whole", () => {
    const tally = tallyErrors([
      at("robot.radius"),
      at("environment"),
      at("environment.dynamic_obstacles.0.radius"),
      at("id"),
      at("what_is_this"),
    ]);
    expect(tally.byTab.robot).toBe(1);
    expect(tally.byTab.traffic).toBe(2);
    expect(tally.identity).toBe(1);
    expect(tally.unmapped).toEqual([at("what_is_this")]);
    expect(tally.total).toBe(5);
  });

  it("never drops one on the floor", () => {
    /* The sum has to match, or a refusal blocks filing while nothing on
       screen accounts for it. */
    const errors = [
      at("environment"),
      at("environment.sensor_noise.wheel_slip_fraction"),
      at("claim_level"),
      at("mystery"),
      at("hardware.total_ram_mb"),
    ];
    const tally = tallyErrors(errors);
    const counted =
      FORM_TABS.reduce((sum, tab) => sum + tally.byTab[tab], 0) +
      tally.identity +
      tally.unmapped.length;
    expect(counted).toBe(errors.length);
  });

  it("gives every tab a zero rather than leaving it absent", () => {
    const tally = tallyErrors([]);
    for (const tab of FORM_TABS) expect(tally.byTab[tab]).toBe(0);
  });
});

describe("where to jump after a refused check", () => {
  it("goes to the first tab with something to show, in strip order", () => {
    expect(firstTabWithError([at("hardware.total_ram_mb"), at("robot.radius")])).toBe("robot");
  });

  it("stays put when the refusals are already on screen", () => {
    /* Identity sits above the tabs and unmapped ones are in the footer:
       moving the author to an unrelated tab to show them nothing there
       is worse than not moving at all. */
    expect(firstTabWithError([at("id")])).toBeNull();
    expect(firstTabWithError([at("mystery")])).toBeNull();
    expect(firstTabWithError([])).toBeNull();
  });
});
