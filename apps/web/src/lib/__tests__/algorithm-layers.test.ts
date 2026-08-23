/** Reading the two layers off the stacks that declare them.
 *
 * The rules worth being wrong about: a layer used two ways has no
 * single observation class, and neither flag on a layer may claim more
 * than the stacks under it say.
 */

import { describe, expect, it } from "vitest";

import { globalPlanners, localControllers } from "@/lib/algorithmLayers";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";

const stack = (over: Partial<AlgorithmInfo>): AlgorithmInfo =>
  ({
    id: "astar+dwa",
    kind: "stack",
    description: "",
    benchmarkable: true,
    config_schema: {},
    global_planner: "astar",
    local_controller: "dwa",
    stochastic_global_planner: false,
    global_observation_class: "full_static_map",
    local_observation_class: "lidar_only",
    requires_global_path: true,
    ...over,
  }) as AlgorithmInfo;

describe("which algorithms exist at each layer", () => {
  it("lists each planner once, however many stacks run it", () => {
    const layers = globalPlanners([
      stack({ id: "astar+dwa" }),
      stack({ id: "astar+ppo", local_controller: "ppo" }),
    ]);
    expect(layers.map((layer) => layer.id)).toEqual(["astar"]);
    expect(layers[0].stacks).toEqual(["astar+dwa", "astar+ppo"]);
  });

  it("reads the layer off the declared field, never out of the id", () => {
    /* The registry's own comment calls the id a display convention.
       Splitting `astar+dwa` on the `+` would read it as a fact. */
    const layers = globalPlanners([stack({ id: "anything-at-all", global_planner: "rrtstar" })]);
    expect(layers.map((layer) => layer.id)).toEqual(["rrtstar"]);
  });

  it("splits the two layers apart", () => {
    const stacks = [
      stack({ id: "astar+dwa" }),
      stack({ id: "rrtstar+dwa_predictive", global_planner: "rrtstar", local_controller: "dwa_predictive" }),
    ];
    expect(globalPlanners(stacks).map((layer) => layer.id)).toEqual(["astar", "rrtstar"]);
    expect(localControllers(stacks).map((layer) => layer.id)).toEqual(["dwa", "dwa_predictive"]);
  });

  it("says an observation class only when every stack agrees", () => {
    const agreeing = localControllers([
      stack({ id: "a+dwa" }),
      stack({ id: "b+dwa", global_planner: "rrtstar" }),
    ]);
    expect(agreeing[0].observation).toBe("lidar_only");
  });

  it("answers null when the stacks disagree, rather than picking one", () => {
    /* Naming one of them would be a claim no stack makes. */
    const mixed = localControllers([
      stack({ id: "a+dwa" }),
      stack({ id: "b+dwa", local_observation_class: "full_static_map" }),
    ]);
    expect(mixed[0].observation).toBeNull();
  });

  it("calls a layer benchmarkable when any stack running it is", () => {
    const layers = localControllers([
      stack({ id: "a+dwa", benchmarkable: false }),
      stack({ id: "b+dwa", benchmarkable: true }),
    ]);
    expect(layers[0].benchmarkable).toBe(true);
  });

  it("calls a layer reference-only when none of its stacks can be benchmarked", () => {
    /* Somebody picking it needs to know it is machinery rather than a
       contender before they read the stacks it appears in. */
    const layers = localControllers([stack({ id: "a+pure_pursuit", local_controller: "pure_pursuit", benchmarkable: false })]);
    expect(layers[0].benchmarkable).toBe(false);
  });

  it("carries the sampling flag from the stacks that report it", () => {
    const layers = globalPlanners([
      stack({ id: "rrtstar+dwa", global_planner: "rrtstar", stochastic_global_planner: true }),
    ]);
    expect(layers[0].stochastic).toBe(true);
  });

  it("invents no layer for a stack that names none", () => {
    /* Grouping it under "" would put a planner called nothing in the
       table. */
    expect(globalPlanners([stack({ global_planner: "" })])).toEqual([]);
  });

  it("sorts by id, so the list does not reshuffle between loads", () => {
    const layers = globalPlanners([
      stack({ id: "r", global_planner: "rrtstar" }),
      stack({ id: "a", global_planner: "astar" }),
    ]);
    expect(layers.map((layer) => layer.id)).toEqual(["astar", "rrtstar"]);
  });

  it("says nothing at all about an empty registry", () => {
    expect(globalPlanners([])).toEqual([]);
    expect(localControllers([])).toEqual([]);
  });
});
