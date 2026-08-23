/** What the sample line says, and which single notice sits under it.
 *
 * **Three figures that read `30`, `30`, `30` are not three findings.**
 * The page opened on a row of 26px cards — measured, requested, N_min —
 * which on an ordinary run are the same number printed three times at
 * the largest type size on screen. A figure earns a card when it is
 * abnormal; when it is fine it earns a clause.
 *
 * Everything here is a decision, and every decision is in this file
 * rather than in the component, because the repo has no jsdom: a rule
 * that lives inside JSX is a rule no test can reach (see
 * `docs/KNOWN_LIMITATIONS.md`). The component's remaining job is to look
 * up two i18n keys and render.
 *
 * Nothing here calls `t()`. These functions choose *which* key; the
 * wording is the dictionary's business, and a module that returned
 * English would have to be edited to add a language.
 */

import type { DecisionRun, RunSample } from "@/lib/decisions";

export const MEETS_N_MIN = "decisions.sample.line.meetsNMin";
export const BELOW_N_MIN = "decisions.sample.line.belowNMin";

export interface SampleLineState {
  /** Which of the two N_min clauses to render. */
  nMinKey: typeof MEETS_N_MIN | typeof BELOW_N_MIN;
  /** `n` is only read by the below-N_min wording, which prints both. */
  params: { n: number; min: number };
  /** Whether the line may claim the run covered what was asked for. */
  ranFullRequest: boolean;
  /** Rounded percent, or `null` for "do not add a coverage clause". */
  coveragePercent: number | null;
}

/** At most one notice, chosen by severity. `null` renders nothing. */
export type SampleNotice =
  /** Below N_min. Voids every number on the page under it. */
  | "critical"
  /** Below N_min *and* cut short — one notice carrying both, never two. */
  | "belowNMinInterrupted"
  /** Cut short but still at or above N_min. Bounded, not disqualifying. */
  | "warn"
  | null;

/**
 * **The line must not claim a state the run is not in.**
 *
 * An earlier draft printed `meets N_min (30)` unconditionally and left
 * the correction to the notice underneath. That does not work: a notice
 * cannot repair a false statement made inside the line it annotates,
 * because the reader who skims reads the line and not the notice. So the
 * clause is chosen, not fixed.
 *
 * The below-N_min wording prints **both** numbers — `18/30` — because
 * `N_min required: 30` on its own is the half of the fact that does not
 * say how short the run fell.
 */
export function sampleLine(sample: RunSample, covered?: number): SampleLineState {
  const short = sample.n_episodes < sample.n_min_required;
  return {
    nMinKey: short ? BELOW_N_MIN : MEETS_N_MIN,
    params: { n: sample.n_episodes, min: sample.n_min_required },
    // All three conditions, and `!== undefined` rather than a truthiness
    // check: a run stored before `n_episodes_requested` existed must not
    // get to claim it ran the full request just because the field is
    // absent. Nor may an interrupted run, however many episodes landed.
    ranFullRequest:
      sample.n_episodes_requested !== undefined &&
      sample.n_episodes >= sample.n_episodes_requested &&
      !sample.interrupted,
    // Full coverage is not worth a clause; missing coverage is not the
    // same as complete coverage and stays out of the line entirely.
    //
    // And it is dropped when it would restate the clause beside it.
    // A real run — 245 measured, 300 requested, N_min 300 — would
    // otherwise print `below N_min (245/300) · coverage 82%`: the same
    // shortfall twice, once as a fraction and once as its percentage,
    // on the line whose entire purpose is to stop saying one number
    // three times. The two clauses only collide when the deployment
    // asked for exactly N_min; where they differ (requested 400 against
    // an N_min of 30) they are separate facts and both stay.
    coveragePercent:
      covered === undefined ||
      covered >= 1 ||
      (short && sample.n_episodes_requested === sample.n_min_required)
        ? null
        : Math.round(covered * 100),
  };
}

/** Coverage read straight off the run, for callers holding one. */
export function sampleLineFor(run: DecisionRun): SampleLineState | null {
  const sample = run.report?.sample;
  if (!sample) return null;
  return sampleLine(sample, coverageOf(run));
}

function coverageOf(run: DecisionRun): number | undefined {
  const requested = run.report?.sample?.n_episodes_requested;
  const measured = run.report?.sample?.n_episodes;
  if (!requested || measured === undefined) return undefined;
  return measured / requested;
}

/**
 * **One notice, never a stack.**
 *
 * A run that is both short and interrupted used to draw two boxes, and
 * two boxes of the same shape read as two problems of the same weight.
 * They are not: below N_min voids the numbers, interrupted explains how
 * the run got that way. So the combined case gets its own key that says
 * both things in one box, and the interrupted notice never appears
 * beneath the critical one.
 *
 * Coverage is deliberately absent from this ladder. Partial coverage is
 * a clause on the line (see `sampleLine`), not a box — it qualifies the
 * sample's size, which the line is already describing.
 */
export function sampleNotice(sample: RunSample): SampleNotice {
  const short = sample.n_episodes < sample.n_min_required;
  if (short) return sample.interrupted ? "belowNMinInterrupted" : "critical";
  return sample.interrupted ? "warn" : null;
}

/** The dictionary key and the CSS variant for a notice, or `null`. */
export function noticeKey(notice: SampleNotice): { key: string; variant: string } | null {
  switch (notice) {
    case "critical":
      return { key: "decisions.sample.belowNMin", variant: "notice--critical" };
    case "belowNMinInterrupted":
      return {
        key: "decisions.sample.belowNMinInterrupted",
        variant: "notice--critical",
      };
    case "warn":
      return { key: "decisions.sample.interrupted", variant: "notice--warn" };
    default:
      return null;
  }
}
