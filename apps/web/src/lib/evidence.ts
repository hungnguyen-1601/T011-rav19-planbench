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
  PlannedRoute,
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

/** The one sentence a finding amounts to, in the reader's own words.
 *
 * **The verdict badge was a term of art and the sentence under it was a
 * method note.** "supports attributing to a component" over "the pattern
 * follows global_planner across every pair that changes only that
 * component" is two ways of describing the experiment, and neither of
 * them says the thing a reader came for — which is whether the route
 * planner is what makes the robot stall. That sentence exists; it was
 * simply never written down, because the panel was built to be
 * defensible rather than to be read.
 *
 * So both survive, in that order: the plain claim first, the method
 * behind it still there for anyone checking the reasoning. What is *not*
 * done is dropping the method note — a reader who disagrees with a claim
 * needs to see how it was reached, and "trust us" is what this whole
 * layer exists to avoid.
 *
 * The subject is a component code (`global_planner`), and it is worded
 * here rather than printed: a sentence naming `global_planner` in the
 * middle of Vietnamese prose is a sentence half-translated. */
export interface LatticePlain {
  key: string;
  /** i18n key for the component, or `null` for the two verdicts that
   *  name no component because they could not isolate one. */
  componentKey: string | null;
}

export function latticePlain(finding: PacketLatticeFinding): LatticePlain {
  const known =
    finding.subject === "global_planner" || finding.subject === "local_controller";
  return {
    key: `evidence.plain.${finding.verdict}`,
    componentKey: known ? `evidence.component.${finding.subject}` : null,
  };
}

/** How a lattice finding's reason should be worded.
 *
 * **The badge was translated and the sentence under it was not.** A
 * Vietnamese page carried `ủng hộ quy kết cho một component` over four
 * lines of English — the platform's `reason` string, rendered verbatim
 * because that is what it was: prose composed in Python, with no code
 * beside it a client could word for itself.
 *
 * The fix is the one `hostWarningView` already made for the measurement
 * caveat, and it is worth stating why that shape and not a translation
 * table keyed on the sentence. What must survive intact is the *claim*,
 * and the claim here is carried by `verdict` and `subject`, both of
 * which are codes. Given those two, this client can say the same thing
 * in either language. Given only the sentence, it can only pattern-match
 * on prose the platform is free to reword.
 *
 * **`interaction_not_isolated` keeps the platform's own sentence**, and
 * that is not an oversight. Its reason names the components the pattern
 * moved with, and that list exists nowhere else in the payload — it is
 * assembled into the prose and never sent as data. Wording it here would
 * mean either dropping the components, which is most of the finding, or
 * parsing them back out of a sentence, which is worse than printing it.
 * An unknown verdict falls through the same way, so a build that meets a
 * verdict added after it still shows the platform's words rather than a
 * blank.
 */
export type LatticeReason =
  | { translated: true; key: string; subject: string | null }
  | { translated: false; text: string };

const WORDABLE = new Set([
  "supports_component_specific_attribution",
  "rules_out_component_specific_attribution",
  "insufficient_contrast",
]);

export function latticeReason(finding: PacketLatticeFinding): LatticeReason {
  if (!WORDABLE.has(finding.verdict)) return { translated: false, text: finding.reason };
  return {
    translated: true,
    key: `evidence.lattice.reason.${finding.verdict}`,
    subject: finding.subject ?? null,
  };
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


/** The plan the robot was following at a given step.
 *
 * **The newest one that has taken over, and only that one.** A replan
 * replaces the route; drawing every attempt at once would show a fan of
 * paths the robot never had, and the reader could not tell which one
 * the trajectory was supposed to be following at the moment they are
 * looking at.
 *
 * `null` before any plan exists and — deliberately — for an attempt
 * that found nothing: at that step the robot had no route, and keeping
 * the previous one on screen would draw a plan that had already been
 * abandoned.
 */
export function routeAt(routes: PlannedRoute[], step: number): PlannedRoute | null {
  let current: PlannedRoute | null = null;
  for (const route of routes) {
    if (route.from_index > step) break;
    current = route;
  }
  if (!current || current.points.length === 0) return null;
  return current;
}

/** The planned route's colour, one per replan.
 *
 * **The point is that it changes, not which colour it lands on.** The
 * dashed line is replaced outright at every replan, and with one colour
 * for all of them a reader watching the canvas cannot tell "the plan
 * bent" from "the plan was thrown away and a new one drawn" — the two
 * look identical mid-scrub, and only one of them is a replan.
 *
 * Four, cycling. Enough that consecutive plans never share a colour,
 * few enough to stay distinguishable; a run with five replans reuses the
 * first, which is fine, because the question this answers is "did it
 * just change" and not "which attempt is this".
 *
 * Chosen to sit clear of what the canvas already spends colour on — blue
 * and purple for the two candidates' paths, amber for moving obstacles,
 * red for HĐ-5 events. Kept translucent and dashed either way: this is
 * an intention, not a measurement.
 */
export const PLANNED_ROUTE_COLOURS = [
  "rgba(15, 23, 42, 0.55)",
  "rgba(15, 118, 110, 0.7)",
  "rgba(146, 64, 14, 0.7)",
  "rgba(77, 124, 15, 0.75)",
] as const;

export function plannedRouteColour(attempt: number): string {
  // Attempts are 1-based in the sidecar. A missing or nonsensical value
  // takes the first colour rather than crashing a canvas over a
  // decoration.
  const index = Number.isFinite(attempt) ? Math.max(0, Math.round(attempt) - 1) : 0;
  return PLANNED_ROUTE_COLOURS[index % PLANNED_ROUTE_COLOURS.length];
}
