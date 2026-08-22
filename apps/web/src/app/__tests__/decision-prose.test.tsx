/** What the decision tab says out loud, and what it keeps behind a mark.
 *
 * The tab had grown a paragraph under every heading — six gates, one
 * Parquet file per episode, counting is not ranking — and together they
 * took more room than the tables they introduced. A panel that is
 * mostly prose is one nobody reads, so the explanations crowded out the
 * numbers they were explaining.
 *
 * They are not deleted: each is now the accessible name of a `?` beside
 * the heading it belongs to, so a screen reader, a keyboard user and a
 * text search all still reach it.
 *
 * **The line this file defends is which sentences may move.** A
 * standing explanation of a section is background and can wait to be
 * asked for. A message that appears only in one state — this run was
 * cut short, these candidates were shown different things, the
 * detectors found nothing — is a *finding*, and a finding behind a mark
 * nobody points at is a finding nobody reads.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { GATES } from "@/lib/decisions";

const SRC = join(process.cwd(), "src");
const read = (...parts: string[]) => readFileSync(join(SRC, ...parts), "utf8");

const DETAIL = read("app", "decisions", "[id]", "page.tsx");
const LIST = read("app", "decisions", "page.tsx");
const PREVIEW = read("components", "DecisionDeploymentPreview.tsx");
const RUNNING = read("components", "RunningComparison.tsx");
const EVIDENCE = read("components", "EvidencePanel.tsx");

/** Every standing explanation, and the file that now hints it. */
const HINTED: [string, string][] = [
  // Moved with the gates themselves: the standalone table is gone,
  // so the sentence explaining what the six are now sits on the
  // gate list inside each candidate card.
  ["decisions.gates.note", DETAIL],
  ["trace.note", DETAIL],
  ["trace.colourNote", DETAIL],
  ["decisions.card.scopeNote", DETAIL],
  ["decisions.tally.note", LIST],
  ["decisions.filter.note", LIST],
  ["decisions.launch.note", LIST],
  ["decisions.map.note", LIST],
  ["decisions.preview.sharedNotice", PREVIEW],
];

describe("standing explanations sit behind a mark", () => {
  it.each(HINTED)("%s is reached through a hint", (key, source) => {
    expect(source).toContain(`<Hint text={t("${key}"`);
  });

  it.each(HINTED)("%s is no longer a paragraph of its own", (key, source) => {
    // The shape that made the tab unreadable. Matching the render, not
    // the key, so re-adding the text under a new class still trips it.
    expect(source).not.toMatch(new RegExp(`<p[^>]*>\\s*\\{t\\("${key.replace(/\./g, "\\.")}"`));
  });

  it.each(HINTED)("%s still exists in both locales", (key) => {
    // Hidden, not deleted: the mark's accessible name is this string.
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});

describe("findings stay on the page", () => {
  // Each of these appears only in one state, and each is the answer to
  // "why does this look wrong". Behind a mark they would be invisible
  // to the only reader who needed them.
  const VISIBLE: [string, string][] = [
    ["evidence.sightings.clean", EVIDENCE],
    ["evidence.sightings.none", EVIDENCE],
    ["evidence.noComparison", EVIDENCE],
    ["evidence.unavailable", EVIDENCE],
    ["decisions.launch.oneAtATime", LIST],
  ];

  it.each(VISIBLE)("%s is rendered as text, not hidden", (key, source) => {
    // The key, not a `t("...")` call: several of these are chosen by a
    // ternary *inside* the call, and a call-shaped pattern would report
    // a message that had been hidden as still visible.
    expect(source).toContain(`"${key}"`);
    expect(source).not.toContain(`<Hint text={t("${key}")`);
  });

  it("keeps the mixed-observation warning beside the gate table", () => {
    expect(DETAIL).toContain("<ObservationNotice candidates={candidates} />");
  });
});

describe("what was dropped rather than hidden", () => {
  it("no longer tells the reader to pick an episode", () => {
    // The selector is directly below with its own label, so the
    // sentence was an instruction for a control already asking for
    // itself. A hint would have been a `?` explaining nothing.
    expect(DETAIL).not.toContain("trace.pickEpisode");
    expect(en).not.toHaveProperty("trace.pickEpisode");
    expect(vi).not.toHaveProperty("trace.pickEpisode");
  });
});

describe("the one caveat that keeps a visible stub", () => {
  it("still says 'not ΔU' on the page", () => {
    // Everything else about the composite moved behind the mark. Not
    // this: it is the one number here a reader will otherwise take for
    // ΔU, and a warning that has to be pointed at is a warning missed
    // by exactly the reader who needed it.
    expect(RUNNING).toContain('t("running.composite.short")');
    expect(RUNNING).toContain("compositeCaveat(point)");
    expect(en).toHaveProperty("running.composite.short");
    expect(vi).toHaveProperty("running.composite.short");
  });
});

describe("what each gate blocks", () => {
  // A column headed "G4" with a red cell under it says a candidate was
  // eliminated and not by what — and the six are not interchangeable.
  // G1 and G3 both count failures, but for different jobs on different
  // layers of the stack; G5 and G6 can exclude a candidate that was
  // never driven at all.

  it("marks every gate on the card that lists them", () => {
    // One list now, not two: the standalone gate table was the same
    // six verdicts a second time.
    expect(DETAIL.match(/decisions\.gates\.blocks\.\$\{gate\}/g)).toHaveLength(1);
  });

  it.each([...GATES])("%s has an explanation in both locales", (gate) => {
    // Composed at runtime from the gate id, so no scan of the source
    // would catch a missing one — the mark would render with the key
    // as its own text and read as broken data.
    const key = `decisions.gates.blocks.${gate}`;
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });

  it.each([...GATES])("%s says what it blocks, not what it measures", (gate) => {
    // The distinction the user asked for. "p99 latency" names a
    // quantity; "blocks a planner that misses control deadlines" names
    // the elimination, which is what a reader looking at a red cell
    // wants.
    const text = (en as Record<string, string>)[`decisions.gates.blocks.${gate}`];
    expect(text.toLowerCase()).toContain("blocks");
    expect(text.length).toBeGreaterThan(60);
  });
});

describe("where the conclusion and the exports sit", () => {
  it("puts the marks after the evidence that justifies them", () => {
    const evidence = DETAIL.indexOf("<EvidencePanel run={run} />");
    const conclusion = DETAIL.indexOf("<ConclusionPanel run={run} />");
    expect(evidence).toBeGreaterThan(-1);
    expect(conclusion).toBeGreaterThan(evidence);
  });

  it("puts the export buttons beside the conclusion, in the head", () => {
    // **This asserted the opposite, and the argument for it was sound
    // at the time.** The buttons had been in the head, and were moved
    // below the marks so that a reader could not be invited to send a
    // run on before reading what it concluded.
    //
    // The reorder dissolved that: what the run concluded is now the
    // first panel on the page, directly under this head. "After the
    // marks" and "in the head" used to be opposite ends of six screens
    // and are now one glance apart, while the old position had costs
    // the new one does not — the buttons carried no heading of their
    // own and floated between two panels, so a reader who arrived to
    // export something scrolled past the whole argument to find them.
    const summary = DETAIL.indexOf("<DecisionSummary run={run} />");
    const exportButtons = DETAIL.indexOf("<ExportReport run={run} />");
    expect(exportButtons).toBeGreaterThan(-1);
    expect(exportButtons).toBeLessThan(summary);
    // In the head's own badge row, not loose above the page.
    const badges = DETAIL.indexOf("decision-detail-badges");
    expect(badges).toBeGreaterThan(-1);
    expect(badges).toBeLessThan(exportButtons);
    // And still only one of them: two export controls on one page is
    // two ways to do one thing.
    expect([...DETAIL.matchAll(/<ExportReport /g)]).toHaveLength(1);
  });

  it("never takes the headline from the top of the ranking", () => {
    // HĐ-10.1 refuses a Pareto-dominated candidate even when it leads
    // on utility, so the winner comes from the card.
    const panel = readFileSync(join(SRC, "components", "ConclusionPanel.tsx"), "utf8");
    expect(panel).toContain("verdictOf(run)");
    expect(panel).not.toContain("eligible[0].label");
  });

  it("keeps the two groups from being ranked against each other", () => {
    const panel = readFileSync(join(SRC, "components", "ConclusionPanel.tsx"), "utf8");
    expect(panel).toContain("const { eligible, blocked } = standings(candidates)");
    expect(panel).toContain("is-separated");
  });

  it("names a config in the headline, because a stack names both candidates", () => {
    /* Both sides of a local-controller comparison run `astar+dwa`, so
       "Use astar+dwa" is true of the winner and of the candidate it
       beat. The sentence has to carry `local_controller_config`. */
    const panel = readFileSync(join(SRC, "components", "ConclusionPanel.tsx"), "utf8");
    expect(panel).toContain("winner.local_controller_config");
    expect(panel).toContain("conclusion.headline.use\", { stack: winnerLabel }");
  });

  it("does not fold the config into the label the rows already print", () => {
    /* `Standing.label` is rendered beside `<code>{standing.config}</code>`
       and is the accessible name of the score bar. Composing the config
       into it would print it twice in one row and reword the bar with
       it, so the headline composes its own string instead. */
    const panel = readFileSync(join(SRC, "components", "ConclusionPanel.tsx"), "utf8");
    expect(panel).toContain("{standing.label} <code>{standing.config}</code>");
    const conclusion = readFileSync(join(SRC, "lib", "conclusion.ts"), "utf8");
    expect(conclusion).not.toContain("local_controller_config}`");
  });

  it("resolves the recommended candidate through one shared lookup", () => {
    /* Four surfaces name the recommendation. Three of them are on the
       detail page, and three separate `candidates.find(...)` calls are
       how they start disagreeing about who won. */
    expect(DETAIL).not.toContain("card.recommended.stack}");
    /* Four surfaces named it when this was written and the share
       dialog's covering note makes five. The number is not the claim —
       every one of them going through the same function is — so what
       this pins is that nothing on the page derives the label for
       itself. */
    expect((DETAIL.match(/recommendedCandidateLabel\(run\)/g) ?? []).length).toBeGreaterThan(1);
    expect(DETAIL).not.toMatch(/candidates[?.]*\.find\([^)]*candidate_id/);
  });
});
