/** Which parts of the explanation surface a run may show.
 *
 * A port of `planbench_explanation.panel`, kept deliberately thin: the
 * *decision* lives on the platform, this reads it. The five outcomes and
 * their flags are duplicated here only because the page has to render
 * before any explanation endpoint answers, and a page that guesses
 * would guess differently from the server.
 *
 * The rule the duplication protects: three of the five outcomes have no
 * paired comparison, so there is no ΔU to decompose, nobody to compare
 * episodes between, and no "why A won" to claim. Drawing any of those
 * would answer a question the run never asked.
 */

import type { DecisionRun } from "./decisions";
import { noCardReason } from "./decisions";

export type RunOutcome =
  | "clear"
  | "near_equivalent"
  | "no_survivors"
  | "gate_only"
  | "interrupted";

export interface PanelPlan {
  outcome: RunOutcome;
  showWaterfall: boolean;
  showClaims: boolean;
  showExemplars: boolean;
  /** The replay viewer itself. True everywhere: a candidate that failed
   *  a gate has traces, and they are what somebody asking "why did it
   *  fail" opens. Gating the viewer on `showExemplars` hid the evidence
   *  for the three outcomes whose only content is evidence. */
  showTraceEvidence: boolean;
  showGateTable: boolean;
  headlineKey: string;
  /** Caveats that belong beside the numbers, not in a footnote. */
  caveatKeys: string[];
}

/** Keyed by outcome **and** by whether a paired comparison exists.
 *
 * `interrupted` is two situations. A run that stopped after ranking has
 * a ΔU and a caveat about how few episodes back it; one that stopped
 * before ranking has no comparison at all. Keying on the outcome alone
 * put a waterfall on the second — each half of the logic right, the
 * pair wrong.
 */
const PLANS: Record<string, PanelPlan> = {
  "clear|true": {
    outcome: "clear",
    showWaterfall: true,
    showClaims: true,
    showExemplars: true,
    showTraceEvidence: true,
    showGateTable: true,
    headlineKey: "explain.headline.clear",
    caveatKeys: ["explain.caveat.scope"],
  },
  "near_equivalent|true": {
    outcome: "near_equivalent",
    showWaterfall: true,
    showClaims: true,
    showExemplars: true,
    showTraceEvidence: true,
    showGateTable: true,
    headlineKey: "explain.headline.nearEquivalent",
    caveatKeys: [
      "explain.caveat.insideTheNoise",
      "explain.caveat.tieBreak",
      "explain.caveat.scope",
    ],
  },
  "no_survivors|false": {
    outcome: "no_survivors",
    showWaterfall: false,
    showClaims: false,
    showExemplars: false,
    showTraceEvidence: true,
    showGateTable: true,
    headlineKey: "explain.headline.noSurvivors",
    caveatKeys: ["explain.caveat.registerABetterCandidate"],
  },
  "gate_only|false": {
    outcome: "gate_only",
    showWaterfall: false,
    showClaims: false,
    showExemplars: false,
    showTraceEvidence: true,
    showGateTable: true,
    headlineKey: "explain.headline.gateOnly",
    caveatKeys: ["explain.caveat.deploymentCannotRank"],
  },
  "interrupted|true": {
    outcome: "interrupted",
    showWaterfall: true,
    showClaims: true,
    showExemplars: true,
    showTraceEvidence: true,
    showGateTable: true,
    headlineKey: "explain.headline.interrupted",
    caveatKeys: ["explain.caveat.fewerEpisodes", "explain.caveat.scope"],
  },
  "interrupted|false": {
    outcome: "interrupted",
    showWaterfall: false,
    showClaims: false,
    showExemplars: false,
    showTraceEvidence: true,
    showGateTable: true,
    headlineKey: "explain.headline.interruptedBeforeRanking",
    caveatKeys: ["explain.caveat.fewerEpisodes", "explain.caveat.noComparisonYet"],
  },
};

/** Which of the five this run is.
 *
 * `interrupted` leads among the no-card cases: a run that stopped early
 * may *also* have had nobody survive, and "we did not finish" is the
 * fact that makes the second one uninterpretable.
 */
export function runOutcome(run: DecisionRun): RunOutcome {
  const reason = noCardReason(run);
  if (reason === "interrupted") return "interrupted";
  if (reason === "gate_only") return "gate_only";
  // One survivor and none share this outcome, and deliberately so: the
  // split `noCardReason` makes is about what the reader should *do*, and
  // this taxonomy is about whether a comparison exists at all. Neither
  // case has one. What differs between them is the sentence and the next
  // action, and both of those are said by `Outcome`, not here.
  if (reason === "no_survivors" || reason === "single_survivor") return "no_survivors";
  if (run.report?.sample?.interrupted) return "interrupted";
  const status = (run.card as { status?: string } | null)?.status;
  return status === "NEAR_EQUIVALENT" ? "near_equivalent" : "clear";
}

/** Whether this run ever produced a paired comparison. */
export function hasComparison(run: DecisionRun): boolean {
  return Boolean(run.ranked);
}

export function panelPlan(run: DecisionRun): PanelPlan {
  const outcome = runOutcome(run);
  const comparison = hasComparison(run) && outcome !== "no_survivors" && outcome !== "gate_only";
  return PLANS[`${outcome}|${comparison}`];
}
