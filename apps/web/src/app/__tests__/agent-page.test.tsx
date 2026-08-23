/** The assistant page, and the choices its shape is making.
 *
 * The page is a client component whose interesting states need a
 * session and a server, so these read the source and the stylesheet the
 * way the other page tests here do. What they lock is not "it looks like
 * this" but the handful of decisions that would be quietly undone by
 * someone tidying the file: which element the reader types into, where
 * the statement of what this thing may do is placed, and whether an
 * answer that read nothing says so as loudly as one that read four
 * sources.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AgentPage from "@/app/agent/page";
import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const PAGE = readFileSync(join(SRC, "app", "agent", "page.tsx"), "utf8");
const CSS = readFileSync(join(SRC, "app", "globals.css"), "utf8");

/** One rule's body, so a claim about it cannot be satisfied by a
 *  coincidence four hundred lines away. */
function rule(selector: string): string {
  /* Anchored to the start of a line, because `.agent-msg-body {` also
     matches the tail of `.agent-msg.user .agent-msg-body {` -- and that
     is the one rule whose whole point is to differ from the bare one. */
  const start = CSS.indexOf(`
${selector} {`);
  expect(start, `missing rule: ${selector}`).toBeGreaterThan(-1);
  return CSS.slice(start, CSS.indexOf("}", start));
}

describe("the shape is a thread with the composer at the bottom", () => {
  it("gives the page the height of the screen and scrolls only the thread", () => {
    /* Otherwise the composer sits below the last answer and walks
       further down the page with every turn, which is the one thing a
       chat layout exists to prevent. */
    expect(rule(".agent-page")).toContain("height: calc(100vh");
    expect(rule(".agent-thread")).toContain("overflow-y: auto");
    expect(rule(".agent-thread")).toContain("flex: 1");
  });

  it("caps the thread at a readable measure rather than the window", () => {
    /* A line that runs the full width of a 1440px screen is a line
       nobody finishes. */
    const inner = rule(".agent-thread-inner");
    expect(inner).toContain("max-width:");
    expect(inner).toContain("margin: 0 auto");
  });

  it("keeps the composer on the same measure as the thread", () => {
    /* A full-width composer under a centred thread reads as belonging to
       the page rather than to the conversation. */
    expect(rule(".agent-composer")).toContain("max-width:");
    expect(rule(".agent-composer")).toContain("margin: 0 auto");
  });
});

describe("a question is a bubble, an answer is not", () => {
  it("puts the reader's own words in a bubble on the right", () => {
    /* Short, theirs, and the thing they scroll back to find. */
    expect(rule(".agent-msg.user")).toContain("align-items: flex-end");
    expect(rule(".agent-msg.user .agent-msg-body")).toContain("background: var(--accent-soft)");
  });

  it("gives the answer the full column and no bubble of its own", () => {
    /* An answer here is prose, a chip row, sometimes a whole extracted
       paper. A bubble sized for a chat message folds that into a column
       too narrow to read, and the old page did exactly that. */
    expect(PAGE).not.toContain("chat-bubble");
    /* The bare rule styles every message; only the `.user` override
       paints one. An answer inherits the page. */
    expect(rule(".agent-msg")).not.toContain("background:");
    expect(rule(".agent-msg")).not.toContain("border:");
  });

  it("keeps the model's own line breaks", () => {
    /* Collapsing them turns a four-step answer into one run-on
       sentence. */
    expect(rule(".agent-msg-body")).toContain("white-space: pre-wrap");
  });

  it("names who is speaking on the answer side only", () => {
    expect(PAGE).toContain("{isUser ? null : <Who />}");
  });
});

describe("the composer takes more than one line", () => {
  it("is a textarea, not a single-line input", () => {
    /* The old box was an `<input>`, so a question with a pasted error
       message in it had to be flattened to one line before it could be
       asked. */
    expect(PAGE).toContain("<textarea");
    expect(PAGE).toContain('className="agent-input"');
  });

  it("sends on Enter and writes a line on Shift+Enter", () => {
    expect(PAGE).toContain('if (event.key === "Enter" && !event.shiftKey)');
    expect(PAGE).toContain("event.preventDefault();");
    expect(PAGE).toContain('t("agent.enterHint")');
  });

  it("grows with the text and then stops", () => {
    /* Past the cap the composer is eating the thread it belongs to. */
    expect(PAGE).toContain("const COMPOSER_MAX_HEIGHT = 200");
    expect(PAGE).toContain('box.style.height = "auto"');
    expect(PAGE).toContain("Math.min(box.scrollHeight, COMPOSER_MAX_HEIGHT)");
    expect(rule(".agent-input")).toContain("resize: none");
  });

  it("holds the attachment inside the box, above the text", () => {
    /* Beside the text it squeezes the line being typed into a slot; a
       long filename then has nowhere to wrap. */
    const composer = PAGE.slice(PAGE.indexOf('className="agent-composer"'));
    const form = composer.slice(0, composer.indexOf("</form>"));
    expect(form.indexOf('className="agent-chip"')).toBeLessThan(form.indexOf("<textarea"));
  });

  it("will not send an empty question", () => {
    expect(PAGE).toContain("const canSend = attached !== null || draft.trim().length > 0");
    expect(PAGE).toContain("disabled={!canSend}");
  });
});

describe("what the page says about an answer", () => {
  it("says an answer read nothing as loudly as it says what it read", () => {
    /* This was small grey prose under the bubble, which is where a
       disclaimer goes to be skipped. It is the most consequential thing
       the row can say: the answer came from the model's memory rather
       than from anything this platform recorded. */
    expect(PAGE).toContain('<span className="agent-tool warn">{t("agent.noTools")}</span>');
    expect(rule(".agent-tool.warn")).toContain("var(--warn)");
  });

  it("shows the tools as chips in one row", () => {
    expect(rule(".agent-evidence")).toContain("flex-wrap: wrap");
    expect(PAGE).toContain('className="agent-tool"');
  });

  it("marks a turn that ran out of tool calls", () => {
    expect(PAGE).toContain("turn.truncated");
    expect(PAGE).toContain('t("agent.truncated")');
  });

  it("copies the answer without the evidence around it", () => {
    /* What travels into a ticket is the sentences. The tool names and
       the truncation warning say how much to trust them, and that is the
       part which must not travel without the page it was read on. */
    expect(PAGE).toContain("<CopyAnswer text={entry.text} />");
    expect(PAGE).toContain("navigator.clipboard?.writeText(text)");
  });
});

describe("what it may do is said where it is read", () => {
  it("sits in the header rather than under the thread", () => {
    /* At the foot of a thread that grows, the statement of what this
       thing may do is below the fold from the second answer onward. */
    const head = PAGE.slice(PAGE.indexOf("<header"), PAGE.indexOf("</header>"));
    expect(head).toContain("<Boundaries />");
  });

  it("names the four acts a reviewer needs to know it cannot perform", () => {
    const cannot = (en as Record<string, string>)["agent.cannotPlain"];
    for (const act of ["run a comparison", "approve", "safe", "robot"]) {
      expect(cannot.toLowerCase()).toContain(act);
    }
  });

  it("says which answers came from no model at all", () => {
    expect(PAGE).toContain("capabilities?.deterministic");
    expect(PAGE).toContain('t("agent.mock")');
  });
});

describe("the empty screen is a prompt, not a blank box", () => {
  it("offers four openers", () => {
    /* A chat that opens blank asks the reader to guess what it knows. */
    expect(PAGE).toContain("<Welcome onPick=");
    expect(PAGE).toContain('className="agent-suggestion"');
    expect(PAGE.match(/"agent\.quick\.[a-z]+"/g) ?? []).toHaveLength(4);
  });

  it("stacks them on a narrow screen", () => {
    /* Two cards side by side at 360px are two cards of three words
       each. */
    const narrow = CSS.slice(CSS.indexOf("@media (max-width: 560px)", CSS.indexOf(".agent-page")));
    expect(narrow.slice(0, narrow.indexOf("\n}\n"))).toContain(
      ".agent-suggestions { grid-template-columns: minmax(0, 1fr); }",
    );
  });
});

describe("signed out, it asks for a sign-in instead of a question", () => {
  it("renders the notice rather than the composer", () => {
    /* `authFetch` answers 401, and it does that after the reader has
       already typed. */
    const html = renderToStaticMarkup(<AgentPage />);
    expect(html).toContain('href="/login"');
    expect(html).not.toContain("agent-composer");
  });
});

describe("translation", () => {
  const keys = [
    ...new Set([...PAGE.matchAll(/t\(\s*"([a-zA-Z0-9_.]+)"/g)].map((hit) => hit[1])),
    ...(PAGE.match(/"agent\.quick\.[a-z]+"/g) ?? []).map((raw) => raw.slice(1, -1)),
  ];

  it.each(keys)("%s exists in both locales", (key) => {
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });

  it("reads enough keys for that to mean something", () => {
    expect(keys.length).toBeGreaterThan(20);
  });
});
