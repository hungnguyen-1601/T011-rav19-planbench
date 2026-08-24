/** The Markdown export, and the charts that did not survive P6.
 *
 * **What retired, and why it is not an oversight.** The difficulty curve
 * and the generalization-gap chart lived on `/leaderboard` and
 * `/benchmarks/[id]`. Both are claims *across scenarios* — "this stack
 * generalises from the training split to the held-out one" — and HĐ-1.4
 * scopes a recommendation to one deployment. They retired with the flow
 * that made those claims rather than being rehomed into one that does
 * not, and their components were deleted with them so no dead code sits
 * behind a green test.
 *
 * **What survived is the export**, because handing a result to somebody
 * who will not open the platform is not a property of the old flow. The
 * mechanism — authenticated fetch, Blob, synthetic anchor, revoked
 * object URL — moved unchanged; only the document it fetches is new.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");
const REPORTS = read("lib", "reports.ts");
const DETAIL = read("app", "decisions", "[id]", "DecisionDetail.tsx");
const MARKDOWN = readFileSync(
  join(process.cwd(), "..", "api", "planbench_api", "decision_markdown.py"),
  "utf8",
);

// What an export *says* moved out of the Markdown renderer when Excel
// became a second format: one module decides every value, and the two
// renderers only decide where it sits. The assertions below are about
// content, so they read that module.
const EXPORT = readFileSync(
  join(process.cwd(), "..", "api", "planbench_api", "decision_export.py"),
  "utf8",
);
const WORKBOOK = readFileSync(
  join(process.cwd(), "..", "api", "planbench_api", "decision_xlsx.py"),
  "utf8",
);
/* The words themselves moved again when the export became bilingual: a
   document in a language the reader does not use is one whose caveats do
   not travel, which is the failure the caveats exist to prevent. The
   renderers now carry keys and this table carries the sentences, so an
   assertion about wording reads it and an assertion about placement
   still reads the renderer. */
const TEXTS = readFileSync(
  join(process.cwd(), "..", "api", "planbench_api", "decision_text.py"),
  "utf8",
);

describe("the export is a fetch, never a link", () => {
  it("sends the token in a header instead of in the URL", () => {
    /* A plain <a href> cannot send an Authorization header, so it would
       either 401 or push the token into history and into every proxy log
       on the way. */
    expect(REPORTS).toContain("Authorization: `Bearer ${session.token}`");
    expect(REPORTS).toContain("URL.createObjectURL");
  });

  it("revokes the object URL, but not before the browser has read it", () => {
    /* A Blob still referenced is held for the life of the document, so
       twenty exports would hold twenty. Revoking synchronously saves an
       empty file in some browsers. */
    expect(REPORTS).toContain("setTimeout(() => URL.revokeObjectURL(url), 0)");
  });

  it("takes a path so the mechanism outlived the flow it was written for", () => {
    // Renamed when it stopped being Markdown-only: a helper whose name
    // says Markdown while it serves .xlsx is a lie nothing ever fails on.
    expect(REPORTS).toContain("downloadReport(path: string, fallbackName: string)");
    // The old name may still be named in a comment explaining the
    // rename; what must be gone is the function.
    expect(REPORTS).not.toContain("function downloadReportMarkdown");
    expect(REPORTS).toContain("export function downloadDecisionReport(");
  });
});

describe("every run can be exported, not only the ranked ones", () => {
  it("offers the button regardless of whether a card came out", () => {
    /* Most runs produce no card — fewer than two candidates through the
       gates means no ΔU (HĐ-7). A button that appeared only on ranked
       runs would make the ordinary outcome the one nobody can put in a
       ticket. */
    expect(DETAIL).toContain("<ExportReport");
    const button = DETAIL.slice(
      DETAIL.indexOf("function ExportReport"),
      DETAIL.indexOf("function ObservationNotice"),
    );
    expect(button).not.toContain("run.ranked");
    expect(button).not.toContain("config_state");
  });

  it("renders the no-card case as a section rather than refusing", () => {
    expect(TEXTS).toContain('"en": "No Decision Card"');
    expect(MARKDOWN).toContain("heading.no_card");
    expect(EXPORT).toContain("gate_only_deployment");
    // And the workbook too — a run that ranked nobody is the
    // ordinary outcome, so it must not be the one that cannot be
    // handed to a reviewer in either format.
    expect(WORKBOOK).toContain("heading.no_card");
    // In both languages, because the reader who cannot be handed it is
    // the same reader either way.
    expect(TEXTS).toContain('"vi": "Không có Thẻ quyết định"');
  });
});

describe("the document keeps the caveats attached to the numbers", () => {
  it("spells out null as 'not measured'", () => {
    /* HĐ-12 defines null that way, and a blank cell in a Markdown table
       reads as reassurance — worse on paper than on screen, because the
       reader cannot ask. */
    expect(TEXTS).toContain('"value.not_measured": {"en": "not measured"');
    expect(EXPORT).toContain('NOT_MEASURED = text("value.not_measured")');
    // Sharper in a spreadsheet: a blank cell sorts to the top, sums
    // as zero, and averages as though it had been measured.
    expect(WORKBOOK).toContain("never as a blank");
    expect(TEXTS).toContain("None of the sensitivity margins were measured");
  });

  it("carries the recommendation's scope with the recommendation", () => {
    expect(TEXTS).toContain("HĐ-1.4");
    expect(TEXTS).toContain("and to nothing else");
    // Both renderers reach for it, so neither format can be the one
    // that arrives without the limit.
    expect(MARKDOWN).toContain("prose.scope");
    expect(WORKBOOK).toContain("prose.scope_sheet");
  });

  it("names every candidate retired early, with the sample it actually got", () => {
    expect(EXPORT).toContain("def retired_candidates(");
    expect(TEXTS).toContain("rest on fewer episodes");
    expect(MARKDOWN).toContain("prose.retired");
  });

  it("puts the gates before the card", () => {
    expect(MARKDOWN.indexOf("_gates(report, locale)")).toBeLessThan(
      MARKDOWN.indexOf("_card(run, report, locale)"),
    );
  });

  it("keeps an unpinned measurement host in the document", () => {
    /* Unpinned, every latency number measures this machine as much as
       the candidate. */
    expect(TEXTS).toContain("Measurement environment");
    expect(MARKDOWN).toContain("heading.measurement_environment");
  });
});

describe("the button is translated in both languages", () => {
  it("has its keys", () => {
    for (const key of ["decisions.export.markdown", "decisions.export.busy"]) {
      expect(en, `en missing ${key}`).toHaveProperty(key);
      expect(vi, `vi missing ${key}`).toHaveProperty(key);
    }
  });
});
