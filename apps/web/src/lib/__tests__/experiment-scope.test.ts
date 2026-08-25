/** The scope a pair of candidates supports, and the run that never ran.
 *
 * The page sent no scope at all, so every comparison took the client
 * default `global_planner_selection` — which requires an identical local
 * layer. Anybody swapping the controller (`astar+dwa` against
 * `astar+vfh_plus`) was therefore refused with `ExperimentScopeViolation`
 * for a scope they had never chosen and could not change. The first
 * three cases below are the three answers that were unreachable; the
 * rest are the ways a chosen scope can contradict the data.
 */

import { describe, expect, it } from "vitest";

import {
  CONFLICT_KEY,
  EXPERIMENT_SCOPES,
  SCOPE_LABEL_KEY,
  SCOPE_NOTE_KEY,
  inferExperimentScope,
  readScopeViolation,
  scopeConflict,
  violationKey,
} from "@/lib/experimentScope";
import type { CandidateChoice } from "@/lib/decisions";
import en from "../i18n/locales/en.json";
import vi from "../i18n/locales/vi.json";

const pick = (stack: string, local_config: string): CandidateChoice => ({ stack, local_config });

/* One controlled swap each way, plus the two undetermined shapes. */
const swapGlobal = [pick("astar+dwa", "dwa_coarse"), pick("rrtstar+dwa", "dwa_coarse")];
const swapLocal = [pick("astar+dwa", "dwa_coarse"), pick("astar+vfh_plus", "vfh_default")];
const swapBoth = [pick("astar+dwa", "dwa_coarse"), pick("rrtstar+vfh_plus", "vfh_default")];
const swapNothing = [pick("astar+dwa", "dwa_coarse"), pick("astar+dwa", "dwa_coarse")];

describe("deriving the scope", () => {
  it("names the global planner when only the global half differs", () => {
    expect(inferExperimentScope(swapGlobal)).toBe("global_planner_selection");
  });

  it("names the local controller when only the local half differs", () => {
    /* The comparison that could not be run from the UI at all. */
    expect(inferExperimentScope(swapLocal)).toBe("local_controller_selection");
  });

  it("counts the configuration as part of the local layer", () => {
    /* Same controller, different parameters. The server fingerprints
       component, version *and* parameters, so this is two local layers
       and a global-planner conclusion over it would be refused —
       matching on the controller name alone would derive the scope that
       fails. */
    expect(
      inferExperimentScope([pick("astar+dwa", "dwa_coarse"), pick("astar+dwa", "dwa_balanced")]),
    ).toBe("local_controller_selection");
    expect(
      inferExperimentScope([pick("astar+dwa", "dwa_coarse"), pick("rrtstar+dwa", "dwa_balanced")]),
    ).toBe("full_stack_selection");
  });

  it("falls back to the full stack when both halves differ", () => {
    /* Not a controlled swap: no single layer is held fixed, so no
       single layer can be concluded about. */
    expect(inferExperimentScope(swapBoth)).toBe("full_stack_selection");
  });

  it("falls back to the full stack when the two candidates are identical", () => {
    /* Nothing varies, so nothing forces an answer. The only scope that
       constrains nothing is the only one that cannot be wrong here —
       the mistake is real but it is not a scope mistake, and
       `scopeConflict` is what reports it. */
    expect(inferExperimentScope(swapNothing)).toBe("full_stack_selection");
    expect(inferExperimentScope([pick("astar+dwa", "dwa_coarse")])).toBe("full_stack_selection");
    expect(inferExperimentScope([])).toBe("full_stack_selection");
  });

  it("treats a stack id with no plus as having no local half", () => {
    /* A monolithic candidate, or free text typed while the registry
       list was unavailable. It has no layer to hold fixed, and the
       server only admits it to `full_stack_selection`. */
    expect(inferExperimentScope([pick("e2e_policy", ""), pick("astar+dwa", "dwa_coarse")])).toBe(
      "full_stack_selection",
    );
  });

  it("derives a scope the server would accept, for every controlled swap", () => {
    /* The property the page depends on: what is derived is never
       something `validate_experiment_scope` refuses. */
    for (const pair of [swapGlobal, swapLocal, swapBoth]) {
      expect(scopeConflict(inferExperimentScope(pair), pair)).toBeNull();
    }
  });
});

describe("a scope that contradicts the candidates", () => {
  it("says so when a global-planner conclusion has a varying local layer", () => {
    expect(scopeConflict("global_planner_selection", swapLocal)).toBe("local_differs");
    expect(scopeConflict("global_planner_selection", swapBoth)).toBe("local_differs");
  });

  it("says so when a local-controller conclusion has a varying planner", () => {
    expect(scopeConflict("local_controller_selection", swapGlobal)).toBe("global_differs");
    expect(scopeConflict("local_controller_selection", swapBoth)).toBe("global_differs");
  });

  it("reports two identical candidates whatever the scope", () => {
    /* One configuration cannot be its own rival. It is not a violation
       of any particular scope, so every scope has to report it. */
    for (const scope of EXPERIMENT_SCOPES) {
      expect(scopeConflict(scope, swapNothing)).toBe("identical");
    }
  });

  it("stays quiet on the full stack, which constrains nothing", () => {
    for (const pair of [swapGlobal, swapLocal, swapBoth]) {
      expect(scopeConflict("full_stack_selection", pair)).toBeNull();
    }
  });

  it("does not call a single candidate a duplicate of itself", () => {
    expect(scopeConflict("full_stack_selection", [pick("astar+dwa", "dwa_coarse")])).toBeNull();
    expect(scopeConflict("full_stack_selection", [])).toBeNull();
  });
});

describe("reading the server's refusal", () => {
  /* Verbatim from a refused launch — the string the screen used to
     show as-is. */
  const layerRefusal =
    "scope global_planner_selection requires an identical local layer (component, " +
    "version and parameters) in every candidate, found 2 variants across " +
    "['e1251e2b', 'e4d2c0aa']";

  it("turns a layer violation into the layer that has to be held fixed", () => {
    expect(readScopeViolation(layerRefusal)).toEqual({ kind: "layer", fixedLayer: "local" });
    expect(
      readScopeViolation(
        "scope local_controller_selection requires an identical global layer (component, " +
          "version and parameters) in every candidate, found 2 variants across ['a', 'b']",
      ),
    ).toEqual({ kind: "layer", fixedLayer: "global" });
  });

  it("recognises the monolithic and duplicate refusals too", () => {
    expect(
      readScopeViolation(
        "scope global_planner_selection holds the local layer fixed, but monolithic " +
          "candidate(s) ['x'] have no layers; run these under full_stack_selection",
      ),
    ).toEqual({ kind: "layer", fixedLayer: "local" });
    expect(
      readScopeViolation(
        "candidate abc appears twice (positions 0 and 1); the same configuration cannot " +
          "be its own rival",
      ),
    ).toEqual({ kind: "duplicate" });
  });

  it("returns null for anything else, so it is shown verbatim", () => {
    /* A mistranslated error is worse than an untranslated one. */
    expect(readScopeViolation("a comparison needs at least one candidate")).toBeNull();
    expect(readScopeViolation("Failed to fetch")).toBeNull();
    expect(readScopeViolation("")).toBeNull();
  });
});

describe("the strings this module names", () => {
  it("has every key it points at, in both locales", () => {
    const keys = [
      ...Object.values(SCOPE_LABEL_KEY),
      ...Object.values(SCOPE_NOTE_KEY),
      ...Object.values(CONFLICT_KEY),
      violationKey({ kind: "duplicate" }),
      violationKey({ kind: "layer", fixedLayer: "local" }),
      violationKey({ kind: "layer", fixedLayer: "global" }),
    ];
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });

  it("offers exactly the three scopes the contract defines", () => {
    expect([...EXPERIMENT_SCOPES]).toEqual([
      "global_planner_selection",
      "local_controller_selection",
      "full_stack_selection",
    ]);
  });
});
