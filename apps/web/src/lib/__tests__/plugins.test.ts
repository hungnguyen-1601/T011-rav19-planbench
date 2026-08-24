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
