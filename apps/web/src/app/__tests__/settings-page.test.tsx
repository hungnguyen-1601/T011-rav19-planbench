/** The settings page, and the four things it must not get wrong.
 *
 * No jsdom in this repo, so the form is asserted through
 * `renderToStaticMarkup` — real HTML from a real render, which covers
 * everything the brief is about except the click. The click is covered
 * where the behaviour actually lives: `saveAgentKey` is checked against
 * a stubbed `fetch`, so the method, the path and the body are the
 * assertion rather than a button that was pressed.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentSettingsForm } from "@/components/AgentSettingsForm";
import { NAV_SECTIONS } from "@/lib/navigation";
import type { AgentSettings } from "@/lib/settings";
import en from "../../lib/i18n/locales/en.json";
import viLocale from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const PAGE = readFileSync(join(SRC, "app", "settings", "page.tsx"), "utf8");
const SIDEBAR = readFileSync(join(SRC, "components", "Sidebar.tsx"), "utf8");
const CSS = readFileSync(join(SRC, "app", "globals.css"), "utf8");

const LIVE: AgentSettings = {
  provider: "openai",
  model: "o4-mini",
  models: ["o4-mini"],
  api_key_env: "OPENAI_API_KEY",
  key_present: true,
  key_hint: "••••9876",
  ready: true,
  missing: "",
  active_provider: "openai",
  active_model: "o4-mini",
  active_deterministic: false,
};

const OFFLINE: AgentSettings = {
  ...LIVE,
  key_present: false,
  key_hint: "",
  ready: false,
  missing: "OPENAI_API_KEY is not set",
  active_provider: "mock",
  active_model: "",
  active_deterministic: true,
};

function form(overrides: Partial<Parameters<typeof AgentSettingsForm>[0]> = {}): string {
  return renderToStaticMarkup(
    <AgentSettingsForm
      settings={LIVE}
      canEdit
      saving={false}
      saved={false}
      error={null}
      fieldErrors={[]}
      onSave={() => {}}
      {...overrides}
    />,
  );
}

describe("the form an admin sees", () => {
  it("offers the model as a disabled choice, not as a missing one", () => {
    /* One option is still the answer to "which model is this". A
       control that vanishes when there is nothing to pick leaves the
       reader unable to tell whether the choice exists at all. */
    const html = form();
    expect(html).toContain("<select");
    expect(html).toContain("disabled");
    expect(html).toContain("o4-mini");
    expect(html).toContain(en["settings.model.hint"]);
  });

  it("takes the key in a password field and offers a save", () => {
    const html = form();
    expect(html).toContain('type="password"');
    expect(html).toContain('class="primary"');
  });

  it("will not submit an empty key", () => {
    /* Disabled on first paint, because the field starts empty and a
       button that sends nothing spends a round trip to be told so. */
    expect(form()).toContain('class="primary" disabled=""');
  });

  it("names the environment variable the server reads", () => {
    expect(form()).toContain("OPENAI_API_KEY");
  });
});

describe("the key never comes back", () => {
  it("shows the hint as the current state, and nothing longer", () => {
    /* `key_hint` is a masked tail. Rendering anything the server did
       not mask would be the page handing back the secret it was
       trusted with. */
    const html = form();
    expect(html).toContain("••••9876");
    expect(html).not.toContain("sk-test");
  });

  it("says so plainly when there is no key at all", () => {
    const html = form({ settings: OFFLINE });
    expect(html).toContain(en["settings.key.absent"]);
    expect(html).not.toContain(en["settings.key.current"].split("{")[0].trim());
  });
});

describe("what is answering, not what is configured", () => {
  it("warns while the offline responder is the one replying", () => {
    /* The failure this exists to stop: a saved key reads as done, and
       the reader never learns that the built-in keyword responder is
       still producing every answer. */
    const html = form({ settings: OFFLINE });
    expect(html).toContain('class="badge warn"');
    expect(html).toContain(en["settings.status.offline"]);
    expect(html).toContain(en["settings.status.offlineHint"]);
  });

  it("goes green only when a real provider is answering", () => {
    const html = form();
    expect(html).toContain('class="badge ok"');
    expect(html).toContain("openai");
    expect(html).not.toContain(en["settings.status.offline"]);
  });

  it("does not call a configured-but-inactive key ready", () => {
    /* `key_present` and `active_deterministic` can both be true: the
       key is stored and the running process has not read it. The
       warning wins. */
    const stored: AgentSettings = { ...OFFLINE, key_present: true, key_hint: "••••1234" };
    const html = form({ settings: stored });
    expect(html).toContain("••••1234");
    expect(html).toContain(en["settings.status.offline"]);
    expect(html).not.toContain('class="badge ok"');
  });
});

describe("a reader who is not an admin", () => {
  it("gets no save control and is told why", () => {
    const html = form({ canEdit: false });
    expect(html).not.toContain('type="password"');
    expect(html).not.toContain('class="primary"');
    expect(html).toContain(en["settings.readOnly"]);
  });

  it("still sees which model answers and whether a key is present", () => {
    /* Read-only, not hidden. "Why is the assistant giving canned
       answers" is a question anyone on the deployment can have. */
    const html = form({ canEdit: false, settings: OFFLINE });
    expect(html).toContain("o4-mini");
    expect(html).toContain(en["settings.status.offline"]);
  });

  it("is not offered the entry in the rail either", () => {
    // Matched on the capability the account holds rather than on a
    // role: the server sends what this account may do, and comparing
    // against that is what keeps the rail from drifting the day a
    // capability moves between packages.
    expect(SIDEBAR).toContain("user?.capabilities?.includes(item.capability)");
    expect(SIDEBAR).toContain("visible(section.items, user)");
  });
});

describe("refusals land where the reader is looking", () => {
  it("puts an addressed complaint beside the field", () => {
    const html = form({
      fieldErrors: [{ path: "body.api_key", message: "String should have at least 8 characters" }],
    });
    expect(html).toContain("settings-field-error");
    expect(html).toContain("at least 8 characters");
  });

  it("puts a 403 above the form, where it is about the request", () => {
    const html = form({ error: "Only an administrator may change this." });
    expect(html).toContain('class="error-box"');
    expect(html).toContain("Only an administrator");
  });

  it("uses no alert", () => {
    /* An alert is a refusal the reader has to dismiss before they can
       look at the field it was about. */
    expect(PAGE).not.toContain("alert(");
  });
});

describe("saving", () => {
  const calls: { url: string; init: RequestInit }[] = [];

  beforeEach(() => {
    calls.length = 0;
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ ...LIVE, key_hint: "••••4321" }),
      } as Response);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("PUTs the key to the settings endpoint", async () => {
    const { saveAgentKey } = await import("@/lib/settings");
    await saveAgentKey("sk-test-123456");
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/api/v1/settings/agent");
    expect(calls[0].init.method).toBe("PUT");
    expect(calls[0].init.body).toBe(JSON.stringify({ api_key: "sk-test-123456" }));
  });

  it("reads the current settings from the same path", async () => {
    const { getAgentSettings } = await import("@/lib/settings");
    await getAgentSettings();
    expect(calls[0].url).toContain("/api/v1/settings/agent");
    expect(calls[0].init.method).toBeUndefined();
  });

  it("takes the answer as the new state rather than re-reading", async () => {
    /* The PUT returns the updated settings. Fetching again asks the
       same question twice and opens a window where the screen
       disagrees with the response that just arrived. */
    expect(PAGE).toContain("setSettings(updated)");
    expect(PAGE).not.toContain("getAgentSettings().then");
  });
});

describe("the rail and the dictionaries", () => {
  it("lists the page under Account, for whoever configures the deployment", () => {
    const account = NAV_SECTIONS.find((section) => section.titleKey === "nav.section.account");
    const entry = account?.items.find((item) => item.href === "/settings");
    expect(entry?.capability).toBe("system.configure");
    expect(entry?.session).toBe(true);
    expect(entry?.labelKey).toBe("nav.settings");
  });

  it("has every key it names in both locales", () => {
    const keys = [
      ...new Set([
        ...[...PAGE.matchAll(/t\("([\w.]+)"/g)].map((match) => match[1]),
        ...[...readFileSync(join(SRC, "components", "AgentSettingsForm.tsx"), "utf8").matchAll(
          /t\("([\w.]+)"/g,
        )].map((match) => match[1]),
        "nav.settings",
        "nav.desc.settings",
      ]),
    ];
    expect(keys.length).toBeGreaterThan(10);
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty([key]);
      expect(viLocale, `vi is missing ${key}`).toHaveProperty([key]);
    }
  });

  it("styles itself from the shared stylesheet", () => {
    expect(CSS).toContain(".settings-status");
    expect(CSS).toContain(".settings-field-error");
  });
});
