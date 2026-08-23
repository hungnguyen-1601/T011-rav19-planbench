/** The floating assistant, and the promises it does not make.
 *
 * `renderToStaticMarkup` covers first render, which is where the claims
 * below live: what it says when nothing is connected, and that it takes
 * no width from the page.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AgentDock } from "@/components/AgentDock";
import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const CSS = readFileSync(join(SRC, "app", "globals.css"), "utf8");
const SHELL = readFileSync(join(SRC, "components", "AppShell.tsx"), "utf8");
const DOCK = readFileSync(join(SRC, "components", "AgentDock.tsx"), "utf8");

const html = () => renderToStaticMarkup(<AgentDock />);

describe("the launcher", () => {
  it("is a button, closed on first paint", () => {
    /* A panel that opens itself takes a corner of every page from
       somebody who did not ask for it. */
    expect(html()).toContain('aria-expanded="false"');
    expect(html()).not.toContain("agent-dock-panel");
  });

  it("sits bottom-right, away from the framework's own overlay", () => {
    /* Bottom-left already belongs to the dev overlay, and two circles in
       one corner is one corner nobody can use. */
    const rule = CSS.slice(CSS.indexOf(".agent-dock {"), CSS.indexOf(".agent-dock-launcher"));
    expect(rule).toContain("position: fixed;");
    expect(rule).toContain("right:");
    expect(rule).toContain("bottom:");
    expect(rule).not.toContain("left:");
  });
});

describe("it floats rather than docking", () => {
  it("is mounted outside the content column", () => {
    /* Every canvas here is sized in pixels rather than percentages, so a
       dock that took width from the content would move every click on a
       map by however wide it happened to be. */
    const shell = SHELL.slice(SHELL.indexOf("</main>"));
    expect(shell).toContain("<AgentDock />");
    expect(SHELL.indexOf("<AgentDock />")).toBeGreaterThan(SHELL.indexOf("</main>"));
  });

  it("changes no layout width", () => {
    expect(SHELL).not.toContain("agentWidth");
    expect(CSS).not.toContain(".layout.has-agent");
  });
});

describe("it says it is not connected", () => {
  it("disables the composer rather than swallowing a question", () => {
    /* A chat box that accepts a question and answers with silence leaves
       somebody wondering whether their question was bad. */
    expect(DOCK).toContain("<input\n              type=\"text\"\n              disabled");
    expect(DOCK).toContain('<button type="submit" disabled>');
  });

  it("says so in the panel and in the header", () => {
    expect(en).toHaveProperty("agentDock.placeholder");
    expect(vi).toHaveProperty("agentDock.placeholder");
    expect((en as Record<string, string>)["agentDock.subtitle"]).toContain("Not connected");
  });

  it("stops a stray Enter from reloading the page", () => {
    /* There is nothing to submit to, so the browser's default would be a
       navigation nobody asked for. */
    expect(DOCK).toContain("event.preventDefault();");
  });
});

describe("closing it", () => {
  it("answers Escape and an outside click", () => {
    expect(DOCK).toContain("useDismiss(open, () => setOpen(false), dockRef)");
  });

  it("holds the launcher inside the dismissed subtree", () => {
    /* Otherwise clicking the button to close registers as an outside
       click, closes the panel, and the same gesture reopens it. */
    expect(DOCK).toContain('<div className="agent-dock" ref={dockRef}>');
  });
});

describe("translation keys", () => {
  const keys = [...DOCK.matchAll(/t\(\s*"([a-zA-Z0-9_.]+)"/g)].map((hit) => hit[1]);

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});
