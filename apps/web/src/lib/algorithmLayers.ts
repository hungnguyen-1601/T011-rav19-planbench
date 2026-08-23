/** The planners and controllers the system has, read off the stacks.
 *
 * **Derived, because there is no separate list to read.** The registry
 * holds *stacks* — `astar+dwa`, `rrtstar+dwa_predictive` — and each one
 * states which global planner and which local controller it runs. There
 * is no endpoint that enumerates the two layers on their own, and
 * inventing one in the browser by splitting `astar+dwa` on the `+` would
 * be reading a display convention as a fact; the registry's own comment
 * says the id is exactly that. So the layers come from the fields the
 * stacks declare, which is the same source a report quotes.
 *
 * **What a layer can honestly say about itself.** Not much on its own: a
 * global planner has no observation class or benchmarkability of its
 * own, only the ones the stacks running it happen to have. Where every
 * stack agrees, that is a fact about the layer; where they disagree, the
 * answer is the disagreement and this says so rather than picking one.
 * A row claiming `lidar_only` for a controller that appears with two
 * different observation classes would be a claim no stack makes.
 */

import type { AlgorithmInfo, ObservationClass } from "@/lib/benchmarkTypes";

export interface AlgorithmLayer {
  /** `astar`, `dwa`, `ppo` — as the registry states it, never parsed. */
  id: string;
  /** Stack ids that run this layer, in registry order. */
  stacks: string[];
  /** The observation class every stack running this layer uses, or
   *  `null` when they do not agree. Null is an answer: it says the layer
   *  is used two ways, which a single value would hide. */
  observation: ObservationClass | null;
  /** True when at least one stack running this layer can be benchmarked.
   *  A layer whose only stacks are references is not a contender. */
  benchmarkable: boolean;
  /** Only meaningful for a global planner: it samples randomly, so
   *  results have to be read across seeds. */
  stochastic: boolean;
}

/** One value if every entry agrees, `null` if they do not. */
function agreed<T>(values: readonly T[]): T | null {
  if (values.length === 0) return null;
  const first = values[0];
  return values.every((value) => value === first) ? first : null;
}

function layersOf(
  stacks: readonly AlgorithmInfo[],
  idOf: (stack: AlgorithmInfo) => string,
  observationOf: (stack: AlgorithmInfo) => ObservationClass,
): AlgorithmLayer[] {
  const grouped = new Map<string, AlgorithmInfo[]>();
  for (const stack of stacks) {
    const id = idOf(stack);
    // A stack that names no layer is a stack this cannot say anything
    // about. Grouping it under "" would invent a planner called nothing.
    if (!id) continue;
    grouped.set(id, [...(grouped.get(id) ?? []), stack]);
  }

  return [...grouped.entries()]
    .map(([id, using]) => ({
      id,
      stacks: using.map((stack) => stack.id),
      observation: agreed(using.map(observationOf)),
      benchmarkable: using.some((stack) => stack.benchmarkable),
      stochastic: using.some((stack) => stack.stochastic_global_planner),
    }))
    .sort((left, right) => left.id.localeCompare(right.id));
}

/** Every global planner in the registry, once each. */
export function globalPlanners(stacks: readonly AlgorithmInfo[]): AlgorithmLayer[] {
  return layersOf(
    stacks,
    (stack) => stack.global_planner,
    (stack) => stack.global_observation_class,
  );
}

/** Every local controller in the registry, once each.
 *
 * `stochastic` is left as whatever the stacks report and is not rendered
 * for this half: the flag describes the *global* planner's sampling, and
 * a controller inheriting it from the stack it shares would be labelled
 * random for something it does not do.
 */
export function localControllers(stacks: readonly AlgorithmInfo[]): AlgorithmLayer[] {
  return layersOf(
    stacks,
    (stack) => stack.local_controller,
    (stack) => stack.local_observation_class,
  );
}
