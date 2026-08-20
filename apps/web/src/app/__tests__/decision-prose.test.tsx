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

const SRC = join(process.cwd(), "src");
const read = (...parts: string[]) => readFileSync(join(SRC, ...parts), "utf8");

const DETAIL = read("app", "decisions", "[id]", "page.tsx");
const LIST = read("app", "decisions", "page.tsx");
const PREVIEW = read("components", "DecisionDeploymentPreview.tsx");
const RUNNING = read("components", "RunningComparison.tsx");
const EVIDENCE = read("components", "EvidencePanel.tsx");

/** Every standing explanation, and the file that now hints it. */
const HINTED: [string, string][] = [
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
