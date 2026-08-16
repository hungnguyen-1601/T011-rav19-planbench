/** The assistant page, and the technical detail that is no longer on it.
 *
 * The brief was specific: no provider name, no model name, no API key
 * variable, no provider status table, no internal tool list, no list of
 * forbidden capabilities, no pip instructions. All of that was true and
 * useful — to a developer — and it was in front of everybody.
 *
 * Source-level, because the page is a client component whose body is
 * behind an effect and a fetch; asserting on its first paint would
 * assert on a loading state. What matters is that these strings are not
 * in the file at all.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(process.cwd(), "src", "app");

/**
 * The file with its comments removed.
 *
 * The page's own docstring names what was taken off it — "a provider
 * readiness table", "instructions about pip install" — and a blunt
 * substring search would flag those as leaks. Only code and markup can
 * reach a user's screen, so only those are searched.
 */
function withoutComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

const ASSISTANT = withoutComments(readFileSync(join(APP, "agent", "page.tsx"), "utf8"));

function pageFiles(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const full = join(directory, entry);
    if (statSync(full).isDirectory()) {
      if (entry !== "__tests__") found.push(...pageFiles(full));
    } else if (entry === "page.tsx") {
      found.push(full);
    }
  }
  return found;
}

/** Everything the brief said to remove from the user-facing assistant. */
const TECHNICAL = [
  "gemini",
  "anthropic",
  "openai",
  "openrouter",
  "deepseek",
  "api_key",
  "API_KEY",
  "pip install",
  "provider",
  "deterministic",
  "list_scenarios",
  "create_benchmark",
  "drive_robot",
  "forbidden",
  "knowledge_documents",
];

describe("the assistant page shows nothing technical", () => {
  for (const term of TECHNICAL) {
    it(`does not mention ${term}`, () => {
      expect(ASSISTANT.toLowerCase()).not.toContain(term.toLowerCase());
    });
  }

  it("does not import the old agent types", () => {
    expect(ASSISTANT).not.toContain("AgentCapabilities");
    expect(ASSISTANT).not.toContain("ProviderInfo");
  });
});

describe("the assistant page is a chat", () => {
  it("has a thread, a composer and a send button", () => {
    expect(ASSISTANT).toContain("chat-thread");
    expect(ASSISTANT).toContain("chat-composer");
    expect(ASSISTANT).toContain("chat.send");
  });

  it("has a stop button for while it is answering", () => {
    expect(ASSISTANT).toContain("chat.stop");
    expect(ASSISTANT).toContain("AbortController");
  });

  it("offers quick prompts", () => {
    expect(ASSISTANT).toContain("QUICK_PROMPTS");
  });

  it("shows a proposal card with an explicit create button", () => {
    expect(ASSISTANT).toContain("ProposalCard");
    expect(ASSISTANT).toContain("chat.createDraft");
  });

  it("shows a result card", () => {
    expect(ASSISTANT).toContain("ResultCardView");
  });

  it("says out loud that it never runs anything", () => {
    expect(ASSISTANT).toContain("chat.noRun");
  });
});

describe("no page asks for a model path", () => {
  it("is absent from every page", () => {
    // The whole point of the registry: a user is never asked where a
    // file lives on the server.
    const offenders = pageFiles(APP)
      .filter((file) => readFileSync(file, "utf8").includes("model_path"))
      .map((file) => file.replace(APP, "").replace(/\\/g, "/"));
    expect(offenders).toEqual([]);
  });

  it("the benchmark form sends a model id instead", () => {
    const form = readFileSync(join(APP, "benchmarks", "page.tsx"), "utf8");
    expect(form).toContain("model_id");
    expect(form).not.toContain("model_path");
  });

  it("the benchmark form has an empty state instead of a validation error", () => {
    const form = readFileSync(join(APP, "benchmarks", "page.tsx"), "utf8");
    expect(form).toContain("benchmarks.noModels.title");
    expect(form).toContain("benchmarks.uploadModel");
    expect(form).toContain("benchmarks.useDwaInstead");
  });
});

describe("the model registry page", () => {
  const modelsFile = join(APP, "models", "page.tsx");
  const REGISTRY = existsSync(modelsFile) ? readFileSync(modelsFile, "utf8") : "";

  it("explains what a PPO model is", () => {
    if (!REGISTRY) return;
    expect(REGISTRY).toContain("models.whatIsPpo");
  });

  it("has an empty state rather than an error when nothing is uploaded", () => {
    if (!REGISTRY) return;
    expect(REGISTRY).toContain("models.empty.title");
  });

  it("never renders a storage location", () => {
    if (!REGISTRY) return;
    expect(REGISTRY).not.toContain("storage_key");
    expect(REGISTRY).not.toContain("model_path");
  });
});
