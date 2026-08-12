/** The `/deployments` page — where noise lives, and where it does not.
 *
 * The thing this page has to teach, and the reason it is a page rather
 * than a field on the run form: **noise belongs to the deployment, not
 * to a run.** `episode_context_id` hashes
 * `(task_profile_id, mission_id, environment_variant, seed)` and HĐ-3.1
 * freezes that payload — the amplitudes are *not* in it. So two runs at
 * the same seeds under different sigma produce contexts that hash
 * identically while being two different experiments, and the only thing
 * standing between those two worlds is the deployment id.
 *
 * A "noise" dropdown on a run form would break that quietly, which is
 * why there is no such dropdown anywhere and why this file checks the
 * page says so out loud.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { NAV_SECTIONS } from "../../lib/navigation";

const APP = join(process.cwd(), "src", "app");
const PAGE = readFileSync(join(APP, "deployments", "page.tsx"), "utf8");
const DECISIONS = readFileSync(join(APP, "decisions", "page.tsx"), "utf8");

describe("noise is a property of the deployment", () => {
  it("says so on the page rather than leaving it to be discovered", () => {
    expect(PAGE).toContain("deployments.noiseNote");
    const note = (en as Record<string, string>)["deployments.noiseNote"];
    expect(note).toContain("HĐ-3.1");
    expect(note).toContain("new id");
  });

  it("is never offered as a per-run choice", () => {
    /* The trap this closes: a sigma picker on the run form would produce
       two experiments whose episode context ids are identical. */
    expect(DECISIONS).not.toContain("sensor_noise");
    expect(DECISIONS.toLowerCase()).not.toContain("noise");
  });

  it("distinguishes 'no noise block' from 'noise set to zero'", () => {
    /* A profile with no `sensor_noise` was measured in a world with no
       noise at all. Rendering "0.00 m" for it would report a
       measurement nobody made — the warehouse profile is exactly this
       case. */
    expect(PAGE).toContain("noise !== undefined && noise !== null");
    expect(PAGE).toContain("deployments.noNoise");
    expect(en).toHaveProperty("deployments.noiseUndeclared");
    expect(vi).toHaveProperty("deployments.noiseUndeclared");
  });
});

describe("filing a deployment", () => {
  it("takes the YAML whole instead of rebuilding it as a form", () => {
    /* The profile is a contract document with a validator that already
       refuses the interesting mistakes. A form would either duplicate
       that validation or let somebody assemble a profile the server
       rejects one field at a time. */
    expect(PAGE).toContain("createTaskProfile");
    expect(PAGE).toContain("textarea");
  });

  it("parses only to build the request body, and validates nowhere", () => {
    /* `TaskProfile` is the single definition of HĐ-2 (§16). A second
       opinion in the browser would be free to disagree with the one that
       decides. */
    expect(PAGE).toContain('await import("yaml")');
    expect(PAGE).not.toContain("success_rate_min <");
    expect(PAGE).not.toContain("if (!parsed.id)");
  });

  it("warns that re-filing an id is refused rather than merged", () => {
    /* Re-filing a changed deployment under an old id would make every
       stored run describe a world that no longer exists. */
    expect(PAGE).toContain("deployments.file.idRule");
    expect((en as Record<string, string>)["deployments.file.idRule"]).toContain("refused");
  });

  it("shows the server's own refusal instead of a generic message", () => {
    expect(PAGE).toContain("caught instanceof Error ? caught.message : String(caught)");
  });
});

describe("what the table puts in front of the reader", () => {
  it("shows the thresholds that decide gate verdicts", () => {
    expect(PAGE).toContain("success_rate_min");
    expect(PAGE).toContain("collision_probability_max");
  });

  it("explains that the episode count follows the declared risk", () => {
    /* HĐ-7.1's arrow runs one way: risk decides N_min. Reading it
       backwards — picking an episode count and inferring a risk — is the
       drift the contract names. */
    expect(PAGE).toContain("deployments.nMinNote");
    const note = (en as Record<string, string>)["deployments.nMinNote"];
    expect(note).toContain("one way");
  });
});

describe("the page is reachable and translated", () => {
  it("has a sidebar entry", () => {
    const hrefs = NAV_SECTIONS.flatMap((section) => section.items).map((item) => item.href);
    expect(hrefs).toContain("/deployments");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set([...PAGE.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});
