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
const FORM = readFileSync(join(process.cwd(), "src", "components", "DeploymentForm.tsx"), "utf8");
const LIB = readFileSync(join(process.cwd(), "src", "lib", "deployments.ts"), "utf8");

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
  it("offers a form and a paste box, and files both the same way", () => {
    /* This page used to argue that a form was the wrong shape, because
       a form would either duplicate the contract's validator or let
       somebody assemble a profile the server rejects one field at a
       time. The argument was right about *those* forms. The one here
       answers both halves: it validates nothing, and it builds the same
       document the paste box does — so there is still one definition of
       a deployment and one endpoint that files it.
       The paste box stays, and not only for old habits: it is the only
       way to write a block the form cannot express. */
    expect(PAGE).toContain("createTaskProfile");
    expect(PAGE).toContain("textarea");
    expect(PAGE).toContain("<DeploymentForm");
    expect(PAGE).toContain("const file = async (profile: ProfileDraft)");
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

describe("the form is an input method, not a second definition", () => {
  it("takes its defaults from the shipped profile rather than a copy", () => {
    /* A hand-copied set of numbers in TypeScript would be a second
       statement of what a working deployment looks like, and the day
       somebody tunes open_hall_v2 the form would keep handing out the
       old ones. */
    expect(FORM).toContain("getProfileTemplate()");
    expect(LIB).toContain('authFetch<ProfileDraft>("/task-profiles/template")');
    expect(FORM).not.toContain("success_rate_min: 0.95");
  });

  it("writes no contract rule of its own", () => {
    /* `TaskProfile` decides. The two computations here are displays of a
       consequence — the episode count a risk implies, and what the RAM
       breakdown leaves — and neither is sent anywhere. */
    for (const forbidden of ["throw new Error(", "if (radius <", "Math.PI)"]) {
      expect(FORM).not.toContain(forbidden);
    }
    expect(LIB).toContain("never travels");
  });

  it("puts the consequence beside the number that causes it", () => {
    /* The risk decides the episode count (HĐ-7.1) and the success
       threshold decides whether the deployment can rank at all
       (HĐ-8.4). Both live in YAML comments today, read after the choice
       rather than during it. */
    expect(FORM).toContain("nMinFor(risk)");
    expect(FORM).toContain("ramLeftOver(draft)");
    expect((en as Record<string, string>)["deployments.form.riskNote"]).toContain("{n}");
    expect((en as Record<string, string>)["deployments.form.successMinNote"]).toContain("HĐ-8.4");
  });

  it("addresses a refusal to the field it is about", () => {
    /* One blob saying "2 validation errors for TaskProfile" leaves the
       reader to find which two among thirty inputs. */
    expect(PAGE).toContain("fieldErrorsOf(caught)");
    expect(FORM).toContain("errorFor(path)");
  });

  it("says out loud that it writes no moving traffic", () => {
    /* With no traffic *and* no noise a deterministic planner replays one
       episode per seed, and G2's bound would rest on a sample of one.
       Legal, and the profile schema does not forbid it — so the form
       says it rather than refusing. */
    const note = (en as Record<string, string>)["deployments.form.noiseNote"];
    expect(note).toContain("traffic");
    expect(note).toContain("one episode per seed");
    expect((vi as Record<string, string>)["deployments.form.noiseNote"]).toContain("traffic");
  });

  it("carries the form's draft into the YAML tab but not back", () => {
    /* Forward, so the reader can see what the form built and hand-edit
       a block it does not cover. Not back, because loading a pasted
       document into a form that cannot express `dynamic_obstacles`
       would swallow that block silently. */
    expect(PAGE).toContain('if (next === "yaml" && formDraft)');
    expect(PAGE).toContain("stringify(formDraft)");
    expect((en as Record<string, string>)["deployments.mode.note"]).toContain("not carry it home");
  });

  it("opens on a map with a mission somebody already drove", () => {
    /* `static_obstacles` brings its own start and goal — a pair the
       author of the scenario chose and knows is drivable. Inventing one
       from the map's size would be guessing at a question that was
       already answered. */
    expect(LIB).toContain('DEFAULT_LIBRARY_SCENARIO = "static_obstacles"');
    expect(FORM).toContain("importLibraryScenario(libraryName)");
    expect(LIB).toContain("if (!scenario) return fallbackPoses(map)");
  });

  it("resets the poses whenever the map changes", () => {
    /* A coordinate means something else on another map — and it might
       still land on free floor, so nothing downstream would catch it. */
    expect(FORM).toContain("const poses = posesFor(data, scenario)");
    expect(FORM).toContain("setStart(poses.start)");
  });

  it("turns the chosen map into the two paths a profile names", () => {
    /* The same pair somebody would have typed, so the form's document
       and a pasted one are the same document. */
    expect(FORM).toContain("materialiseMap(mapId)");
    expect(FORM).toContain('"environment.map"');
    expect(FORM).toContain('"environment.map_yaml"');
  });

  it("draws and places through the shared components", () => {
    expect(FORM).toContain("<MapPainter");
    expect(FORM).toContain("<MissionPlacer");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set([...FORM.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
    for (const source of ["library", "stored", "drawn"]) {
      expect(en).toHaveProperty(`deployments.form.source.${source}`);
      expect(vi).toHaveProperty(`deployments.form.source.${source}`);
    }
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

describe("the noise a new deployment starts with", () => {
  it("arrives switched on rather than at zero", () => {
    /* A simulator with no noise is more optimistic than reality, and
       this project has already paid for that once: a Decision Card
       bounded a collision probability off a single episode replayed a
       hundred times, because nothing varied between seeds. Starting a
       new deployment at zero makes that the easy path again. */
    expect(FORM).toContain("NOISE_DEFAULTS");
    expect(FORM).toContain("withNoiseDefaults(template)");
  });

  it("is a form default and NOT a schema default", () => {
    /* The shipped profiles do not declare these fields, so a non-zero
       schema default would change the world underneath open_hall_v2 and
       warehouse_a_v2 *without changing their task_profile_id* — every
       stored trace, gate verdict and card would silently describe a
       world that no longer exists (HĐ-3.1, HĐ-13). The Python suite
       pins the schema side; this pins that the form knows why. */
    expect(FORM).toContain("deliberately not a schema default");
  });

  it("never overwrites an amplitude the template already declared", () => {
    /* The hall's 2 cm sigma is a measured figure. Overwriting it would
       be this form deciding what a deployment measured. */
    expect(FORM).toContain("if (!Number(at(filled, path) ?? 0))");
  });

  it("switches a source off by writing zero, not by adding a flag", () => {
    /* One representation of "off" in the data. A stored `enabled: false`
       beside a declared sigma is a deployment nobody can classify at a
       glance, and the two halves would be free to disagree. */
    expect(FORM).toContain("noiseField");
    expect(FORM).not.toContain("sensor_noise.enabled");
    expect(FORM).not.toContain('"enabled"');
  });

  it("gives back what was typed when a source is switched on again", () => {
    /* Losing an edited amplitude to a stray click is the kind of small
       thing that costs a re-measurement to notice. */
    expect(FORM).toContain("remembered[path] ?? NOISE_DEFAULTS[path].value");
  });
});

describe("the vehicle register fills the form, it does not own it", () => {
  /** P5 — `robot-profiles` becomes the source of truth for the *vehicle*.
   *
   * Before this, every deployment's robot was typed from memory into a
   * form, which is how one site ends up measured on a robot 4 cm wider
   * than another site's copy of the same machine. The register already
   * existed for the PPO adapter; it just had no way into a deployment.
   */
  const EN = en as Record<string, string>;

  it("offers the stored vehicles and copies their limits in", () => {
    expect(FORM).toContain("listRobotProfiles()");
    expect(FORM).toContain("const adoptVehicle = (id: string)");
    expect(FORM).toContain('withValue(next, "robot.radius", vehicle.radius)');
  });

  it("copies the numbers rather than storing a reference", () => {
    /* HĐ-13 asks somebody else to rebuild a run from the profile alone.
       A profile pointing at an editable database row would change
       meaning the day that row is edited, and every stored trace would
       quietly describe a different robot — under the same
       `task_profile_id`, so nothing would warn. That is the whole reason
       this is a fill and not a foreign key. */
    expect(FORM).not.toContain("robot_profile_id");
    expect(EN["deployments.form.vehicleNote"]).toContain("HĐ-13");
    expect(vi).toHaveProperty("deployments.form.vehicleNote");
  });

  it("never fills the control period from a vehicle", () => {
    /* T_cycle is gate G4's threshold — the budget one control step has
       on the target board. The same robot in a hall and in a warehouse
       aisle can be held to two different cycles, so filling it from the
       vehicle would let one setting move a gate at every site using that
       robot. The server keeps the field off `RobotProfile` entirely
       (`tests/api/test_robot_profile_boundary.py`); this is the same
       fence on the near side. */
    const adopt = FORM.slice(
      FORM.indexOf("const adoptVehicle"),
      FORM.indexOf("const chosenVehicle"),
    );
    expect(adopt).not.toContain("control_period");
    expect(EN["deployments.form.vehicleNote"]).toContain("Control period is not filled");
  });

  it("leaves an undeclared acceleration alone instead of writing a zero", () => {
    /* Null on a vehicle means nobody said. A zero here would say the
       robot cannot change speed, and the form would submit that as
       though somebody had claimed it. */
    expect(FORM).toContain("vehicle.max_linear_acceleration !== null");
    expect(FORM).toContain("undeclaredAccelerations");
    expect(EN["deployments.form.vehicleUndeclared"]).toContain("not zero");
  });

  it("still works with no vehicles stored", () => {
    /* A fresh install has an empty register. Losing the ability to file
       a deployment because a convenience list was empty would be a worse
       form than the one before the picker existed. */
    expect(FORM).toContain("listRobotProfiles().catch(() => [] as RobotProfile[])");
    expect(en).toHaveProperty("deployments.form.vehicleNone");
  });
});
