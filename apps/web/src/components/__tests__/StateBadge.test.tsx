import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const COMPONENT = join(__dirname, "..", "StateBadge.tsx");
const CONTENT = readFileSync(COMPONENT, "utf8");

const EN = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "lib", "i18n", "locales", "en.json"), "utf8"),
) as Record<string, string>;

const VI = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "lib", "i18n", "locales", "vi.json"), "utf8"),
) as Record<string, string>;

const REQUIRED_STATES = [
  "draft",
  "running",
  "success",
  "collision",
  "stuck",
  "timeout",
  "accepted",
  "rejected",
  "approved",
  "pending_approval",
  "pending_review",
  "completed",
  "failed",
  "cancelled",
  "queued",
  "paused",
  "idle",
];

describe("StateBadge component standardization", () => {
  it("supports all 17 required protocol states with explicit configurations", () => {
    for (const state of REQUIRED_STATES) {
      expect(CONTENT).toContain(`${state}:`);
    }
  });

  it("includes visual symbols/icons for multi-sensory feedback (not color alone)", () => {
    expect(CONTENT).toContain("badge-icon");
    expect(CONTENT).toContain("aria-hidden");
    // Verify visual icons are defined in config
    expect(CONTENT).toMatch(/icon:\s*"[✓💥🛑⏱⏳⏸📝⚡ℹ✖]"/);
  });

  it("provides technical tooltips and accessible aria-labels", () => {
    expect(CONTENT).toContain("title={tooltip}");
    expect(CONTENT).toContain("aria-label={ariaLabel}");
  });

  it("defines localized labels and tooltips in both en.json and vi.json", () => {
    for (const state of REQUIRED_STATES) {
      expect(EN[`status.label.${state}`], `en missing status.label.${state}`).toBeTruthy();
      expect(VI[`status.label.${state}`], `vi missing status.label.${state}`).toBeTruthy();
      expect(EN[`status.tooltip.${state}`], `en missing status.tooltip.${state}`).toBeTruthy();
      expect(VI[`status.tooltip.${state}`], `vi missing status.tooltip.${state}`).toBeTruthy();
    }
  });
});
