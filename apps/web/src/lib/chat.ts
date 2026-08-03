"use client";

/** The assistant, from the browser's side.
 *
 * Notice what is absent: no provider name, no model name, no API key
 * variable, no tool list. Those are diagnostics and live on /system.
 * A person preparing a benchmark never needs them, and putting them in
 * front of everyone was the main thing wrong with the old page.
 *
 * Creating a benchmark is two calls, not one. `sendMessage` may return a
 * proposal; `confirmDraft` acts on it. The assistant cannot create
 * anything on its own, and cannot run anything at all.
 */

import { authFetch } from "./auth";

export type ChatRole = "user" | "assistant";

export interface BenchmarkProposal {
  id: string;
  name: string;
  map_id: string;
  scenario_id: string;
  scenario_name: string;
  stacks: string[];
  seeds: number[];
  robot_profile_id: string;
  model_id: string;
  model_label: string;
  user_priority: string;
  assumptions: string[];
  missing_fields: string[];
  warnings: string[];
  status: "draft" | "confirmed" | "cancelled";
  benchmark_id: string;
}

export interface ResultCard {
  benchmark_id: string;
  name: string;
  state: string;
  conditions_checksum: string;
  aggregates: {
    algorithm: string;
    episodes: number;
    success_rate: number;
    collision_rate: number;
    timeout_rate: number;
    mean_travel_time: number | null;
    worst_min_clearance: number | null;
    mean_latency: number | null;
  }[];
}

export interface ChatMessage {
  sequence: number;
  role: ChatRole;
  content: string;
  proposal: BenchmarkProposal | null;
  result: ResultCard | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  locale: string;
  created_at: string;
  updated_at: string;
}

export function startConversation(locale: string): Promise<Conversation> {
  return authFetch<Conversation>("/ai/conversations", {
    method: "POST",
    body: JSON.stringify({ locale }),
  });
}

export function listConversations(): Promise<Conversation[]> {
  return authFetch<Conversation[]>("/ai/conversations");
}

export function getConversation(
  id: string,
): Promise<{ conversation: Conversation; messages: ChatMessage[] }> {
  return authFetch(`/ai/conversations/${id}`);
}

export function deleteConversation(id: string): Promise<void> {
  return authFetch<void>(`/ai/conversations/${id}`, { method: "DELETE" });
}

export function sendMessage(conversationId: string, message: string): Promise<ChatMessage> {
  return authFetch<ChatMessage>(`/ai/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function confirmDraft(conversationId: string, proposalId: string): Promise<ChatMessage> {
  return authFetch<ChatMessage>(`/ai/conversations/${conversationId}/confirm-draft`, {
    method: "POST",
    body: JSON.stringify({ proposal_id: proposalId }),
  });
}

export function latestResult(): Promise<ResultCard | null> {
  return authFetch<ResultCard | null>("/ai/latest-result");
}

/**
 * The assistant's replies are translation *keys*, not prose.
 *
 * The backend decides which situation applies; the UI renders it in the
 * reader's language. That is what keeps English and Vietnamese from
 * drifting apart somewhere nobody looks — and it means the assistant
 * cannot accidentally answer in the wrong language.
 */
export function isMessageKey(content: string): boolean {
  return content.startsWith("chat.");
}

/** Suggestions offered on an empty conversation. */
export const QUICK_PROMPTS = [
  "chat.quick.createBenchmark",
  "chat.quick.whichAlgorithm",
  "chat.quick.analyseLatest",
  "chat.quick.whyStuck",
  "chat.quick.compare",
] as const;
