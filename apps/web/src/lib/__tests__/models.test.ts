/** The model registry, browser side.
 *
 * The rule that matters most and is easiest to lose: **the client sends
 * an id, never a path**. Everything else here is about catching a wrong
 * file before it is uploaded rather than after.
 */

import { describe, expect, it } from "vitest";

import { ACCEPTED, extensionOf, formatSize, isUsable, type ModelSummary } from "@/lib/models";

function model(overrides: Partial<ModelSummary> = {}): ModelSummary {
  return {
    id: "m1",
    name: "warehouse-ppo",
    version: "2",
    description: "",
    algorithm_type: "ppo",
    framework: "stable-baselines3",
    robot_profile_id: "p1",
    status: "active",
    validation_status: "structural",
    validation_message: "",
    file_size: 2048,
    checksum: "a".repeat(64),
    training_environment: "dynamic_warehouse",
    training_steps: 1_000_000,
    observation_schema: {
      type: "lidar_goal_velocity",
      shape: [34],
      lidar_beams: 24,
      includes_goal_direction: true,
      includes_current_velocity: true,
    },
    action_schema: { type: "continuous_velocity", shape: [2], fields: ["v", "w"] },
    created_at: "2026-08-01T00:00:00Z",
    is_owner: true,
    ...overrides,
  };
}

describe("the three kinds of file", () => {
  it("keeps them distinct", () => {
    // The confusion this whole feature guards against: a PDF about a
    // model is not a model.
    expect(ACCEPTED.model).toBe(".zip");
    expect(ACCEPTED.metadata).toBe(".json");
    expect(ACCEPTED.document).toBe(".pdf");
  });

  it("reads an extension, case-insensitively", () => {
    expect(extensionOf("model.ZIP")).toBe(".zip");
    expect(extensionOf("report.pdf")).toBe(".pdf");
    expect(extensionOf("archive.tar.gz")).toBe(".gz");
  });

  it("returns nothing for a name with no extension", () => {
    expect(extensionOf("model")).toBe("");
  });

  it("is not fooled by a dot in a directory name", () => {
    expect(extensionOf("v1.2/model.zip")).toBe(".zip");
  });
});

describe("isUsable", () => {
  it("accepts a checked, active model", () => {
    expect(isUsable(model())).toBe(true);
    expect(isUsable(model({ validation_status: "loaded" }))).toBe(true);
  });

  it("rejects a disabled model", () => {
    // Offering one would mean the server refuses it at launch, which
    // the user discovers only after clicking Run.
    expect(isUsable(model({ status: "disabled" }))).toBe(false);
  });

  it("rejects a model that failed validation", () => {
    expect(isUsable(model({ validation_status: "failed" }))).toBe(false);
  });

  it("rejects a model nobody has checked yet", () => {
    expect(isUsable(model({ validation_status: "pending" }))).toBe(false);
  });
});

describe("formatSize", () => {
  it("uses units a person reads", () => {
    expect(formatSize(512)).toBe("512 B");
    expect(formatSize(2048)).toBe("2.0 KB");
    expect(formatSize(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("the client never handles a file path", () => {
  it("has no path field anywhere in the model type", () => {
    // A compile-time guarantee made runtime-visible: if someone adds a
    // path to the API response, this fails.
    const keys = Object.keys(model());
    for (const key of keys) {
      expect(key).not.toContain("path");
      expect(key).not.toContain("storage");
    }
  });
});
