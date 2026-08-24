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
import type { ModelStatus, ValidationStatus } from "./models";

export interface PluginBundleSummary {
  id: string;
  name: string;
  version: string;
  description: string;
  plugin_id: string;
  plugin_version: string;
  role: string;
  requirements: string[];
  robot_profile_id: string;
  original_filename: string;
  file_size: number;
  checksum: string;
  status: ModelStatus;
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

export interface PluginBundleDetail {
  bundle: PluginBundleSummary;
  compatibility: HostCompatibility;
}

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
  status: ModelStatus,
): Promise<PluginBundleSummary> {
  return authFetch<PluginBundleSummary>(`/algorithms/plugins/${bundleId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
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

/** The stack id a benchmark would name this plugin by.
 *
 * `<global>+<plugin id>` — the plugin's own id rather than its display
 * name, because that is what the candidate hashes on. Shown in the row
 * so somebody reading a report can match the two.
 */
export function stackIdFor(bundle: PluginBundleSummary, globalPlanner = "astar"): string {
  return `${globalPlanner}+${bundle.plugin_id}`;
}
