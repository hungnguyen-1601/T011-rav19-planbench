/** Which field names a candidate in the column head.
 *
 * **The heading has to be the field that differs, and which field that
 * is changes per run.** A comparison swaps exactly one component and
 * holds the rest fixed, so on any given run one of these two is
 * identical down both columns and the other is the whole point:
 *
 * | `experiment_scope`           | differs                    | identical                  |
 * |------------------------------|----------------------------|----------------------------|
 * | `local_controller_selection` | `local_controller_config`  | `stack_label`              |
 * | `global_planner_selection`   | `stack_label`              | `local_controller_config`  |
 *
 * Both mistakes have the same shape: two column heads reading the same
 * words. The page shipped with `stack_label` as the heading, which is
 * wrong for the first row — `astar+dwa` twice. An earlier draft of the
 * fix hard-coded the config instead, which is wrong for the second —
 * `dwa_coarse` twice — and that is the commoner run, ten of the sixteen
 * stored when this was written.
 *
 * **Read from the data, not from `experiment_scope`.** The two agree on
 * every stored run, and they should: the scope names the component being
 * swapped. But the scope is a declaration and the candidates are what is
 * on the screen, so if they ever disagree the heading must follow what
 * the reader can see. It also means a run with a scope nobody has taught
 * this page about still gets a sensible heading.
 */

import type { RunCandidate } from "@/lib/decisions";

export type HeadingField = "stack" | "config";

/** The field to put in the column head.
 *
 * Falls back to `"stack"` in the two cases where neither answer is
 * forced: a single candidate has nothing to differ from, and a run where
 * *both* fields differ is not a controlled swap at all — naming the
 * stack is then at least the coarser, more recognisable label, and the
 * sub-line carries the config underneath either way.
 */
export function headingField(candidates: readonly RunCandidate[]): HeadingField {
  const stacks = new Set(candidates.map((candidate) => candidate.stack_label));
  if (stacks.size > 1) return "stack";
  const configs = new Set(candidates.map((candidate) => candidate.local_controller_config));
  return configs.size > 1 ? "config" : "stack";
}

/** Heading and sub-line for one candidate, already ordered.
 *
 * The sub-line carries whichever field the heading did not, so no
 * identifier is lost whichever way the choice went, and then the
 * observation class. `filter(Boolean)` rather than string concatenation:
 * `local_observation_class` is `string | null | undefined`, and joining
 * blind yields `astar+dwa · null`, or — since JSX swallows `null` —
 * `astar+dwa ·` with the separator dangling.
 */
export function candidateNames(
  candidate: RunCandidate,
  heading: HeadingField,
): { heading: string; secondary: string } {
  const isStack = heading === "stack";
  return {
    heading: isStack ? candidate.stack_label : candidate.local_controller_config,
    secondary: [
      isStack ? candidate.local_controller_config : candidate.stack_label,
      candidate.local_observation_class,
    ]
      .filter(Boolean)
      .join(" · "),
  };
}
