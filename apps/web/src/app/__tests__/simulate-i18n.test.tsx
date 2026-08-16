import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..");
const SIMULATE_PAGE = readFileSync(join(APP, "simulate", "page.tsx"), "utf8");
const SCENE25D_COMPONENT = readFileSync(
  join(APP, "..", "components", "Scene25D.tsx"),
  "utf8",
);
const EN = JSON.parse(
  readFileSync(join(APP, "..", "lib", "i18n", "locales", "en.json"), "utf8"),
) as Record<string, string>;
const VI = JSON.parse(
  readFileSync(join(APP, "..", "lib", "i18n", "locales", "vi.json"), "utf8"),
) as Record<string, string>;

describe("/simulate page localization compliance", () => {
  it("uses i18n keys for Stop, Reset, Speed, pose, and dt buttons and labels", () => {
    expect(SIMULATE_PAGE).toContain('{t("simulate.stop")}');
    expect(SIMULATE_PAGE).toContain('{t("simulate.reset")}');
    expect(SIMULATE_PAGE).toContain('{t("simulate.speed")}:');
    expect(SIMULATE_PAGE).toContain('{t("simulate.pose")}');
    expect(SIMULATE_PAGE).toContain('{t("simulate.dt")}');
  });

  it("does not contain raw hard-coded user-facing strings for controls", () => {
    expect(SIMULATE_PAGE).not.toMatch(/<button[^>]*>\s*Stop\s*<\/button>/i);
    expect(SIMULATE_PAGE).not.toMatch(/<button[^>]*>\s*Reset\s*<\/button>/i);
    expect(SIMULATE_PAGE).not.toMatch(/<label[^>]*>\s*Speed:/i);
  });

  it("Scene25D component uses i18n keys for controls", () => {
    expect(SCENE25D_COMPONENT).toContain('{t("scene25d.rotate")}');
    expect(SCENE25D_COMPONENT).toContain('{t("scene25d.tilt")}');
    expect(SCENE25D_COMPONENT).toContain('t("scene25d.topDown")');
    expect(SCENE25D_COMPONENT).toContain('{t("scene25d.wallHeight")}');
  });
});

describe("i18n locale key parity and validity", () => {
  it("en.json and vi.json have 100% key parity", () => {
    const enKeys = Object.keys(EN).sort();
    const viKeys = Object.keys(VI).sort();
    expect(viKeys).toEqual(enKeys);
  });

  it("no empty values exist in either dictionary", () => {
    for (const [key, value] of Object.entries(EN)) {
      expect(value.trim(), `Empty value in en.json for key "${key}"`).not.toBe("");
    }
    for (const [key, value] of Object.entries(VI)) {
      expect(value.trim(), `Empty value in vi.json for key "${key}"`).not.toBe("");
    }
  });

  it("all placeholders match between English and Vietnamese", () => {
    const extractPlaceholders = (str: string) =>
      (str.match(/\{(\w+)\}/g) ?? []).sort();
    for (const key of Object.keys(EN)) {
      const enVars = extractPlaceholders(EN[key]);
      const viVars = extractPlaceholders(VI[key]);
      expect(viVars, `Placeholder mismatch in key "${key}"`).toEqual(enVars);
    }
  });

  it("contains all simulate.* and scene25d.* required keys in both languages", () => {
    const requiredKeys = [
      "simulate.title",
      "simulate.subtitle",
      "simulate.run",
      "simulate.play",
      "simulate.pause",
      "simulate.stop",
      "simulate.reset",
      "simulate.restart",
      "simulate.speed",
      "simulate.pose",
      "simulate.dt",
      "simulate.tooltip.dt",
      "simulate.tooltip.t",
      "simulate.tooltip.pose",
      "simulate.tooltip.v",
      "simulate.tooltip.omega",
      "scene25d.rotate",
      "scene25d.tilt",
      "scene25d.topDown",
      "scene25d.wallHeight",
    ];

    for (const key of requiredKeys) {
      expect(EN[key], `en.json missing key ${key}`).toBeTruthy();
      expect(VI[key], `vi.json missing key ${key}`).toBeTruthy();
    }
  });
});
