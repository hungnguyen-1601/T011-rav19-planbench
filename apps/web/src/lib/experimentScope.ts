/** Which experiment scope a pair of candidates can actually support.
 *
 * **The scope is a property of the two candidates, so it is read from
 * them rather than asked for.** HĐ-1.4 lets a comparison conclude about
 * one layer only when every other layer is held fixed, and the server
 * enforces exactly that (`validate_experiment_scope`):
 *
 * | scope                        | held fixed everywhere      | conclusion is about |
 * |------------------------------|----------------------------|---------------------|
 * | `global_planner_selection`   | the local layer, parameters included | the global planner |
 * | `local_controller_selection` | the global layer           | the local controller |
 * | `full_stack_selection`       | nothing                    | the whole stack, no single layer |
 *
 * Which of the three a given pair supports is therefore already decided
 * by the moment both candidates are picked; a dropdown asking the reader
 * to declare it again can only be right by accident. The page shipped
 * without one at all and sent nothing, so every run took the client
 * default `global_planner_selection` — and anybody swapping the local
 * controller (`astar+dwa` against `astar+vfh_plus`) got an
 * `ExperimentScopeViolation` for a comparison the platform is precisely
 * built to run.
 *
 * **Read from the data, not from a declaration** — the same rule
 * `candidateHeading.ts` follows for the column heads, and for the same
 * reason: the candidates are what is on the screen. The override stays
 * because the derivation cannot see one case. Two candidates that differ
 * in *both* layers are not a controlled swap, so they derive to
 * `full_stack_selection`; a reader who knows the local difference is
 * immaterial to the question they are asking may still say so, and the
 * server will refuse if they are wrong. The declaration is never the
 * source of truth here — it is a second opinion the server gets to
 * overrule.
 */

import type { CandidateChoice } from "@/lib/decisions";

export const EXPERIMENT_SCOPES = [
  "global_planner_selection",
  "local_controller_selection",
  "full_stack_selection",
] as const;

export type ExperimentScope = (typeof EXPERIMENT_SCOPES)[number];

/** The i18n key naming each scope, and the sentence saying what it
 *  licenses a conclusion about. Kept beside the rule rather than in the
 *  page: the page renders whichever scope it is handed. */
export const SCOPE_LABEL_KEY: Record<ExperimentScope, string> = {
  global_planner_selection: "decisions.scope.globalPlanner",
  local_controller_selection: "decisions.scope.localController",
  full_stack_selection: "decisions.scope.fullStack",
};

export const SCOPE_NOTE_KEY: Record<ExperimentScope, string> = {
  global_planner_selection: "decisions.scope.globalPlannerNote",
  local_controller_selection: "decisions.scope.localControllerNote",
  full_stack_selection: "decisions.scope.fullStackNote",
};

/** The two halves of a stack id.
 *
 * `astar+dwa` is the registry's display convention and every entry
 * today spells it that way. An id with no `+` — a monolithic candidate,
 * or free text typed while the registry list was unavailable — has no
 * local half to hold fixed, which is itself the right answer: it makes
 * every layer key differ and lands the pair on `full_stack_selection`,
 * the only scope the server allows a monolithic candidate into.
 */
function layers(choice: CandidateChoice): { global: string; local: string } {
  const plus = choice.stack.indexOf("+");
  if (plus < 0) return { global: choice.stack, local: "" };
  return { global: choice.stack.slice(0, plus), local: choice.stack.slice(plus + 1) };
}

/** The local layer's identity, **parameters included**.
 *
 * The server fingerprints component, version *and* parameters, so
 * `dwa` under `dwa_coarse` and `dwa` under `dwa_balanced` are two local
 * layers, not one. Comparing only the controller name here would derive
 * `global_planner_selection` for a pair the server then refuses — the
 * exact failure this module exists to prevent, moved one step later.
 */
function localKey(choice: CandidateChoice): string {
  return JSON.stringify([layers(choice).local, choice.local_config]);
}

function distinct(values: readonly string[]): boolean {
  return new Set(values).size > 1;
}

/** The scope this candidate set supports, before anybody overrides it.
 *
 * `full_stack_selection` is the answer in both undetermined cases —
 * every layer differing and no layer differing — because it is the only
 * one of the three that constrains nothing, so it is the only one that
 * cannot be wrong about the data. Two identical candidates are still a
 * mistake; it is just not a *scope* mistake, and `scopeConflict` reports
 * it separately.
 */
export function inferExperimentScope(candidates: readonly CandidateChoice[]): ExperimentScope {
  const globalsDiffer = distinct(candidates.map((choice) => layers(choice).global));
  const localsDiffer = distinct(candidates.map(localKey));
  if (globalsDiffer && !localsDiffer) return "global_planner_selection";
  if (localsDiffer && !globalsDiffer) return "local_controller_selection";
  return "full_stack_selection";
}

/** What the server will refuse, said before the click.
 *
 * Advisory, never a veto: the launch button stays live because the
 * server re-checks every rule and is the one that decides. What this
 * buys is the hours between "start" and the refusal — the sweep is
 * queued, and a reader who learns the pair was invalid after it ran has
 * learned it too late.
 *
 * - `identical` — one configuration cannot be its own rival, whatever
 *   the scope. Nothing varies, so nothing is being compared.
 * - `local_differs` — a global-planner conclusion over candidates whose
 *   local layers differ. The measured difference could come from either
 *   layer, so the sentence the card would print is not supported.
 * - `global_differs` — the mirror case.
 */
export type ScopeConflict = "identical" | "local_differs" | "global_differs";

export const CONFLICT_KEY: Record<ScopeConflict, string> = {
  identical: "decisions.scope.conflict.identical",
  local_differs: "decisions.scope.conflict.localDiffers",
  global_differs: "decisions.scope.conflict.globalDiffers",
};

export function scopeConflict(
  scope: ExperimentScope,
  candidates: readonly CandidateChoice[],
): ScopeConflict | null {
  const globalsDiffer = distinct(candidates.map((choice) => layers(choice).global));
  const localsDiffer = distinct(candidates.map(localKey));
  if (candidates.length > 1 && !globalsDiffer && !localsDiffer) return "identical";
  if (scope === "global_planner_selection" && localsDiffer) return "local_differs";
  if (scope === "local_controller_selection" && globalsDiffer) return "global_differs";
  return null;
}

/** A backend `ExperimentScopeViolation`, read back into something to do.
 *
 * The server's wording is precise and unreadable on a screen: *"scope
 * global_planner_selection requires an identical local layer (component,
 * version and parameters) in every candidate, found 2 variants across
 * ['e1251e…', 'e4d2c…']"*. Two candidate hashes and a sentence about
 * fingerprints, where what the reader needs is which of two moves to
 * make — widen the scope, or pick a pair that holds a layer fixed.
 *
 * Matched on the shape of the message rather than on a code, because
 * there is no code: the API surfaces `ValueError.args[0]`. So this
 * returns `null` for anything it does not recognise and the caller
 * shows the original text — a mistranslated error is worse than an
 * untranslated one.
 */
export type ScopeViolation =
  | { kind: "layer"; fixedLayer: "global" | "local" }
  | { kind: "duplicate" };

const LAYER_VIOLATION = /requires an identical (global|local) layer/;
const MONOLITHIC_VIOLATION = /holds the (global|local) layer fixed/;
const DUPLICATE_VIOLATION = /appears twice|cannot be its own rival/;

export function readScopeViolation(message: string): ScopeViolation | null {
  if (DUPLICATE_VIOLATION.test(message)) return { kind: "duplicate" };
  const layer = LAYER_VIOLATION.exec(message) ?? MONOLITHIC_VIOLATION.exec(message);
  if (!layer) return null;
  return { kind: "layer", fixedLayer: layer[1] as "global" | "local" };
}

/** The i18n key explaining one violation, and what to do about it. */
export function violationKey(violation: ScopeViolation): string {
  if (violation.kind === "duplicate") return "decisions.scope.violation.duplicate";
  return violation.fixedLayer === "local"
    ? "decisions.scope.violation.local"
    : "decisions.scope.violation.global";
}
