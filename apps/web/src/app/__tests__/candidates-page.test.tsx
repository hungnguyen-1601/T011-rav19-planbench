/** The Candidates page, and the gap it closes.
 *
 * Until it existed, naming a candidate meant typing `astar+dwa` and
 * `dwa_coarse` into two free-text boxes: no list of what there was to
 * choose from, no sign that one registry entry is a reference
 * implementation nobody should compare against, and no sign of a typo
 * until the server refused it after the click.
 *
 * Source-level, matching the other page tests: the page sits behind an
 * effect and three fetches, so a first paint would only show a loading
 * state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { NAV_SECTIONS } from "../../lib/navigation";

const APP = join(process.cwd(), "src", "app");
const PAGE = readFileSync(join(APP, "candidates", "page.tsx"), "utf8");
const LAUNCH = readFileSync(join(APP, "decisions", "page.tsx"), "utf8");
const CLIENT = readFileSync(join(process.cwd(), "src", "lib", "decisions.ts"), "utf8");
/* The picker is shared by both pages, so the claims about *choosing*
   a candidate live with it — same assertions, the file they read
   follows the code. */
const PICKER = readFileSync(
  join(process.cwd(), "src", "components", "CandidatePicker.tsx"),
  "utf8",
);
/* The paper reader moved out of this page and into a component, so it
   could also be mounted on the assistant page — which is where somebody
   looking for "the AI reads my document" actually goes. The claims about
   it follow the code. */
const PAPER = readFileSync(
  join(process.cwd(), "src", "components", "FromPaperPanel.tsx"),
  "utf8",
);
const AGENT = readFileSync(join(APP, "agent", "page.tsx"), "utf8");

describe("what there is to choose between comes from the server", () => {
  it("never hardcodes the stacks or the controller configurations", () => {
    /* Registration already refuses anything outside these tables, so a
       list in the browser would be a second statement of what the
       platform accepts — free to drift, and drifting silently until a
       dropdown offers something the server rejects. */
    expect(CLIENT).toContain('authFetch<LocalControllerConfig[]>("/local-controllers")');
    expect(PAGE).toContain('authFetch<AlgorithmInfo[]>("/algorithms")');
    expect(PAGE).not.toContain('"dwa_coarse"');
    expect(PAGE).not.toContain('"astar+dwa"');
  });

  it("shows the sampling numbers, not only the configuration names", () => {
    /* `dwa_coarse` and `dwa_default` differ by 7×15 samples against
       20×40, and that difference is the entire reason a sampling choice
       is a candidate rather than a constant inside whichever script
       ran. */
    expect(PAGE).toContain("ConfigTable");
    expect((en as Record<string, string>)["candidates.configs.note"]).toContain("7×15");
  });
});

describe("a reference stack is never offered as a candidate", () => {
  it("is filtered out of both pickers", () => {
    /* It exists to validate the pipeline and must never support a
       conclusion. Offering it would put it one click from one. */
    expect(PICKER).toContain("stacks.filter((entry) => entry.benchmarkable)");
    expect(PICKER).toContain("usableStacks");
  });

  it("is still listed, with the reason it cannot be used", () => {
    /* Hiding it entirely would leave a reader wondering why the registry
       and the picker disagree. */
    expect(PAGE).toContain("candidates.stacks.reference");
    expect((en as Record<string, string>)["candidates.stacks.referenceNote"]).toContain(
      "validate the pipeline",
    );
  });
});

describe("the id is the identity", () => {
  it("offers no id field when registering", () => {
    /* HĐ-1.3 makes candidate_id a hash over the stack, its parameters
       and its code version. A caller-supplied id would let two different
       configurations share an identity that every trace, pairing and ΔU
       keys on. */
    expect(CLIENT).toContain("registerCandidate");
    expect(CLIENT).not.toContain("candidate_id: string;\n  stack: string");
    expect((en as Record<string, string>)["candidates.register.note"]).toContain("HĐ-1.3");
    expect((en as Record<string, string>)["candidates.register.note"]).toContain("hash");
  });

  it("says that two candidates differing by one parameter are two candidates", () => {
    expect((en as Record<string, string>)["candidates.registered.idNote"]).toContain(
      "two candidates",
    );
  });
});

describe("an undeclared tuning is not a zero", () => {
  it("renders it as its own answer", () => {
    /* HĐ-1.6: the objectives layer charges an undeclared candidate for
       the silence rather than substituting nothing, so "not declared"
       has to reach the screen instead of rendering as a blank. */
    expect(PAGE).toContain("candidates.registered.undeclared");
    expect((en as Record<string, string>)["candidates.registered.silenceNote"]).toContain(
      "Not the same as zero",
    );
  });
});

describe("the launch panel stops asking people to type identifiers", () => {
  it("offers the served lists as dropdowns", () => {
    expect(LAUNCH).toContain("listLocalControllers()");
    expect(LAUNCH).toContain("<CandidatePicker");
  });

  it("falls back to free text rather than blocking a sweep", () => {
    /* Losing the ability to start a sweep because a convenience list did
       not arrive would be a worse page than the one this replaced. */
    expect(PICKER).toContain('placeholder="astar+dwa"');
    expect(PICKER).toContain("if (globals.length === 0)");
  });

  it("links to the page that explains what the names mean", () => {
    expect(LAUNCH).toContain('href="/candidates"');
    expect(en).toHaveProperty("decisions.launch.whatAreThese");
    expect(vi).toHaveProperty("decisions.launch.whatAreThese");
  });
});

describe("the page is reachable and translated", () => {
  it("sits in the sidebar as a material, not as a thing being replaced", () => {
    /* A candidate is what a comparison chooses *between* — an input, the
       same kind of thing as a map. */
    const materials = NAV_SECTIONS.find((section) => section.titleKey === "nav.section.materials");
    expect(materials?.items.map((item) => item.href)).toContain("/candidates");
  });

  it("is the only page left that shows the registry", () => {
    /* `/algorithms` was the other one. It moved here in P3 and was
       removed in P6 — regrouped first, deleted only once this page
       carried everything it did, including the observation classes it
       was the sole place to read. */
    expect(NAV_SECTIONS.flatMap((section) => section.items).map((item) => item.href)).not.toContain(
      "/algorithms",
    );
    expect(PAGE).toContain("StackTable");
    expect(PAGE).toContain("stack.global_observation_class");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set([...PAGE.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});

describe("choosing a candidate one layer at a time", () => {
  it("picks a global planner and a controller separately", () => {
    /* One dropdown of whole stacks grows as the *product* of the layers
       while the thing being chosen is one item from each. That shape is
       wrong before anybody notices it is long. */
    expect(PICKER).toContain("globalPlanners");
    expect(PICKER).toContain("controllersFor");
    expect(en).toHaveProperty("candidates.pick.global");
    expect(en).toHaveProperty("candidates.pick.local");
  });

  it("only offers controllers the registry actually pairs with that planner", () => {
    /* The registry is not a full cross product: `rrtstar+ppo` does not
       exist. Two free dropdowns would let somebody build it and find out
       from a server refusal. */
    expect(PICKER).toContain("entry.global_planner === globalPlanner");
    expect(PICKER).toContain("entry.local_controller");
  });

  it("looks the stack id up instead of assembling it from the halves", () => {
    /* Every entry today is spelled `<global>+<local>` and building the
       id would work — until an entry is not. The id is a display
       convention; `global_planner` and `local_controller` are the
       facts. */
    expect(PICKER).toContain("stackFor");
    expect(PICKER).not.toContain("`${");
  });

  it("only offers configurations belonging to the chosen controller", () => {
    /* `velocity_samples` is a DWA idea. Offering it beside a PPO policy
       would be a knob with nothing behind it. */
    expect(PICKER).toContain("config.controller === controller");
  });

  it("drops the configuration when the controller changes, keeps it when only the planner does", () => {
    /* `dwa_coarse` on a PPO policy is a name from another vocabulary.
       But "the same controller under a different planner" is exactly the
       comparison this platform is for, so that one keeps both. */
    expect(PICKER).toContain("forController.some((one) => one.name === value.local_config)");
  });

  it("says so when a controller has no named configuration yet", () => {
    /* Not an error — one nobody has written configurations for. Saying
       so is more use than an empty dropdown. */
    expect(PICKER).toContain("candidates.pick.noConfigs");
    expect(vi).toHaveProperty("candidates.pick.noConfigs");
  });
});

describe("a paper can arrive as a file, not only as a paste", () => {
  it("keeps its panel on the page where a candidate gets registered", () => {
    expect(PAGE).toContain("<FromPaperPanel");
  });

  it("offers an upload button beside the box", () => {
    /* Asking a reader to select a PDF's setup section, copy it and paste
       it is the step that stops most people from trying the feature at
       all. The paste box stays: a scanned paper no extractor can read
       still has two lines somebody can retype. */
    expect(PAPER).toContain('type="file"');
    expect(PAPER).toContain('t("paper.upload")');
    expect(PAPER).toContain('t("paper.read")');
  });

  it("filters the picker to the extensions the server can read", () => {
    /* A courtesy, not the check — the server refuses independently. */
    expect(PAPER).toContain(".pdf");
    expect(PAPER).toContain("accept={PAPER_FILE_TYPES}");
  });

  it("sends the file as multipart rather than as a JSON string", () => {
    expect(CLIENT).toContain("new FormData()");
    expect(CLIENT).toContain('"/candidates/from-paper/upload"');
  });

  it("lets the same file be picked twice", () => {
    /* A reader whose first upload failed picks the same file again, and
       an input that keeps its value fires no change event. */
    expect(PAPER).toContain("event.target.value = \"\"");
  });

  it("routes both entry points through one reader", () => {
    /* So an upload and a paste of the same paper cannot drift into
       producing different-looking drafts. */
    expect(PAPER).toContain("async function run(");
    expect(PAPER.match(/setResult\(await/g)).toHaveLength(1);
  });

  it("says the file is not kept", () => {
    /* The upload is a shortcut past the copy step, not a new place
       papers live — and the reader is entitled to know that before
       uploading something unpublished. */
    for (const locale of [en, vi]) {
      expect((locale as Record<string, string>)["paper.uploadHint"]).toBeTruthy();
    }
    expect(en["paper.uploadHint"]).toMatch(/not stored/);
  });
});

describe("the panel does not report which model answered", () => {
  it("shows no provider or model badge", () => {
    /* Which vendor served the request is a deployment fact, not
       evidence about the paper. What the reader has to check is whether
       the quoted sentences are in the paper, and a vendor string beside
       them competes for that attention. */
    expect(PAPER).not.toContain("result.provider");
    expect(PAPER).not.toContain("result.model");
    expect(PAPER).not.toContain("paper.mock");
    expect(PAPER).not.toContain("paper.live");
  });

  it("drops the strings that badge used", () => {
    for (const locale of [en, vi] as Record<string, string>[]) {
      expect(locale["paper.mock"]).toBeUndefined();
      expect(locale["paper.live"]).toBeUndefined();
    }
  });

  it("still shows what a reader must check", () => {
    /* Removing the badge must not remove the honesty: the quote behind
       every value, and the count of the ones that were invented. */
    expect(PAPER).toContain('t("paper.fromSentence")');
    expect(PAPER).toContain("result.unquoted");
  });
});

describe("every suggested question is one the tools can answer", () => {
  /* Two of them were not, and that is how the regression showed up in
     the UI: after the documentation corpus was removed, "what does gate
     G2 check?" and "how is fairness kept?" had nothing behind them. A
     suggested question the agent cannot answer is the platform inviting
     a failure and then producing it on the first click. */
  const KEYS = ["deployments", "runs", "candidates", "critique"];

  it("suggests only questions backed by a read tool", () => {
    for (const key of KEYS) {
      expect(AGENT).toContain(`agent.quick.${key}`);
    }
  });

  it("no longer suggests the two the corpus used to answer", () => {
    expect(AGENT).not.toContain("agent.quick.gates");
    expect(AGENT).not.toContain("agent.quick.contract");
    for (const locale of [en, vi] as Record<string, string>[]) {
      expect(locale["agent.quick.gates"]).toBeUndefined();
      expect(locale["agent.quick.contract"]).toBeUndefined();
    }
  });

  it("every suggestion has both translations", () => {
    for (const key of KEYS) {
      expect((en as Record<string, string>)[`agent.quick.${key}`]).toBeTruthy();
      expect((vi as Record<string, string>)[`agent.quick.${key}`]).toBeTruthy();
    }
  });

  it("stops claiming answers come from indexed documents", () => {
    /* The copy outlived the corpus by one commit and said something
       false to every reader of the empty state. */
    expect(en["agent.empty.body"]).not.toMatch(/indexed/i);
    expect(en["agent.askHint"]).not.toMatch(/indexed/i);
    expect(vi["agent.empty.body"]).not.toMatch(/index/i);
    expect((en as Record<string, string>)["agent.documentsIndexed"]).toBeUndefined();
  });
});

describe("the assistant takes a paper the way a chat client does", () => {
  /* The first attempt bolted the whole candidates panel onto the top of
     /agent: a form the size of the page sitting above a chat box. That
     is not how anybody attaches a file to a conversation. The paperclip
     belongs in the composer, the file becomes a turn, and the reading
     comes back as the reply. */

  it("puts a paperclip in the composer, not a panel above the thread", () => {
    expect(AGENT).toContain('className="chat-attach"');
    expect(AGENT).toContain('type="file"');
    expect(AGENT).not.toContain("<FromPaperPanel");
  });

  it("holds the file until send rather than reading it on pick", () => {
    /* Attaching is not asking. Reading on pick spends a model call on a
       mis-click, and gives no chance to change the file. */
    expect(AGENT).toContain("setAttached(file)");
    expect(AGENT).toContain('aria-label={t("agent.attachRemove")}');
  });

  it("shows the reading as a turn in the conversation", () => {
    expect(AGENT).toContain("paper?: PaperExtraction");
    expect(AGENT).toContain("<PaperResult result={entry.paper}");
  });

  it("renders the reading with the candidates page's own component", () => {
    /* Two renderings of one extraction would drift, and the second one
       is the one that quietly drops what the paper failed to state. */
    expect(PAPER).toContain("export function PaperResult");
    expect(AGENT).toContain('from "@/components/FromPaperPanel"');
  });

  it("still ends at a human, not at a registration", () => {
    expect(AGENT).toContain('t("agent.paperRegister")');
    expect(AGENT).toContain('href="/candidates"');
  });

  it("names the attachment strings in both languages", () => {
    for (const key of ["agent.attach", "agent.attachRemove", "agent.readPaper"]) {
      expect((en as Record<string, string>)[key]).toBeTruthy();
      expect((vi as Record<string, string>)[key]).toBeTruthy();
    }
  });
});

describe("stopping an upload actually stops it", () => {
  /* The Stop button aborts whatever `inFlight` holds. The first version
     of the upload path never put anything there, so Stop cleared the
     spinner while the request ran on — and the reading arrived minutes
     later, appended under a thread the reader had moved on from. */

  it("registers the upload in the same slot the chat path uses", () => {
    expect(AGENT).toContain("inFlight.current = controller");
    expect(AGENT.match(/inFlight\.current = controller/g)!.length).toBeGreaterThanOrEqual(2);
  });

  it("drops a result that arrived after the abort", () => {
    expect(AGENT).toContain("if (controller.signal.aborted) return false;");
  });

  it("does not surface an error the reader caused by pressing Stop", () => {
    expect(AGENT).toContain("if (!controller.signal.aborted) setError");
  });

  it("threads the signal all the way to fetch", () => {
    const CLIENT_SRC = readFileSync(join(process.cwd(), "src", "lib", "decisions.ts"), "utf8");
    expect(CLIENT_SRC).toContain("signal?: AbortSignal");
    expect(CLIENT_SRC).toContain("signal,");
  });
});

describe("the hidden file input does not steal the message box's styling", () => {
  it("excludes the file input rather than naming the text input's type", () => {
    /* The message box declares no `type`, so a rule written as
       input[type="text"] would silently stop styling it. */
    const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
    expect(CSS).toContain('.chat-composer input:not([type="file"])');
  });
});

describe("the boundaries section says something a person can read", () => {
  /* It used to be two rows of function names — `write_task_profile`,
     `declare_safe` — which tell a reader nothing and made the one claim
     worth making look like debug output. The claim is that the assistant
     cannot act. That has to be legible first and checkable second, not
     the other way round. */

  it("leads with sentences, not identifiers", () => {
    expect(AGENT).toContain('t("agent.canReadPlain")');
    expect(AGENT).toContain('t("agent.cannotPlain")');
  });

  it("names the acts a person keeps, in words", () => {
    for (const locale of [en, vi] as Record<string, string>[]) {
      expect(locale["agent.cannotPlain"]).toBeTruthy();
      expect(locale["agent.canReadPlain"]).toBeTruthy();
    }
    /* The four that matter to a reviewer: it cannot run, approve,
       declare safe, or drive. */
    expect(en["agent.cannotPlain"]).toMatch(/run a comparison/i);
    expect(en["agent.cannotPlain"]).toMatch(/approve/i);
    expect(en["agent.cannotPlain"]).toMatch(/safe/i);
    expect(en["agent.cannotPlain"]).toMatch(/robot/i);
  });

  it("keeps the raw list one level deeper, so the claim stays checkable", () => {
    /* Deleting it outright would make the guarantee unverifiable — a
       reviewer could no longer confirm the page matches the server. */
    expect(AGENT).toContain('t("agent.boundariesRaw")');
    expect(AGENT).toContain("capabilities.forbidden.map");
    expect(AGENT).toContain("capabilities.tools.map");
  });
});

describe("what an adversarial review found, and what now holds", () => {
  /* Thirteen findings survived refutation against the first version of
     the attachment. These are the ones that were real defects rather
     than preferences, each pinned so it cannot come back. */

  it("does not lock the message box when a file is attached", () => {
    /* It had `disabled={attached !== null}` and no `input:disabled`
       rule anywhere, so the box looked live while swallowing every
       keystroke. */
    expect(AGENT).not.toContain("disabled={attached !== null}");
  });

  it("sends a question typed beside the file instead of dropping it", () => {
    /* The upload endpoint takes a file and nothing else, so the question
       cannot ride along. It goes as the next turn — which is a design
       choice, where silently discarding it was a bug. */
    expect(AGENT).toContain("const question = draft.trim();");
    expect(AGENT).toContain("if (sent && question) await ask(question);");
  });

  it("keeps the attachment when the reading fails, so it can be retried", () => {
    /* `setAttached(null)` ran before the request, so a refused file —
       wrong extension, too large, a scan with no text — vanished from
       the composer and had to be found in the file dialog again. */
    const body = AGENT.slice(AGENT.indexOf("async function sendPaper"));
    const clear = body.indexOf("setAttached(null)");
    const request = body.indexOf("await extractCandidateFromPaperFile");
    expect(clear).toBeGreaterThan(request);
  });

  it("refuses an oversized file before uploading it", () => {
    /* The server could only answer once the whole file had crossed the
       wire and been spooled — minutes of upload to earn a refusal that
       `file.size` gives instantly. */
    expect(AGENT).toContain("file.size > MAX_PAPER_BYTES");
    expect(PAPER).toContain("file.size > MAX_PAPER_BYTES");
    expect(PAPER).toContain("export const MAX_PAPER_BYTES");
  });

  it("returns focus to the paperclip when the chip is removed", () => {
    /* React does not relocate focus when the focused element unmounts;
       the browser resets to <body> and the next Tab restarts at the skip
       link. */
    expect(AGENT).toContain("attachButton.current?.focus()");
  });

  it("announces the attachment to a reader who cannot see it", () => {
    expect(AGENT).toContain('role="status"');
  });

  it("clears the previous reading before attempting the next", () => {
    /* The worst of the thirteen: a failed second upload rendered the
       *previous* paper's parameter table under the new file's name,
       above a notice telling the reader to register it. */
    const body = PAPER.slice(PAPER.indexOf("async function run("));
    expect(body.slice(0, body.indexOf("await read()"))).toContain("setResult(null)");
  });

  it("says when only part of the document was read", () => {
    /* A 90k-character paper came back with a stack, quoted parameters
       and an assumptions list computed over the first two thirds — and
       rendered identically to a complete reading. */
    expect(PAPER).toContain("result.chars_total > result.chars_read");
    expect(en["paper.truncated"]).toBeTruthy();
    expect(vi["paper.truncated"]).toBeTruthy();
  });

  it("stops a paste at the limit instead of refusing it afterwards", () => {
    /* Over the limit, FastAPI answered with a validation error that the
       browser's error parser filtered down to the bare words "invalid
       request", naming neither the limit nor the field. */
    expect(PAPER).toContain("maxLength={MAX_PAPER_CHARS}");
  });

  it("uses colour tokens that exist", () => {
    /* --fg, --surface-2, --surface-3 and --danger are declared nowhere.
       Two rules that predate this change had been silently dead. */
    const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
    for (const dead of ["var(--fg)", "var(--surface-2", "var(--surface-3", "var(--danger)"]) {
      expect(CSS).not.toContain(dead);
    }
  });
});

describe("the Vietnamese UI calls a candidate a phương án", () => {
  /* "Ứng viên" is the literal translation, and in Vietnamese it means a
     job applicant or someone standing for election — an odd thing for a
     planner configuration to be. "Phương án" is what a person choosing
     between alternatives calls them, which is exactly the act this
     platform exists to support.

     "Cấu hình" was not available: it is already the word for a
     controller configuration in 27 other strings, and one candidate is
     a stack *plus* one of those. */

  it("uses no form of the old word anywhere", () => {
    for (const value of Object.values(vi as Record<string, string>)) {
      expect(value.toLowerCase()).not.toContain("ứng viên");
    }
  });

  it("does not leave the raw English word in Vietnamese prose", () => {
    for (const [key, value] of Object.entries(vi as Record<string, string>)) {
      /* `candidate_id` and `candidate_a` are field names the server
         publishes; translating those would name something that does not
         exist. */
      const prose = value.replace(/candidate_[a-z]+/g, "");
      expect(prose.toLowerCase(), key).not.toContain("candidate");
    }
  });

  it("keeps both languages on the same set of keys", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });
});
