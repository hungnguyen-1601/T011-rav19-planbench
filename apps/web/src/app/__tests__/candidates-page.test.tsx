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
