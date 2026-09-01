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
const ANALYST = readFileSync(join(SRC, "components", "DockAnalyst.tsx"), "utf8");
const ICON = readFileSync(join(SRC, "components", "Icon.tsx"), "utf8");

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

describe("it is wired to the agent that exists", () => {
  /* This dock spent its first version disabling its own composer, which
     was honest while nothing was behind it. The agent was behind it the
     whole time -- `POST /agent/chat`, reachable only from a tile on the
     dashboard once the sidebar entry came off. These lock the join, so
     the dead box cannot come back by accident. */

  it("asks the same endpoint the full agent page asks", () => {
    /* The third argument is the run the reader has open. It arrived
       when the dock learned to answer about the page rather than about
       nothing, and this pin was left describing the two-argument call
       -- so it had been red since, saying the dock was unwired while
       the dock was working. Pinned loosely on purpose: what matters is
       that one client is called, not how many things it takes. */
    expect(DOCK).toContain('from "@/lib/agent"');
    expect(DOCK).toContain("await askAgent(message, controller.signal");
  });

  it("no longer describes itself as unconnected", () => {
    const strings = en as Record<string, string>;
    expect(strings["agentDock.subtitle"]).not.toContain("Not connected");
    expect(strings["agentDock.placeholder"]).not.toContain("Nothing is wired");
    expect(vi).toHaveProperty("agentDock.placeholder");
  });

  it("takes a question only when there is a session to send it with", () => {
    /* Signed out, the request comes back 401 after the reader has
       already typed. */
    expect(DOCK).toContain("disabled={!session}");
    expect(DOCK).toContain('t("agentDock.signedOut")');
  });

  it("stops a stray Enter from reloading the page, then sends", () => {
    /* The browser default is a navigation nobody asked for, and it would
       take the transcript with it -- the thread lives in this component
       because the server keeps none. */
    expect(DOCK).toContain("event.preventDefault();");
    expect(DOCK).toContain("void ask();");
  });
});

describe("what it says about an answer, beside the answer", () => {
  it("marks an answer that no model produced", () => {
    /* The offline keyword responder and a real model read alike. */
    expect(DOCK).toContain("entry.deterministic");
    expect(DOCK).toContain('t("agentDock.mock")');
  });

  it("says when the tool budget ran out first", () => {
    /* A turn that stopped mid-thought reads as a finished one unless it
       is named. */
    expect(DOCK).toContain("entry.turn?.truncated");
    expect(DOCK).toContain('t("agentDock.truncated")');
  });

  it("names the tools an answer was read from", () => {
    expect(DOCK).toContain("entry.turn.tools_used");
    expect(DOCK).toContain("entry.turn.tool_errors");
  });
});

describe("a request outlives the panel", () => {
  it("is not cancelled when the dock closes", () => {
    /* Clicking away from a question is not withdrawing it, and only the
       panel unmounts -- the transcript is state on the component, so an
       answer that lands while it is shut is waiting on reopen. */
    const closer = DOCK.slice(DOCK.indexOf("agent-dock-close"));
    expect(closer.slice(0, closer.indexOf("</button>"))).not.toContain("abort()");
    expect(DOCK).toContain("useDismiss(open, () => setOpen(false), dockRef)");
  });

  it("offers Stop as the way to withdraw one", () => {
    expect(DOCK).toContain("inFlight.current?.abort()");
    expect(DOCK).toContain('t("agentDock.stop")');
  });
});

describe("it stays a shortcut, not a second agent", () => {
  it("does not carry a standing link out of itself", () => {
    /* The dock used to end with a line pointing at `/agent`, so that
       papers and plugin drafts were named somewhere. It sat below the
       composer, which is where a chat puts what its reader needs to
       know about the answers -- and a reader looking for the box to
       type in found a link to somewhere else instead.

       The full page still exists and is still reachable; what came off
       is the permanent line inside the conversation. It is not
       replaced by another one: two exits at the bottom of a 380px card
       is the same crowding with different words. */
    expect(DOCK).not.toContain('<Link href="/agent">');
    expect(DOCK).not.toContain("agentDock.openFull");
    expect(en).not.toHaveProperty("agentDock.openFull");
    expect(vi).not.toHaveProperty("agentDock.openFull");
  });

  it("still refuses to be a second agent", () => {
    /* A 380px card is the wrong place to inspect what a model was
       allowed to do, and a duplicate of that surface would drift. The
       link going is not permission to grow the dock into the page. */
    expect(DOCK).not.toContain('type="file"');
  });
});

describe("the analyst reads like a chat", () => {
  /* The dock had the analyst render inside the scrolling log, its
     question box the last thing in the stream. An answer is taller than
     the panel, so the box the reader was about to type in scrolled off
     the bottom the moment one arrived -- the input has to hold still
     while the conversation above it moves, which is the one thing every
     chat widget agrees on. */

  it("puts the answer in the scrolling half and the box under it", () => {
    expect(ANALYST).toContain('<div className="agent-dock-log">');
    expect(ANALYST).toContain('className="agent-dock-composer"');
    /* The composer is a **sibling** of the log, not a child. Ordering
       alone does not say that -- nested, the composer still comes
       second and still scrolls away. What says it is that the log
       closes first, so the text between the two carries the closing
       tag. */
    /* `lastIndexOf`, not `indexOf`. The early return for "no episode
       chosen" opens a log div of its own further up, and measuring from
       that one puts its closing tag inside the slice -- which made this
       assertion pass while the composer sat nested, the exact fault it
       is here to catch. Found by injecting that fault and watching
       nothing go red. */
    const opensLog = ANALYST.lastIndexOf('<div className="agent-dock-log">');
    const opensComposer = ANALYST.indexOf('className="agent-dock-composer"');
    expect(opensLog).toBeGreaterThanOrEqual(0);
    expect(opensComposer).toBeGreaterThan(opensLog);
    expect(ANALYST.slice(opensLog, opensComposer)).toContain("</div>");
  });

  it("hands the analyst both halves rather than wrapping it in one", () => {
    /* The dock wrapped `<DockAnalyst>` in a log div, which made a
       pinned composer impossible however the analyst was written. */
    expect(DOCK).toContain("<DockAnalyst runId={runId} episodeId={episodeId} />");
    /* Whitespace-insensitive: pinning the indentation between the two
       tags would go red the day the file's line endings changed, and
       would not have protected anything. */
    expect(DOCK).not.toMatch(/agent-dock-log"\s*>\s*<DockAnalyst/);
  });

  it("sends on an empty box, because empty is the measured question", () => {
    /* A send button greyed out until something is typed would hide the
       one question every quality figure for this scope describes. */
    /* The property, not the line. Pinned as "nothing about what was
       typed reaches `disabled`" so the assertion survives the button
       being reformatted, which is what broke its first version. */
    expect(ANALYST).toMatch(/disabled=\{asking\}/);
    expect(ANALYST).not.toMatch(/disabled=\{[^}]*question/);
  });

  it("hides the label with a class the stylesheet actually defines", () => {
    /* It was written as `visually-hidden`, a name this stylesheet has
       never had. A class that matches nothing hides nothing, so the
       label rendered as ordinary text and took a third of the row from
       the box beside it -- and nothing failed, because a missing class
       is not an error anywhere. Pinned as "every class the composer
       names exists" rather than as the one name, so the next invented
       one is caught too. */
    for (const className of ANALYST.matchAll(/className="([a-z0-9 -]+)"/g)) {
      for (const one of className[1].split(" ")) {
        if (one === "muted" || one === "small") continue; // utilities, defined elsewhere
        expect(CSS, `.${one} is used by the dock but defined nowhere`).toContain(`.${one}`);
      }
    }
  });

  it("sends with an icon, and still has a name for a screen reader", () => {
    /* The glyph is `aria-hidden`, so an icon-only button with no label
       is one a screen reader can only announce as "button". */
    expect(ANALYST).toContain('<Icon name="send"');
    expect(ANALYST).toContain("aria-label={asking ?");
    expect(ICON).toContain('| "send"');
  });

  it("keeps the caveat under the composer, where a chat puts it", () => {
    expect(ANALYST).toContain('className="agent-dock-note muted small"');
    expect(CSS).toContain(".agent-dock-note");
    expect(CSS).not.toContain(".agent-dock-more");
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
