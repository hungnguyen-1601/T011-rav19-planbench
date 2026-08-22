/** Which tab of the deployment form a server refusal belongs to.
 *
 * **The path does not say, and that is the whole problem.** Every
 * traffic rule the contract states — unique names, a seed head start, a
 * full period, a declared closing speed, a shared clock — is a model
 * validator on `EnvironmentSpec`, so pydantic addresses all five to
 * `environment` with nothing after it. A tab panel that guessed from
 * the path alone could not tell those from a noise amplitude or a
 * closing speed, which live under the same prefix and have controls of
 * their own on other tabs.
 *
 * So the mapping is written out rather than derived, and the bare
 * `environment` case is a decision with a consequence worth stating: it
 * goes to **Traffic**, because that is where all five of those
 * validators live today, and it is where `TrafficEditor` already
 * renders them. The one that reads oddly is the closing-speed
 * cross-check (`v_obstacle_max` against the fastest declared obstacle)
 * — also a model validator, also addressed to `environment`, so it
 * surfaces under Traffic while its input sits under Policies. That is
 * the shipped behaviour rather than a new choice, and it is pinned on
 * the server side by tests/api/test_api_profile_validation.py: if the
 * backend ever addresses those rules more precisely, this table and
 * that test move together.
 *
 * **Nothing is guessed into a nearby tab.** A path this table does not
 * know is `unmapped`, and the footer shows it verbatim. Inventing a
 * home for it would put a refusal behind a tab nobody has reason to
 * open, which is indistinguishable from hiding it — and a blocked
 * filing with no visible reason is the failure this whole addressing
 * scheme exists to prevent.
 *
 * The message text is never consulted. A refusal is routed by where the
 * server said it belongs, not by what it happens to say.
 */

export const FORM_TABS = [
  "mission",
  "traffic",
  "robot",
  "constraints",
  "noise",
  "policies",
  "hardware",
] as const;

export type FormTab = (typeof FORM_TABS)[number];

/** Where a refusal is shown when it is not on a tab.
 *
 * `identity` is the id and the two claim fields, which sit above the
 * tabs because they are what the deployment *is* rather than one aspect
 * of it — their refusals render beside their own inputs, as they always
 * have. */
export type ErrorHome = FormTab | "identity" | "unmapped";

/** Longest prefix wins, so `environment.sensor_noise.*` beats the bare
 *  `environment` entry below it. Order in this list does not matter;
 *  specificity does. */
const ROUTES: { prefix: string; home: ErrorHome }[] = [
  { prefix: "id", home: "identity" },
  { prefix: "claim_level", home: "identity" },
  { prefix: "deployment_role", home: "identity" },
  { prefix: "missions", home: "mission" },
  { prefix: "robot", home: "robot" },
  { prefix: "constraints", home: "constraints" },
  { prefix: "clearance_preference", home: "constraints" },
  { prefix: "environment.sensor_noise", home: "noise" },
  { prefix: "environment.v_obstacle_max", home: "policies" },
  { prefix: "replanning", home: "policies" },
  { prefix: "recovery", home: "policies" },
  { prefix: "environment.dynamic_obstacles", home: "traffic" },
  // Every traffic rule in the contract lands here — see the note above.
  { prefix: "environment", home: "traffic" },
  { prefix: "hardware", home: "hardware" },
];

/** Whether `path` is `prefix` itself or a field inside it. */
function under(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(`${prefix}.`);
}

export function routeError(path: string): ErrorHome {
  let best: { prefix: string; home: ErrorHome } | null = null;
  for (const route of ROUTES) {
    if (!under(path, route.prefix)) continue;
    if (best === null || route.prefix.length > best.prefix.length) best = route;
  }
  return best?.home ?? "unmapped";
}

export interface ErrorTally {
  /** How many refusals each tab has to show, for its badge. */
  byTab: Record<FormTab, number>;
  identity: number;
  /** Addresses no tab claims. Shown in full at the foot of the form
   *  rather than counted into a tab that did not earn them. */
  unmapped: { path: string; message: string }[];
  total: number;
}

export function tallyErrors(errors: { path: string; message: string }[]): ErrorTally {
  const byTab = Object.fromEntries(FORM_TABS.map((tab) => [tab, 0])) as Record<FormTab, number>;
  let identity = 0;
  const unmapped: { path: string; message: string }[] = [];
  for (const entry of errors) {
    const home = routeError(entry.path);
    if (home === "unmapped") unmapped.push(entry);
    else if (home === "identity") identity += 1;
    else byTab[home] += 1;
  }
  return { byTab, identity, unmapped, total: errors.length };
}

/** The first tab holding a refusal, in the order the tabs are shown.
 *
 * What the form jumps to after a failed check. Null when the refusals
 * are all on the identity row or unaddressed — both are already on
 * screen, and moving the author to an unrelated tab to show them
 * nothing would be worse than staying put. */
export function firstTabWithError(errors: { path: string; message: string }[]): FormTab | null {
  const { byTab } = tallyErrors(errors);
  return FORM_TABS.find((tab) => byTab[tab] > 0) ?? null;
}
