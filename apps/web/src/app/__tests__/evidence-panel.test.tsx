/** The evidence panel, checked the way this repository can check UI.
 *
 * No jsdom here (see `vitest.config.ts`), so a component with a fetch in
 * an effect cannot be driven through its states. What *can* be checked
 * is everything that would still be wrong if the markup were perfect:
 * the panel is mounted where it was argued to belong, every translation
 * key it names exists in both locales, and a 409 is handled as a state
 * rather than as an error.
 *
 * The decisions themselves — which block to draw, how a verdict reads —
 * live in `lib/evidence.ts` and are tested directly there.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const PANEL = readFileSync(join(SRC, "components", "EvidencePanel.tsx"), "utf8");
const DETAIL = readFileSync(join(SRC, "app", "decisions", "[id]", "page.tsx"), "utf8");
const CLIENT = readFileSync(join(SRC, "lib", "decisions.ts"), "utf8");
const AUTH = readFileSync(join(SRC, "lib", "auth.ts"), "utf8");

describe("where the evidence sits", () => {
  it("is mounted under the gate table, after the headline that qualifies it", () => {
    // The gate table says who was eliminated where; the next thing a
    // reader should meet is what was seen while they ran, not a
    // recommendation three sections down.
    //
    // And the headline goes *between* them. `ExplanationHeader` carries
    // the caveats, and its own contract is that they sit above the
    // evidence — a qualifier below the thing it qualifies has already
    // been scrolled past. Dropping the evidence in under the gates left
    // that header three sections down: still correct, no longer doing
    // its job.
    const gates = DETAIL.indexOf("<GateTable run={run} />");
    const headline = DETAIL.indexOf("<ExplanationHeader run={run} />");
    const evidence = DETAIL.indexOf("<EvidencePanel run={run} />");
    const comparison = DETAIL.indexOf("<CandidateComparison run={run} />");
    expect(gates).toBeGreaterThan(-1);
    expect(headline).toBeGreaterThan(gates);
    expect(evidence).toBeGreaterThan(headline);
    expect(evidence).toBeLessThan(comparison);
  });
});

describe("a run with no packet", () => {
  it("reads a 409 as a state rather than as a failure", () => {
    // A run scored before the packet builder existed has no evidence.
    // Showing an error box would tell a reader something broke.
    expect(PANEL).toContain("caught.status === 409");
    expect(PANEL).toContain("evidence.unavailable");
  });

  it("catches the error type `authFetch` actually throws", () => {
    // The first version checked `ApiError`, which `authFetch` never
    // throws — so every 409 fell through to the red box while this
    // file's other assertion (the string `caught.status === 409` is
    // present) passed happily. Checking the source for a substring
    // proves the substring, not the behaviour.
    expect(PANEL).toContain("caught instanceof FieldError");
    expect(PANEL).not.toContain("instanceof ApiError");
    expect(AUTH).toContain("throw new FieldError(message, details, raw, response.status)");
  });

  it("carries the status on the error rather than leaving it in the message", () => {
    // Same rule as a checker's failure code: a state is told apart from
    // a fault by a number, not by matching prose that changes whenever
    // somebody improves a sentence.
    expect(AUTH).toMatch(/public status: number/);
  });

  it("keeps the two ways of having no decomposition apart", () => {
    // "This run ranked nobody" and "the panel plan withholds it" are
    // different sentences, and the component picks between them.
    expect(PANEL).toContain("evidence.noComparison");
    expect(PANEL).toContain("evidence.comparisonWithheld");
  });
});

describe("what the panel promises", () => {
  it("says out loud that nothing here is a conclusion", () => {
    // No analyst has passed the gate, so the packet carries evidence
    // and no claims. The badge is what stops a reader supplying the
    // inference silently.
    expect(PANEL).toContain("evidence.noClaimsYet");
  });

  it("shows what could not be built instead of hiding a thin packet", () => {
    expect(PANEL).toContain("evidence.omissions.title");
    expect(PANEL).toContain("evidence.gaps.title");
  });

  it("prints an interval beside every contribution", () => {
    // A bar chart without intervals invites reading the height alone.
    expect(PANEL).toContain("evidence.waterfall.ci");
    expect(PANEL).toContain("bar.ci95[0]");
  });

  it("reports sightings as a fraction, never as a percentage", () => {
    // "3%" hides that it was one episode out of thirty.
    expect(PANEL).toMatch(/episodes_seen\}\s*\/\s*\{item\.episodes_total/);
    expect(PANEL).not.toContain("episodes_seen / item.episodes_total");
  });
});

describe("translation keys", () => {
  const keys = [...PANEL.matchAll(/t\(\s*"(evidence\.[a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);
  const dynamic = [
    "supports_component_specific_attribution",
    "rules_out_component_specific_attribution",
    "interaction_not_isolated",
    "insufficient_contrast",
  ].map((verdict) => `evidence.lattice.verdict.${verdict}`);

  it("names at least the blocks this panel is made of", () => {
    expect(keys.length).toBeGreaterThan(8);
  });

  it.each([...new Set(keys)])("%s exists in both locales", (key) => {
    // A missing key renders as the key itself, which looks like a bug
    // in the data rather than in the translation file.
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });

  it.each(dynamic)("%s exists for every lattice verdict", (key) => {
    // Composed at runtime from the verdict, so no static scan would
    // catch a missing one.
    expect(en).toHaveProperty(key);
    expect(vi).toHaveProperty(key);
  });
});

describe("the client", () => {
  it("asks the route that serves a packet built during scoring", () => {
    expect(CLIENT).toContain("/decisions/${runId}/explanation");
  });

  it("types the decomposition as nullable, because a run may rank nobody", () => {
    expect(CLIENT).toMatch(/waterfall: PacketWaterfall \| null/);
  });
});
