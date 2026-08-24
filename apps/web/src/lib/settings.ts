/** Agent settings: which model answers, and whether a key is present.
 *
 * Two shapes live in one record and the difference is the whole point.
 * `provider`/`model`/`key_present` describe what is **configured**;
 * `active_provider`/`active_model`/`active_deterministic` describe what
 * is **answering right now**. A saved key that the process has not
 * picked up yet reads as configured and offline at the same time, and a
 * page that showed only the first would tell the reader they were done
 * while the offline responder kept replying.
 *
 * The key itself never travels back. `key_hint` is the last few
 * characters behind bullets — enough to tell two keys apart, not enough
 * to be one.
 */

import { authFetch } from "./auth";

export interface AgentSettings {
  /** Configured provider, whether or not it is the one answering. */
  provider: string;
  model: string;
  /** Every model this provider offers. One entry today. */
  models: string[];
  /** Environment variable the server reads the key from. */
  api_key_env: string;
  key_present: boolean;
  /** Masked tail of the stored key, or empty when there is none. */
  key_hint: string;
  ready: boolean;
  /** What is missing when `ready` is false. Empty otherwise. */
  missing: string;
  /** The provider actually producing answers. */
  active_provider: string;
  active_model: string;
  /** True means the offline keyword responder is answering, not a
   *  model — no key, or a key the running process has not read yet. */
  active_deterministic: boolean;
}

export function getAgentSettings(): Promise<AgentSettings> {
  return authFetch<AgentSettings>("/settings/agent");
}

/** Store a new key. Admin only; anyone else gets a 403. */
export function saveAgentKey(apiKey: string): Promise<AgentSettings> {
  return authFetch<AgentSettings>("/settings/agent", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}
