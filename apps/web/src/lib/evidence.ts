/** What the evidence panel shows, decided apart from how it looks.
 *
 * The rules here are the ones worth being wrong about: whether a
 * decomposition may be drawn, whether "nothing was found" means the
 * detectors ran and found nothing or that they never ran, and which
 * lattice verdicts are findings rather than shrugs. A component that
 * decided those inline would be a component whose reasoning can only be
 * checked by looking at pixels — and this repository has no DOM in its
 * tests, so it could not be checked at all.
 */

import type {
  ExplanationView,
  PacketLatticeFinding,
  PacketObservation,
  PacketWaterfall,
} from "@/lib/decisions";

/** How a lattice verdict should read.
 *
 * **Three of the four verdicts are refusals and they are not alike.**
 * `rules_out_component_specific_attribution` is a *result* — both stacks
 * show the pattern, so whatever separates them is not that component —
 * while `insufficient_contrast` is the lattice declining to speak.
 * Painting them the same grey files a finding as an absence, which is
 * the failure this whole layer exists to prevent, committed in CSS.
 */
export const VERDICT_TONE: Record<string, string> = {
  supports_component_specific_attribution: "ok",
  rules_out_component_specific_attribution: "warn",
  interaction_not_isolated: "muted-badge",
  insufficient_contrast: "muted-badge",
};

export function verdictTone(verdict: string): string {
  return VERDICT_TONE[verdict] ?? "muted-badge";
}

/** Why there is no decomposition on screen.
 *
 * `"none"` means one is being drawn. The other two are different facts
 * and must not share a sentence: a run that ranked nobody had nothing to
 * decompose, while a plan that forbids the comparison is the panel
 * matrix refusing to draw one that exists.
 */
export type NoWaterfallReason = "none" | "run-ranked-nobody" | "plan-forbids";

export function waterfallState(
  waterfall: PacketWaterfall | null,
  planAllows: boolean,
): NoWaterfallReason {
  if (!planAllows) return "plan-forbids";
  if (waterfall === null) return "run-ranked-nobody";
  return "none";
}

/** What the sightings section is actually saying.
 *
 * `"no-traces"` and `"clean"` look identical — both render an empty
 * table — and mean opposite things. One is "the detectors never ran";
 * the other is "they ran and this run is clean", which is a finding.
 */
export type SightingsState = "some" | "clean" | "no-traces";

export function sightingsState(observations: PacketObservation[]): SightingsState {
  if (observations.length === 0) return "no-traces";
  return observations.some((item) => item.episodes_seen > 0) ? "some" : "clean";
}

export function firedSightings(observations: PacketObservation[]): PacketObservation[] {
  return observations.filter((item) => item.episodes_seen > 0);
}

/** The widest bar, for scaling. Never zero, so a run whose bars are all
 * zero renders flat rather than dividing by nothing. */
export function widestContribution(waterfall: PacketWaterfall): number {
  return Math.max(...waterfall.bars.map((bar) => Math.abs(bar.contribution)), 1e-9);
}

/** Everything the panel would report as missing, in one list.
 *
 * Omissions and skipped episodes are separate facts in the payload —
 * "this part could not be built" versus "this episode's trace was
 * unreadable" — and they are labelled separately here rather than
 * concatenated into an undifferentiated pile.
 */
export function missingNotes(view: ExplanationView): { note: string; kind: "omission" | "skipped" }[] {
  return [
    ...view.omissions.map((note) => ({ note, kind: "omission" as const })),
    ...view.skipped_episodes.map((note) => ({ note, kind: "skipped" as const })),
  ];
}

/** Lattice findings, strongest statement first.
 *
 * A reader scanning seven rows should meet the ones that say something
 * before the ones that decline to. Ordering by verdict rather than by
 * detection type is a presentation choice and is made here, where it can
 * be argued with, rather than by whatever order the packet happened to
 * carry.
 */
const VERDICT_RANK: Record<string, number> = {
  supports_component_specific_attribution: 0,
  rules_out_component_specific_attribution: 1,
  interaction_not_isolated: 2,
  insufficient_contrast: 3,
};

export function orderedFindings(findings: PacketLatticeFinding[]): PacketLatticeFinding[] {
  return [...findings].sort((left, right) => {
    const byVerdict = (VERDICT_RANK[left.verdict] ?? 9) - (VERDICT_RANK[right.verdict] ?? 9);
    return byVerdict !== 0 ? byVerdict : left.detection_type.localeCompare(right.detection_type);
  });
}
