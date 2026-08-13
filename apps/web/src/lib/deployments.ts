/** Filing a deployment from a form instead of from a pasted document.
 *
 * **The form and the paste box must produce the same artifact.** A task
 * profile is a contract document under HĐ-2 — readable, diffable,
 * committable — and the form is an *input method* for it, not a second
 * way of saying what a deployment is. Everything here exists to keep
 * that true: the defaults come from the shipped profile rather than a
 * copy, and a chosen map becomes the same two paths a person would have
 * typed.
 *
 * **Nothing here validates.** `TaskProfile` on the server decides, and a
 * second opinion in the browser would be free to disagree with the one
 * that actually refuses.
 */

import { authFetch } from "./auth";
import type { LibraryEntry } from "./platformTypes";
import type { MapData, Pose2D, Scenario } from "./types";

/** A profile as it travels: the same JSON the paste box parses its YAML
 *  into. Deliberately loose — the shape is the server's to define, and a
 *  mirrored interface here would be the second definition this module
 *  exists to avoid. */
export type ProfileDraft = Record<string, unknown>;

/** The values a blank form opens with, read from the shipped profile.
 *
 * Served rather than hand-copied into TypeScript: a duplicate set of
 * numbers would keep handing out the old ones the day somebody tunes
 * `open_hall_v2`. The `id` comes back empty on purpose — re-filing an
 * existing id with different content is refused (HĐ-3.1), so a template
 * carrying one would make the first submit fail for a reason the author
 * did not choose.
 */
export function getProfileTemplate(): Promise<ProfileDraft> {
  return authFetch<ProfileDraft>("/task-profiles/template");
}

/** The two paths a profile names, for a map held in the store.
 *
 * The crossing between how a map is *edited* (a grid in the database)
 * and how a profile *names* it (two paths, HĐ-2). Writes the pair; safe
 * to call twice, since the filename is (map id, version).
 */
export function materialiseMap(mapId: string): Promise<{ map: string; map_yaml: string }> {
  return authFetch<{ map: string; map_yaml: string }>(`/maps/${mapId}/materialise`, {
    method: "POST",
  });
}

export function listScenarioLibrary(): Promise<LibraryEntry[]> {
  return authFetch<LibraryEntry[]>("/scenario-library");
}

/** Turn a built-in scenario into a stored map, and hand back its poses.
 *
 * The scenario's own start and goal come with it, and that is the point:
 * they are a pair the author of the scenario chose and knows is
 * drivable. Inventing one from the map's size would be guessing at a
 * question somebody already answered.
 */
export function importLibraryScenario(name: string): Promise<{
  map_id: string;
  scenario: Scenario;
}> {
  return authFetch<{ map_id: string; scenario: Scenario }>(`/scenario-library/${name}/import`, {
    method: "POST",
  });
}

/** The library entry a blank form opens on.
 *
 * Pillars in a hall: not empty, so a planner has something to weave
 * around, and with no moving traffic — which matches what the form can
 * currently express. It is also the scenario the tuning harness already
 * uses as its reference, so it is a shape this project already trusts.
 */
export const DEFAULT_LIBRARY_SCENARIO = "static_obstacles";

/** Where the robot starts and stops on a map nobody wrote a mission for.
 *
 * **A starting point, not a promise.** On a map somebody drew, this pair
 * can land inside a wall — and the server will refuse it with a reason
 * (`validate_missions_on_map` catches five ways a profile and a map
 * disagree). Producing a pair that is *guaranteed* drivable would mean
 * running a path search in the browser, which is a second implementation
 * of the planner.
 *
 * The 1.5 m inset is the same one `defaultScenario` has always used, so
 * a map that worked in the old editor opens the same way here.
 */
export function fallbackPoses(map: MapData): { start: Pose2D; goal: Pose2D } {
  const worldWidth = map.width * map.resolution;
  const worldHeight = map.height * map.resolution;
  return {
    start: { x: 1.5, y: 1.5, theta: 0 },
    goal: { x: worldWidth - 1.5, y: worldHeight - 1.5, theta: 0 },
  };
}

/** A scenario's own poses when there is one, the map's corners otherwise. */
export function posesFor(map: MapData, scenario?: Scenario | null): {
  start: Pose2D;
  goal: Pose2D;
} {
  if (!scenario) return fallbackPoses(map);
  return { start: { ...scenario.start_pose }, goal: { ...scenario.goal_pose } };
}

/** Read one nested value out of a draft, or undefined.
 *
 * The draft is loose JSON on purpose (see `ProfileDraft`), so every field
 * the form binds goes through here rather than through a cast that would
 * quietly claim a shape nobody checked.
 */
export function at(draft: ProfileDraft, path: string): unknown {
  let current: unknown = draft;
  for (const key of path.split(".")) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

/** The draft with one nested value replaced, copied down the path.
 *
 * Copied rather than mutated so React sees a new object at every level
 * it renders from — a mutation would update the draft and leave the
 * inputs showing the previous value until something else re-rendered.
 */
export function withValue(draft: ProfileDraft, path: string, value: unknown): ProfileDraft {
  const [head, ...rest] = path.split(".");
  if (rest.length === 0) return { ...draft, [head]: value };
  const child = draft[head];
  const nested = child !== null && typeof child === "object" ? (child as ProfileDraft) : {};
  return { ...draft, [head]: withValue(nested, rest.join("."), value) };
}

/** Episodes the declared collision risk demands: ceil(3 / p) (HĐ-7.1).
 *
 * Shown beside the risk field because the arrow runs one way and people
 * expect it to run the other: the risk decides the episode count, and a
 * warehouse at 1% is 300 episodes and hours of simulation. Recomputed in
 * the browser purely to *display* the consequence — the server derives
 * its own, and this one never travels.
 */
export function nMinFor(risk: unknown): number | null {
  if (typeof risk !== "number" || !Number.isFinite(risk) || risk <= 0 || risk > 1) return null;
  return Math.ceil(Number((3 / risk).toFixed(6)));
}

/** What the RAM breakdown leaves for navigation, as the profile counts it.
 *
 * Not a rule — the server owns whether the arithmetic has to balance.
 * This only puts the subtraction in front of somebody typing the numbers,
 * because four figures that must add up are four chances to be one out.
 */
export function ramLeftOver(draft: ProfileDraft): number | null {
  const total = at(draft, "hardware.total_ram_mb");
  const breakdown = at(draft, "hardware.ram_budget_breakdown");
  if (typeof total !== "number" || breakdown === null || typeof breakdown !== "object") return null;
  let spent = 0;
  for (const value of Object.values(breakdown as Record<string, unknown>)) {
    if (typeof value !== "number") return null;
    spent += value;
  }
  return total - spent;
}
