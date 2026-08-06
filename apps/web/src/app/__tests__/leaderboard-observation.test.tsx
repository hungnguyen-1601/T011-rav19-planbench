/** The leaderboard's half of information parity (P02).
 *
 * The backend already refuses to rank across observation classes; what
 * has to be defended here is that the UI does not quietly undo that —
 * by defaulting the toggle to "mixed", by dropping the warning, or by
 * printing a blank cell where an unknown class should be named.
 *
 * Source-level rather than rendered, matching the other page tests:
 * this page's whole body sits behind an effect and a fetch, so a first
 * paint would only show a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const APP = join(process.cwd(), "src", "app");
const LEADERBOARD = readFileSync(join(APP, "leaderboard", "page.tsx"), "utf8");
const ALGORITHMS = readFileSync(join(APP, "algorithms", "page.tsx"), "utf8");

describe("the leaderboard states what each stack was shown", () => {
  it("renders the controller's observation class per row", () => {
    expect(LEADERBOARD).toContain("entry.local_observation_class");
  });

  it("names the class instead of leaving a blank cell when it is unknown", () => {
    expect(LEADERBOARD).toContain("leaderboard.observationUnknown");
  });

  it("labels the group with the class its rows share", () => {
    expect(LEADERBOARD).toContain("group.local_observation_class");
  });
});

describe("mixing observation classes is opt-in and never silent", () => {
  it("separates classes by default", () => {
    expect(LEADERBOARD).toContain("useState(true)");
    expect(LEADERBOARD).toContain("group_by_observation_class");
  });

  it("shows the warning the backend flags on a mixed group", () => {
    expect(LEADERBOARD).toContain("group.cross_observation_class_warning");
    expect(LEADERBOARD).toContain("leaderboard.mixedObservationWarning");
  });

  it("warns as soon as the user turns separation off", () => {
    expect(LEADERBOARD).toContain("!groupByObservation ?");
  });
});

describe("the algorithms page shows the declaration before a run", () => {
  it("prints both observation classes", () => {
    expect(ALGORITHMS).toContain("algorithm.global_observation_class");
    expect(ALGORITHMS).toContain("algorithm.local_observation_class");
  });
});

describe("both locales carry the new strings", () => {
  const keys = [
    "leaderboard.observation",
    "leaderboard.observationHint",
    "leaderboard.observationUnknown",
    "leaderboard.groupObservation",
    "leaderboard.groupByObservation",
    "leaderboard.mixedObservationWarning",
    "algorithms.observationGlobal",
    "algorithms.observationLocal",
  ];

  it.each(keys)("%s is translated in English and Vietnamese", (key) => {
    expect((en as Record<string, string>)[key]).toBeTruthy();
    expect((vi as Record<string, string>)[key]).toBeTruthy();
  });

  it("does not leave the Vietnamese warning as the English one", () => {
    expect(vi["leaderboard.mixedObservationWarning"]).not.toEqual(
      en["leaderboard.mixedObservationWarning"],
    );
  });
});
