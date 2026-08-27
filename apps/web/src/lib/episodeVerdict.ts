/** One episode: who won, what happened to each side, what differed.
 *
 * Everything here is a pure function of what the server sent. The rules
 * that decide a verdict, a diagnosis or a contrast all live on the
 * platform — a second copy in TypeScript would disagree with the first
 * the day either was fixed, and the disagreement would surface as a
 * panel claiming something the report does not.
 *
 * What this module *does* own is the reading: which episode counts as
 * chosen, whether an answer still belongs to what is on screen, and how
 * a finding is worded so a diagnosis is never mistaken for an account
 * of the difference.
 */

/** How an episode came to be selected.
 *
 * The replay opens on the first episode so the canvases are not blank.
 * That is a default, not a choice — nobody pointed at it. Anything that
 * answers "the episode the reader is looking at" has to distinguish the
 * two, or it will explain an episode the reader never asked about.
 */
export type SelectionOrigin = "default" | "user";

export type VerdictBasis =
  | "episode_decision_utility"
  | "outcome_only"
  | "not_comparable"
  | "undecidable";

export type ContrastStrength = "context" | "support";

export interface MeasuredValue {
  value: number;
  unit: string;
  denominator: number | null;
}

export interface EpisodeVerdict {
  episode_context_id: string;
  candidate_a: string;
  candidate_b: string;
  basis: VerdictBasis;
  winner: string | null;
  loser: string | null;
  tie: boolean;
  utility_a: MeasuredValue | null;
  utility_b: MeasuredValue | null;
  delta_utility: MeasuredValue | null;
  undecided_reason: string;
  caveat: string;
}

export interface EpisodeDetection {
  type: string;
  candidate_id: string;
  episode_context_id: string;
  window: {
    start_m: number;
    end_m: number;
    start_s: number;
    end_s: number;
  } | null;
  measurements: Record<string, number>;
}

export interface EpisodeDiagnosis {
  candidate_id: string;
  outcome: {
    candidate_id: string;
    success: boolean;
    failure_reason: string | null;
    collision_count: number;
    min_clearance: number | null;
    travel_time_s: number | null;
    p99_latency_ms: number | null;
    replan_count: number;
    decision_utility: number | null;
  } | null;
  detections: EpisodeDetection[];
  planning_attempts: number | null;
  no_path_attempts: number | null;
  first_no_path_tick: number | null;
}

export interface EpisodeContrast {
  kind: string;
  against_candidate_id: string;
  subject: string | null;
  proposition_type: string | null;
  detail: string;
  evidence_refs: string[];
  measurements: Record<string, number>;
}

export interface RuledOut {
  kind: string;
  reason: string;
  detail: string;
}

export interface EpisodeFloorProposal {
  hypothesis_id: string;
  hypothesis_statement: string;
  proposition_type: string;
  proposed_subject: string;
}

export interface EpisodeVerdictView {
  verdict: EpisodeVerdict;
  diagnoses: EpisodeDiagnosis[];
  contrasts: EpisodeContrast[];
  ruled_out: RuledOut[];
  floor: {
    abstained: boolean;
    proposals: EpisodeFloorProposal[];
    bearings: Record<string, string>;
  };
  omissions: string[];
  candidate_a: string;
  candidate_b: string;
  episode_context_id: string;
}

/** Which kinds of difference carry a mechanism, and which are context.
 *
 * Mirrors the platform's own table. Duplicated here for **wording**
 * only — the panel says "context" or "relevant" — and never to decide
 * whether a finding may be offered: that decision is the server's, and
 * the client renders what it was sent.
 */
const SUPPORTING_KINDS = new Set(["detection_only_on_loser", "detection_worse_on_loser"]);

export function contrastStrength(kind: string): ContrastStrength {
  return SUPPORTING_KINDS.has(kind) ? "support" : "context";
}

/** The episode this panel is about, or `null` when nobody chose one.
 *
 * `null` is a real answer and the panel renders it as one. Falling back
 * to whatever the replay happens to be showing would explain an episode
 * the reader never pointed at — and, worse, would do it with the same
 * confidence as an episode they did.
 */
export function selectedEpisode(state: {
  episodeId: string;
  origin: SelectionOrigin;
}): string | null {
  if (state.origin !== "user") return null;
  return state.episodeId || null;
}

/** Whether an answer still describes what is on screen.
 *
 * Compared at **render** time rather than at request time. A reader who
 * clicks through three episodes while the first is still in flight must
 * not be shown the first one's answer under the third one's heading,
 * and the request that started earliest is exactly the one that lands
 * last often enough to matter.
 */
export function answersCurrentSelection(
  view: EpisodeVerdictView | null,
  selection: { episode: string | null; candidateA: string; candidateB: string },
): boolean {
  if (!view || !selection.episode) return false;
  if (view.episode_context_id !== selection.episode) return false;
  return view.candidate_a === selection.candidateA && view.candidate_b === selection.candidateB;
}

/** Whether the verdict names a side. */
export function hasDirection(verdict: EpisodeVerdict): boolean {
  return Boolean(verdict.winner && verdict.loser);
}

/** The i18n key for the headline, by basis.
 *
 * Four bases and four sentences: `not_comparable` says a record is
 * missing, and saying "these two were equal" there would be a claim
 * about a comparison nobody made.
 */
export function verdictHeadlineKey(verdict: EpisodeVerdict): string {
  if (verdict.basis === "not_comparable") return "episodeVerdict.headline.notComparable";
  if (verdict.basis === "undecidable") return "episodeVerdict.headline.undecidable";
  if (verdict.tie) return "episodeVerdict.headline.tie";
  if (verdict.basis === "outcome_only") return "episodeVerdict.headline.outcomeOnly";
  return "episodeVerdict.headline.utility";
}

/** Diagnoses in the verdict's own order: winner first when there is one. */
export function orderedDiagnoses(view: EpisodeVerdictView): EpisodeDiagnosis[] {
  const winner = view.verdict.winner;
  if (!winner) return view.diagnoses;
  return [...view.diagnoses].sort((left, right) => {
    if (left.candidate_id === winner) return -1;
    if (right.candidate_id === winner) return 1;
    return 0;
  });
}

/** Where in the replay a detection happened, in seconds, or `null`.
 *
 * `null` for a detection with no window: seeking to a moment nothing
 * recorded would move the playhead somewhere arbitrary and tell the
 * reader it was the place.
 */
export function detectionSeconds(detection: EpisodeDetection): number | null {
  return detection.window ? detection.window.start_s : null;
}

/** Which side of the pair a candidate is, for a seek. */
export function sideOf(
  view: EpisodeVerdictView,
  candidateId: string,
): "a" | "b" | null {
  if (candidateId === view.candidate_a) return "a";
  if (candidateId === view.candidate_b) return "b";
  return null;
}

/** Whether the model half of the panel may be offered at all.
 *
 * Three conditions, all required. The mode is the platform's; the role
 * is the reader's; the episode is the question. An answer needs all
 * three and the button needs the same three — a control that appears
 * and then refuses is worse than one that was never there.
 */
export function mayAskTheModel(state: {
  mode: string;
  isAdmin: boolean;
  episode: string | null;
}): boolean {
  if (!state.episode) return false;
  if (state.mode !== "internal_preview" && state.mode !== "production") return false;
  return state.mode === "production" || state.isAdmin;
}
