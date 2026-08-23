/** The assistant, browser side.
 *
 * Two properties: replies are translation keys (so both languages stay
 * in step), and nothing in this module can run a benchmark.
 */

import { describe, expect, it } from "vitest";

import { QUICK_PROMPTS, isMessageKey } from "@/lib/chat";
import { DICTIONARIES } from "@/lib/i18n";
import * as chat from "@/lib/chat";

describe("assistant replies are translation keys", () => {
  it("recognises one", () => {
    expect(isMessageKey("chat.proposalReady")).toBe(true);
  });

  it("does not mistake a user's own words for a key", () => {
    expect(isMessageKey("chat with me about benchmarks")).toBe(false);
    expect(isMessageKey("Tôi muốn kiểm thử robot")).toBe(false);
  });

  it("has both languages for every reply the backend can send", () => {
    // These strings come from chat_service.py. A missing translation
    // renders the raw key, which is a bug nobody notices in review.
    const replies = [
      "chat.proposalReady",
      "chat.needScenario",
      "chat.needModel",
      "chat.noResults",
      "chat.explainLatest",
      "chat.help",
      "chat.draftCreated",
    ];
    for (const key of replies) {
      expect(DICTIONARIES.en[key], `${key} missing in English`).toBeTruthy();
      expect(DICTIONARIES.vi[key], `${key} missing in Vietnamese`).toBeTruthy();
    }
  });
});

describe("quick prompts", () => {
  it("offers the five the brief asked for", () => {
    expect(QUICK_PROMPTS).toHaveLength(5);
  });

  it("translates all of them", () => {
    for (const key of QUICK_PROMPTS) {
      expect(DICTIONARIES.en[key]).toBeTruthy();
      expect(DICTIONARIES.vi[key]).toBeTruthy();
    }
  });
});

describe("the client cannot run a benchmark from chat", () => {
  it("exports no run, approve or accept function", () => {
    // Enforced by absence, and asserted so adding one is a deliberate
    // act that breaks a test saying not to.
    const exported = Object.keys(chat);
    for (const name of exported) {
      expect(name.toLowerCase()).not.toContain("run");
      expect(name.toLowerCase()).not.toContain("approve");
      expect(name.toLowerCase()).not.toContain("accept");
    }
  });

  it("creating a draft is a separate call from sending a message", () => {
    // Two functions, two endpoints: a message can never create.
    expect(typeof chat.sendMessage).toBe("function");
    expect(typeof chat.confirmDraft).toBe("function");
    expect(chat.sendMessage).not.toBe(chat.confirmDraft);
  });
});
