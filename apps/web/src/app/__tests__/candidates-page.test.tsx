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
    expect(PAGE).toContain("stacks.filter((entry) => entry.benchmarkable)");
    expect(LAUNCH).toContain("stacks.filter((entry) => entry.benchmarkable)");
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
    expect(LAUNCH).toContain("configs.length > 0 ?");
  });

  it("falls back to free text rather than blocking a sweep", () => {
    /* Losing the ability to start a sweep because a convenience list did
       not arrive would be a worse page than the one this replaced. */
    expect(LAUNCH).toContain('placeholder="astar+dwa"');
    expect(LAUNCH).toContain("// Free-text inputs remain; nothing to say.");
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

  it("moved /algorithms into the group being replaced", () => {
    /* It was the only way to see the registry; now this page shows it
       with the configurations and the registered candidates beside it. */
    const retiring = NAV_SECTIONS.find((section) => section.titleKey === "nav.section.retiring");
    expect(retiring?.items.map((item) => item.href)).toContain("/algorithms");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set([...PAGE.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});
