/** The LLM agent: one question, one answer, tools in between.
 *
 * Stateless on the server. The transcript lives in the page, which keeps
 * a refresh honest — there is no hidden context making the second answer
 * depend on a first the reader cannot see.
 */

import { authFetch } from "./auth";

export interface ProviderInfo {
  name: string;
  ready: boolean;
  api_key_env: string;
  missing: string;
}

export interface Capabilities {
  provider: string;
  model: string;
  /** True means the answer came from the offline keyword responder, not
   *  a model. Shown rather than inferred: the two read alike. */
  deterministic: boolean;
  tools: string[];
  /** Capabilities the agent must never have, published so the claim is
   *  checkable rather than promised. */
  forbidden: string[];
  knowledge_documents: number;
  providers: ProviderInfo[];
}

export interface ChatTurn {
  text: string;
  /** Which tools ran. This is the evidence that an answer came from
   *  stored data rather than from the model's memory. */
  tools_used: string[];
  tool_errors: string[];
  iterations: number;
  /** The tool budget ran out before an answer. Nothing is asserted. */
  truncated: boolean;
}

export interface ChatResponse {
  provider: string;
  model: string;
  deterministic: boolean;
  turn: ChatTurn;
}

export function getCapabilities(): Promise<Capabilities> {
  return authFetch<Capabilities>("/agent/capabilities");
}

export function askAgent(message: string, signal?: AbortSignal): Promise<ChatResponse> {
  return authFetch<ChatResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
    signal,
  });
}
