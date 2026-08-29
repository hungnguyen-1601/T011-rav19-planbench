/** What the imported-algorithms tab is allowed to offer.
 *
 * The repository has no jsdom, so the decisions live in `lib/plugins.ts`
 * rather than inside the component and are tested here. That is not a
 * workaround: "may this be picked?" is a rule about the platform, and a
 * rule that could only be checked by rendering a table would be a rule
 * nobody could check.
 */

import { describe, expect, it } from "vitest";

import {
  type PluginBundleSummary,
  blockedReason,
  bundleStates,
  isSelectable,
  stackIdFor,
} from "@/lib/plugins";

function bundle(overrides: Partial<PluginBundleSummary> = {}): PluginBundleSummary {
  return {
    id: "b1",
    name: "VFH+",
    version: "1",
    description: "",
    plugin_id: "org.vinai.vfh-plus",
    plugin_version: "0.1.0",
    revision: 1,
    role: "local",
    requirements: ["lidar_2d"],
    robot_profile_id: "p1",
    original_filename: "vfh.zip",
    file_size: 2048,
    checksum: "abc",
    status: "active",
    validation_status: "loaded",
    validation_message: "",
    owned: true,
    created_at: "2026-08-24T00:00:00Z",
    updated_at: "2026-08-24T00:00:00Z",
    ...overrides,
  };
}

describe("what may be offered as a candidate", () => {
  it("takes a bundle that is enabled and has actually been run", () => {
    expect(isSelectable(bundle())).toBe(true);
    expect(blockedReason(bundle())).toBeNull();
  });

  it("refuses one nobody has run, however readable its archive was", () => {
    /* `structural` is neither a pass nor a failure — it is "not run".
       Offering it would put a candidate into a comparison on the
       strength of its zip being well formed. */
    const unverified = bundle({ validation_status: "structural" });
    expect(isSelectable(unverified)).toBe(false);
    expect(blockedReason(unverified)).toBe("unverified");
  });

  it("refuses one that ran and misbehaved", () => {
    const failed = bundle({ validation_status: "failed" });
    expect(isSelectable(failed)).toBe(false);
    expect(blockedReason(failed)).toBe("failed");
  });

  it("refuses a disabled one even when it passed", () => {
    const disabled = bundle({ status: "disabled" });
    expect(isSelectable(disabled)).toBe(false);
    expect(blockedReason(disabled)).toBe("disabled");
  });

  it("reports the decision before the file when both are wrong", () => {
    /* Ordered by what the reader can act on: a disabled bundle is one
       click from running, a failed one needs its code changed. */
    expect(blockedReason(bundle({ status: "disabled", validation_status: "failed" }))).toBe(
      "disabled",
    );
  });

  it("never returns a reason for something that is fine", () => {
    /* So a caller cannot render an empty warning box. */
    expect(blockedReason(bundle({ validation_status: "loaded" }))).toBeNull();
  });
});

describe("the name a report will quote", () => {
  it("pairs the global planner with the plugin's own id", () => {
    /* The plugin id, not the display name: it is what the candidate
       hashes on, so a prettier alias here would be a second identity
       nobody could resolve back to this row. */
    expect(stackIdFor(bundle())).toBe("astar+org.vinai.vfh-plus");
  });

  it("is unaffected by renaming the bundle", () => {
    expect(stackIdFor(bundle({ name: "Something else", version: "9" }))).toBe(
      "astar+org.vinai.vfh-plus",
    );
  });
});

describe("what to call a bundle's state", () => {
  it("names the published revision as the one a benchmark gets", () => {
    const one = bundle({ id: "b1", revision: 1 });
    expect(bundleStates([one], ["b1"]).get("b1")).toBe("published");
  });

  it("tells a superseded revision apart from one nobody published", () => {
    // Same plugin, two uploads, the newer one published. The older is
    // not merely unpublished — somebody replaced it, and a reviewer
    // reading the list has nothing to do about that.
    const old = bundle({ id: "b1", revision: 1 });
    const fresh = bundle({ id: "b2", revision: 2 });
    const states = bundleStates([old, fresh], ["b2"]);
    expect(states.get("b1")).toBe("superseded");
    expect(states.get("b2")).toBe("published");

    // Nothing published at all is the other case, and it *is* somebody's
    // job: it is waiting for a reviewer.
    expect(bundleStates([old, fresh], []).get("b1")).toBe("awaiting");
  });

  it("puts a reviewer's decision ahead of the conformance verdict", () => {
    // A held or disabled bundle that also happens to have failed its
    // suite is reported as held: that is the fact somebody can act on,
    // and the failure is what the detail panel is for.
    expect(
      bundleStates([bundle({ status: "held", validation_status: "failed" })], []).get("b1"),
    ).toBe("held");
    expect(
      bundleStates([bundle({ status: "disabled", validation_status: "loaded" })], ["b1"]).get("b1"),
    ).toBe("disabled");
  });

  it("does not call an unrun bundle broken", () => {
    // "structural" means nobody has run it, which is not the same as
    // having run it and found it misbehaving. Reporting both as failed
    // would send somebody to fix code that may be fine.
    expect(bundleStates([bundle({ validation_status: "structural" })], []).get("b1")).toBe(
      "checking",
    );
    expect(bundleStates([bundle({ validation_status: "failed" })], []).get("b1")).toBe("broken");
  });

  it("reads an empty published set as governance being off", () => {
    // No publications means the deployment never turned publishing on,
    // and every runnable bundle is then simply waiting rather than
    // hidden.
    const states = bundleStates([bundle({ id: "b1" }), bundle({ id: "b2" })], []);
    expect([...states.values()]).toEqual(["awaiting", "awaiting"]);
  });
});
