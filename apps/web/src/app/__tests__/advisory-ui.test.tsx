/** The advisory layer's UI: five features, one shape, no dead ends.
 *
 * Source-level, like the other page tests: every claim here is about
 * what the code wires, not about pixels. The claims that matter:
 * each advisory endpoint has a surface a user can reach, both halves of
 * every advice item are rendered (`do` and `do_not`), the plugin
 * verdict shown is the validator's, and the model layer's honesty
 * fields (fabricated, refused) reach the screen.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const APP = join(process.cwd(), "src", "app");
const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");

const LAUNCH = read("app", "decisions", "page.tsx");
const DETAIL = readFileSync(join(APP, "decisions", "[id]", "page.tsx"), "utf8");
const AGENT = read("app", "agent", "page.tsx");
const PAPER = read("components", "FromPaperPanel.tsx");
const ADVICE_VIEW = read("components", "AdviceListView.tsx");
const PLUGIN_VIEW = read("components", "PluginDraftView.tsx");
const CLIENT = read("lib", "decisions.ts");

describe("every advisory endpoint has a surface a user can reach", () => {
  it("pre-flight is a button on the launch panel, sending the launch body", () => {
    expect(LAUNCH).toContain("preflightDecision");
    expect(LAUNCH).toContain('t("preflight.check")');
    /* The same body as the launch — never a paraphrase. */
    expect(LAUNCH).toContain("candidates: [first, second]");
  });

  it("gate advice and report advice are panels on the run page", () => {
    expect(DETAIL).toContain("getDecisionAdvice");
    expect(DETAIL).toContain("getReportAdvice");
    expect(DETAIL).toContain("<AdvicePanel");
    expect(DETAIL).toContain("<ReportAdvicePanel");
  });

  it("the model layer is opt-in, beside the rules, never instead of them", () => {
    expect(DETAIL).toContain('t("advice.askModel")');
    expect(CLIENT).toContain("use_model=true");
  });

  it("plugin drafting is reachable from both paper flows", () => {
    expect(PAPER).toContain("draftPluginFromPaper");
    expect(AGENT).toContain("draftPluginFromPaperFile");
  });
});

describe("both halves of every advice item are rendered", () => {
  it("shows do and do_not, with do_not present whenever set", () => {
    expect(ADVICE_VIEW).toContain('t("advice.do")');
    expect(ADVICE_VIEW).toContain('t("advice.doNot")');
    expect(ADVICE_VIEW).toContain("item.do_not");
  });

  it("distinguishes the model's additions from the rules'", () => {
    expect(ADVICE_VIEW).toContain('item.source === "model"');
  });

  it("shows the honesty counters, not only the advice", () => {
    /* `fabricated` is how a reader tells a model that added judgement
       from one that added noise; hiding it would erase the difference. */
    expect(ADVICE_VIEW).toContain("result.fabricated");
    expect(ADVICE_VIEW).toContain("result.refused");
  });

  it("says how many rules ran, so silence reads as a result", () => {
    expect(ADVICE_VIEW).toContain("result.rules_applied");
    expect(ADVICE_VIEW).toContain('t("advice.clean")');
  });
});

describe("the plugin verdict on screen is the validator's", () => {
  it("renders accepted or rejected from the accepted flag", () => {
    expect(PLUGIN_VIEW).toContain("draft.accepted");
    expect(PLUGIN_VIEW).toContain('t("plugin.accepted")');
    expect(PLUGIN_VIEW).toContain('t("plugin.rejected")');
  });

  it("names the errors instead of hiding a rejected draft", () => {
    expect(PLUGIN_VIEW).toContain("draft.errors.map");
    expect(PLUGIN_VIEW).toContain("draft.files");
  });

  it("says nothing is stored or executed", () => {
    expect(PLUGIN_VIEW).toContain('t("plugin.hint")');
    for (const locale of [en, vi] as Record<string, string>[]) {
      expect(locale["plugin.hint"]).toBeTruthy();
    }
  });
});

describe("the paper flows keep the source the plugin path needs", () => {
  it("the panel remembers the last file or text it read", () => {
    /* The platform stores no paper; forgetting the source would turn
       "draft a plugin from that paper" into a trip back to the file
       dialog. */
    expect(PAPER).toContain("setLastSource({ file })");
    expect(PAPER).toContain("setLastSource({ text })");
  });

  it("the chat keeps the last paper sent", () => {
    expect(AGENT).toContain("setLastPaper(file)");
  });

  it("a new read clears the previous plugin draft", () => {
    expect(PAPER).toContain("setPlugin(null)");
  });

  it("the no-stack case is called out as the plugin's reason to exist", () => {
    expect(PAPER).toContain('t("plugin.newMethod")');
    expect(AGENT).toContain('t("plugin.buildNoStack")');
  });
});

describe("the strings exist in both languages", () => {
  it.each(["advice.do", "advice.doNot", "advice.fabricated", "preflight.check", "plugin.build", "plugin.rejected", "reportAdvice.title"])(
    "%s",
    (key) => {
      expect((en as Record<string, string>)[key]).toBeTruthy();
      expect((vi as Record<string, string>)[key]).toBeTruthy();
    },
  );
});

describe("the outcome panel explains wins and losses", () => {
  it("is a panel on the run page with the model opt-in beside the rules", () => {
    expect(DETAIL).toContain("getOutcomeAdvice");
    expect(DETAIL).toContain("<OutcomePanel");
  });

  it("names the feature in both languages", () => {
    expect((en as Record<string, string>)["outcome.title"]).toBeTruthy();
    expect((vi as Record<string, string>)["outcome.title"]).toBeTruthy();
  });
});
