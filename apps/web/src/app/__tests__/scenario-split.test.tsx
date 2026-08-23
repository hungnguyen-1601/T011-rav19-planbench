/** The dev/held-out surface (P05), after P6 took half of it away.
 *
 * The split *labelling* survives: `/library` and `/scenarios` still show
 * which set each scenario belongs to, and that is a fact about the
 * scenario, not about who ran it. `SplitBadge` still has two live
 * callers.
 *
 * The split *analysis* did not. The generalization gap, the held-out
 * usage counter and the pre-run held-out warning lived on `/leaderboard`
 * and `/benchmarks`, and all three are claims across scenarios — "this
 * stack generalises from dev to held-out". HĐ-1.4 scopes a
 * recommendation to one deployment, so they retired with the flow that
 * made them rather than being rehomed into one that does not. Their
 * assertions are deleted here deliberately, and this paragraph is the
 * record of that.
 *
 * Source-level, matching the other page tests: these pages sit behind an
 * effect and a fetch, so a first paint shows only a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");

const BADGE = read("components", "SplitBadge.tsx");
const LIBRARY = read("app", "library", "page.tsx");
const SCENARIOS = read("app", "scenarios", "page.tsx");

describe("the split badge distinguishes all three states", () => {
  it("styles held out as a warning, not as a neutral label", () => {
    expect(BADGE).toContain("holdout: \"badge warn\"");
  });

  it("labels unassigned rather than rendering it as empty or as dev", () => {
    expect(BADGE).toContain("unassigned:");
    expect(BADGE).toContain("protocol.unassignedHint");
  });
});

describe("the library no longer carries the split", () => {
  /* The split governs which scenarios a generalization report may quote
     — a rule about the benchmark protocol, not a description of the
     world. It stays on the scenario editor, where somebody choosing
     what to run against needs it, and left the library, which is read
     to find out what a scenario does. */

  it("shows no split column", () => {
    expect(LIBRARY).not.toContain("SplitBadge");
    expect(LIBRARY).not.toContain("entry.split");
    expect(LIBRARY).not.toContain("protocol.splitHint");
  });
});

describe("the editor labels a scenario's split too", () => {
  it("shows it where scenarios are built, not only where they are listed", () => {
    /* Which set a scenario belongs to changes what using it costs. The
       page that creates them is the last place that should keep it
       quiet. */
    expect(SCENARIOS).toContain("SplitBadge");
  });
});

describe("both locales carry the new strings", () => {
  const keys = [
    "protocol.split",
    "protocol.dev",
    "protocol.holdout",
    "protocol.unassigned",
    "protocol.splitHint",
    "protocol.unassignedHint",
    "protocol.version",
    "protocol.holdoutWarning",
    "protocol.holdoutBenchmarkNotice",
    "protocol.unassignedBenchmarkNotice",
    "generalization.title",
    "generalization.hint",
    "generalization.gap",
    "generalization.noGap",
    "generalization.holdoutUsage",
    "generalization.holdoutUsageHint",
  ];

  it.each(keys)("%s is translated in English and Vietnamese", (key) => {
    expect((en as Record<string, string>)[key]).toBeTruthy();
    expect((vi as Record<string, string>)[key]).toBeTruthy();
  });

  it("keeps the scenario placeholder in the held-out warning", () => {
    expect(en["protocol.holdoutWarning"]).toContain("{scenario}");
    expect(vi["protocol.holdoutWarning"]).toContain("{scenario}");
  });

  it("does not leave the Vietnamese explanation as the English one", () => {
    expect(vi["protocol.splitHint"]).not.toEqual(en["protocol.splitHint"]);
    expect(vi["generalization.hint"]).not.toEqual(en["generalization.hint"]);
  });
});
