"use client";

/** Imported algorithm bundles, from the browser's side.
 *
 * The sibling of `models.ts`, and separate for the reason the API keeps
 * them separate: a model is weights for a controller the platform
 * already has, a bundle is a controller it has never seen. Sharing a
 * module would mean one `ModelSummary` with half its fields meaningless
 * depending on which kind of thing it described.
 *
 * Upload goes through `XMLHttpRequest` for the same reason it does
 * there — `fetch` still cannot report upload progress, and an upload
 * with no progress looks exactly like a hung page.
 */

import { API_BASE } from "./api";
import { authFetch, loadSession } from "./auth";
import type { ValidationStatus } from "./models";

/** May this revision be picked, and if not, is that final.
 *
 * A third value on the field that already answered the question rather
 * than a second field beside it. `held` is a reviewer pulling a revision
 * back while they look at something; `disabled` is terminal, and
 * terminal on purpose — "turn it back on" and "upload the fixed one"
 * should not both exist, because only the second is honest about what
 * changed in between.
 */
export type BundleStatus = "active" | "held" | "disabled";

export interface PluginBundleSummary {
  id: string;
  name: string;
  version: string;
  description: string;
  plugin_id: string;
  plugin_version: string;
  /** Which upload of this `plugin_id` this is. Publication names a
   * revision rather than a bundle, so this is what a history row and a
   * pinned run both point at. */
  revision: number;
  role: string;
  requirements: string[];
  robot_profile_id: string;
  original_filename: string;
  file_size: number;
  checksum: string;
  status: BundleStatus;
  validation_status: ValidationStatus;
  validation_message: string;
  owned: boolean;
  created_at: string;
  updated_at: string;
}

/** The host's own preflight answer, field for field.
 *
 * Rendered rather than reworded. Every entry here is a list the host
 * filled in, and `why` is its own one-line explanation — a UI that
 * summarised them into something friendlier would be inventing a
 * diagnosis the platform did not make.
 */
export interface HostCompatibility {
  state: string;
  runnable: boolean;
  evidence_class: string;
  runtime_lane: string;
  why: string;
  missing_capabilities: string[];
  missing_providers: string[];
  missing_runtime: string[];
  incompatible_action_types: string[];
  incompatible_dynamics: string[];
  incompatible_execution_models: string[];
  fairness_refusals: string[];
  undeclared_providers: string[];
  graph_problems: string[];
  provider_order: string[];
  oracle_providers: string[];
}

/** One act of putting a revision in front of everybody.
 *
 * Append-only, and the two closing dates are separate columns because
 * they are separate facts: `superseded_at` means a newer revision took
 * its place, `unpublished_at` means somebody withdrew it and nothing
 * replaced it. A single `ended_at` would answer "is it current?"
 * equally well and "why did it stop?" not at all, which is the question
 * a reader of the history is actually asking.
 */
export interface PluginPublication {
  bundle_id: string;
  revision: number;
  published_at: string;
  published_by_user_id: string | null;
  superseded_at: string | null;
  unpublished_at: string | null;
  reason: string;
  is_current: boolean;
}

export interface PluginEvent {
  sequence: number;
  revision: number;
  actor_user_id: string | null;
  actor_roles: string;
  authorized_capability: string;
  action: string;
  reason: string;
  created_at: string;
}

export interface PluginBundleDetail {
  bundle: PluginBundleSummary;
  compatibility: HostCompatibility;
  /** The revision an engineer would actually get, or `null` while
   * nobody has published one. Sent to every reader, not just a
   * reviewer: "why is this not in my picker?" is a question the person
   * picking has to be able to answer without asking one. */
  published_revision: number | null;
  /** The half that describes code rather than capability. Absent — not
   * empty — for a reader without `algorithm.inspect`, so a component
   * that finds them missing should draw nothing rather than an empty
   * box. */
  manifest?: Record<string, unknown> | null;
  entry_point?: string | null;
  publications?: PluginPublication[] | null;
}

export function pluginEvents(bundleId: string): Promise<PluginEvent[]> {
  return authFetch<PluginEvent[]>(`/algorithms/plugins/${bundleId}/events`);
}

/** The five governed acts, which differ only in the word in the path.
 *
 * All five answer 404 rather than 403 while
 * `PLANBENCH_ALGORITHM_GOVERNANCE` is off, because the truth is "this
 * deployment has not turned publishing on" rather than "you may not" —
 * and a caller that can tell the difference hides the button instead of
 * offering one that always fails.
 */
function govern(
  bundleId: string,
  act: string,
  reason: string,
): Promise<PluginBundleSummary> {
  return authFetch<PluginBundleSummary>(`/algorithms/plugins/${bundleId}/${act}`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export const publishPlugin = (id: string, reason = "") => govern(id, "publish", reason);
export const unpublishPlugin = (id: string, reason: string) => govern(id, "unpublish", reason);
export const holdPlugin = (id: string, reason: string) => govern(id, "hold", reason);
export const releasePluginHold = (id: string, reason = "") => govern(id, "release-hold", reason);
export const disablePlugin = (id: string, reason: string) => govern(id, "disable", reason);

export interface ImportFields {
  name: string;
  version: string;
  description: string;
  robotProfileId: string;
  bundleFile: File;
}

export function listPlugins(): Promise<PluginBundleSummary[]> {
  return authFetch<PluginBundleSummary[]>("/algorithms/plugins");
}

export function getPlugin(bundleId: string): Promise<PluginBundleDetail> {
  return authFetch<PluginBundleDetail>(`/algorithms/plugins/${bundleId}`);
}

export function setPluginStatus(
  bundleId: string,
  status: BundleStatus,
): Promise<PluginBundleSummary> {
  return authFetch<PluginBundleSummary>(`/algorithms/plugins/${bundleId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

/** Change what is *written about* a bundle, never what it is.
 *
 * The manifest and the archive are identity: a bundle whose code could
 * be edited in place would let one `plugin_id` at one version mean two
 * different controllers, and every result recorded against it would stop
 * being attributable. The server refuses those fields; this only ever
 * sends the four it accepts.
 */
export function updatePlugin(
  bundleId: string,
  changes: {
    name?: string;
    version?: string;
    description?: string;
    robot_profile_id?: string;
  },
): Promise<PluginBundleSummary> {
  return authFetch<PluginBundleSummary>(`/algorithms/plugins/${bundleId}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export function revalidatePlugin(bundleId: string): Promise<PluginBundleSummary> {
  return authFetch<PluginBundleSummary>(`/algorithms/plugins/${bundleId}/validate`, {
    method: "POST",
  });
}

export function importPlugin(
  fields: ImportFields,
  onProgress: (percent: number) => void,
): Promise<PluginBundleSummary> {
  const session = loadSession();
  const body = new FormData();
  body.append("name", fields.name);
  body.append("version", fields.version || "1");
  body.append("description", fields.description);
  body.append("robot_profile_id", fields.robotProfileId);
  body.append("bundle", fields.bundleFile);

  return new Promise<PluginBundleSummary>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/api/v1/algorithms/plugins`);
    if (session) request.setRequestHeader("Authorization", `Bearer ${session.token}`);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      let parsed: unknown = null;
      try {
        parsed = JSON.parse(request.responseText);
      } catch {
        // A non-JSON body means something upstream failed; the status is
        // then the only thing worth reporting.
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(parsed as PluginBundleSummary);
        return;
      }
      const message =
        (parsed as { error?: { message?: string } })?.error?.message ??
        `Import failed (${request.status})`;
      reject(new Error(message));
    };
    request.onerror = () => reject(new Error("The upload could not reach the server."));
    request.onabort = () => reject(new Error("Upload cancelled."));
    request.send(body);
  });
}

/** Whether this bundle may be offered as a candidate.
 *
 * **Two conditions, and both are load-bearing.** `active` is a decision
 * somebody made; `loaded` is the conformance suite having actually run
 * the plugin and found it behaved. `structural` is neither a pass nor a
 * failure — it is "nobody has run this yet", and offering it would put a
 * candidate in a comparison on the strength of its archive being
 * readable.
 *
 * The API refuses such a stack anyway; this is the same rule stated
 * where the button lives, so the answer arrives before the click rather
 * than as a 422 after it.
 */
export function isSelectable(bundle: PluginBundleSummary): boolean {
  return bundle.status === "active" && bundle.validation_status === "loaded";
}

/** The single sentence a row shows about why it cannot be picked.
 *
 * Ordered by what the reader can act on: a disabled bundle is one
 * decision away from running, a failed one needs its code changed, and
 * an unverified one needs whatever stopped the run. Returns `null` when
 * there is nothing to say, so a caller cannot render an empty warning.
 */
export function blockedReason(bundle: PluginBundleSummary): string | null {
  if (isSelectable(bundle)) return null;
  if (bundle.status !== "active") return "disabled";
  if (bundle.validation_status === "failed") return "failed";
  return "unverified";
}

/** What to call each bundle's state, in one word a reader can act on.
 *
 * A projection, not a stored field. The server keeps three orthogonal
 * facts — may it be picked, did it load, is it published — because each
 * is set by a different act, and a stored label collapsing them would be
 * a fourth fact free to disagree with the other three. Collapsing them
 * *here*, for display, is what a status chip is for.
 *
 * Labels the whole list at once because one of the seven answers cannot
 * be reached from a single row: `superseded` means *another* revision of
 * the same `plugin_id` is the published one, so the verdict needs the
 * siblings. `awaiting` — nobody has published any of them — reads the
 * same to a picker but not to a reviewer, who has something to do about
 * exactly one of the two.
 */
export type BundleState =
  | "disabled"
  | "held"
  | "broken"
  | "checking"
  | "published"
  | "superseded"
  | "awaiting";

export function bundleStates(
  bundles: readonly PluginBundleSummary[],
  publishedIds: readonly string[],
): Map<string, BundleState> {
  const published = new Set(publishedIds);
  const pluginsWithOne = new Set(
    bundles.filter((bundle) => published.has(bundle.id)).map((bundle) => bundle.plugin_id),
  );
  return new Map(
    bundles.map((bundle) => {
      let state: BundleState;
      if (bundle.status === "disabled") state = "disabled";
      else if (bundle.status === "held") state = "held";
      else if (bundle.validation_status === "failed") state = "broken";
      else if (bundle.validation_status !== "loaded") state = "checking";
      else if (published.has(bundle.id)) state = "published";
      else state = pluginsWithOne.has(bundle.plugin_id) ? "superseded" : "awaiting";
      return [bundle.id, state] as const;
    }),
  );
}

export function publishedBundleIds(): Promise<string[]> {
  return authFetch<string[]>("/algorithms/plugins/published");
}

/** The stack id a benchmark would name this plugin by.
 *
 * `<global>+<plugin id>` — the plugin's own id rather than its display
 * name, because that is what the candidate hashes on. Shown in the row
 * so somebody reading a report can match the two.
 */
export function stackIdFor(bundle: PluginBundleSummary, globalPlanner = "astar"): string {
  return `${globalPlanner}+${bundle.plugin_id}`;
}
