/** Which field names a candidate, and the way both answers can be wrong.
 *
 * Two column heads reading the same words is the bug. It has two forms —
 * `astar+dwa` twice on a global-planner comparison, `dwa_coarse` twice
 * on a local-controller one — and a fix that hard-codes either field
 * produces the other. Both are here.
 */

import { describe, expect, it } from "vitest";

import { candidateNames, headingField } from "@/lib/candidateHeading";
import type { RunCandidate } from "@/lib/decisions";

const candidate = (over: Partial<RunCandidate> = {}): RunCandidate =>
  ({
    candidate_id: "c1",
    stack_label: "astar+dwa",
    local_controller_config: "dwa_coarse",
    local_observation_class: "lidar_only",
    n_distinct_episodes: 30,
    success_rate: 1,
    cleared_gates: true,
    ...over,
  }) as RunCandidate;

/** The two comparisons the platform actually runs. */
const localControllerRun = [
  candidate({ candidate_id: "a", local_controller_config: "dwa_coarse" }),
  candidate({ candidate_id: "b", local_controller_config: "dwa_balanced" }),
];
const globalPlannerRun = [
  candidate({ candidate_id: "a", stack_label: "astar+dwa" }),
  candidate({ candidate_id: "b", stack_label: "rrtstar+dwa" }),
];

describe("choosing the heading", () => {
  it("names the config when the stacks are identical", () => {
    expect(headingField(localControllerRun)).toBe("config");
  });

  it("names the stack when the configs are identical", () => {
    /* Ten of the sixteen runs stored when this was written. A fix that
       hard-coded the config would print `dwa_coarse` down both columns —
       the same bug, inverted. */
    expect(headingField(globalPlannerRun)).toBe("stack");
  });

  it("never picks a field that is the same on both sides", () => {
    for (const run of [localControllerRun, globalPlannerRun]) {
      const field = headingField(run);
      const shown = run.map((c) => candidateNames(c, field).heading);
      expect(new Set(shown).size, `heading ${field}`).toBe(run.length);
    }
  });

  it("falls back to the stack when nothing forces a choice", () => {
    expect(headingField([candidate()])).toBe("stack");
    expect(headingField([])).toBe("stack");
    /* Both fields differ: not a controlled swap, so there is no "the"
       varied component to name. */
    expect(
      headingField([
        candidate({ stack_label: "astar+dwa", local_controller_config: "dwa_coarse" }),
        candidate({ stack_label: "rrtstar+dwa", local_controller_config: "dwa_balanced" }),
      ]),
    ).toBe("stack");
  });
});

describe("the sub-line", () => {
  it("carries whichever field the heading did not", () => {
    expect(candidateNames(candidate(), "stack")).toEqual({
      heading: "astar+dwa",
      secondary: "dwa_coarse · lidar_only",
    });
    expect(candidateNames(candidate(), "config")).toEqual({
      heading: "dwa_coarse",
      secondary: "astar+dwa · lidar_only",
    });
  });

  it("loses no identifier whichever way the choice went", () => {
    for (const field of ["stack", "config"] as const) {
      const { heading, secondary } = candidateNames(candidate(), field);
      expect(`${heading} ${secondary}`).toContain("astar+dwa");
      expect(`${heading} ${secondary}`).toContain("dwa_coarse");
    }
  });

  it("drops the separator when the observation class is missing", () => {
    /* `local_observation_class` is `string | null | undefined`. Joining
       blind gives `astar+dwa · null`, or — since JSX swallows `null` —
       `astar+dwa ·` with the separator left dangling. */
    for (const missing of [null, undefined, ""]) {
      const { secondary } = candidateNames(
        candidate({ local_observation_class: missing as string | null }),
        "stack",
      );
      expect(secondary).toBe("dwa_coarse");
      expect(secondary).not.toContain("·");
      expect(secondary).not.toContain("null");
    }
  });
});
