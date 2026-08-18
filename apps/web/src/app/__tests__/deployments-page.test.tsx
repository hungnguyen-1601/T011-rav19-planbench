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
const TRAFFIC_UI = readFileSync(join(process.cwd(), "src", "components", "TrafficEditor.tsx"), "utf8");
const TRAFFIC_LIB = readFileSync(join(process.cwd(), "src", "lib", "traffic.ts"), "utf8");

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
    for (const forbidden of ["if (radius <", "Math.PI)"]) {
      expect(FORM).not.toContain(forbidden);
    }
    /* One throw exists, and it is not about a deployment: it fires when a
       *caller of this file* passes a leaf name where a dotted path
       belongs, which is a mistake in the code rather than in what
       somebody typed. Counted rather than banned, so a second throw —
       which would more likely be a rule about a deployment — fails
       here. */
    expect(FORM.match(/throw new Error\(/g) ?? []).toHaveLength(1);
    expect(FORM).toContain("has no NOISE_DEFAULTS entry");
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

  it("says out loud what leaving both quiet costs", () => {
    /* With no traffic *and* no noise a deterministic planner replays one
       episode per seed, and G2's bound would rest on a sample of one.
       Legal, and the profile schema does not forbid it — so the form
       says it rather than refusing. The note used to end by sending the
       reader to the YAML tab for traffic; it no longer can, because the
       form writes traffic now. */
    const note = (en as Record<string, string>)["deployments.form.noiseNote"];
    expect(note).toContain("traffic");
    expect(note).toContain("one episode per seed");
    expect(note).not.toContain("YAML");
    expect((vi as Record<string, string>)["deployments.form.noiseNote"]).toContain("traffic");
    expect((vi as Record<string, string>)["deployments.form.noiseNote"]).not.toContain("YAML");
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
    /* The canvas and the pose fields are mounted separately here, one
       per column, while `/decisions` still uses the arrangement that
       holds all three together. Same components either way — a second
       copy would be a second answer to what clicking the map does. */
    expect(FORM).toContain("<MissionCanvas");
    expect(FORM).toContain("<MissionPoseFields");
  });

  it("has every key it asks for, in both locales", () => {
    /* Both files, because the authoring moved into its own component
       and the guard did not follow it. A dozen traffic keys were being
       checked by nothing at all: an untranslated one renders as its own
       dotted path, which reads as a bug in the page rather than as a
       missing line in a locale file. */
    for (const source of [FORM, TRAFFIC_UI]) {
      const keys = new Set([...source.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
      for (const key of keys) {
        expect(en, `en is missing ${key}`).toHaveProperty(key);
        expect(vi, `vi is missing ${key}`).toHaveProperty(key);
      }
    }
    /* Keys assembled from a variable, which the scan above cannot
       see — every branch of each, spelled out. */
    for (const source of ["library", "stored", "drawn"]) {
      expect(en).toHaveProperty(`deployments.form.source.${source}`);
      expect(vi).toHaveProperty(`deployments.form.source.${source}`);
    }
    for (const hint of ["self-seeded", "one-shot", "incomplete"]) {
      expect(en).toHaveProperty(`deployments.form.traffic.seedTimeOffset.${hint}`);
      expect(vi).toHaveProperty(`deployments.form.traffic.seedTimeOffset.${hint}`);
    }
    for (const kind of ["waypoint", "periodic", "randomWalk", "suddenStop"]) {
      expect(en).toHaveProperty(`deployments.form.traffic.kind.${kind}`);
      expect(vi).toHaveProperty(`deployments.form.traffic.kind.${kind}`);
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
    expect(FORM).toContain("remembered[path] ?? defaults.value");
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

describe("every noise control is wired to a field the contract has", () => {
  /** The guard for a bug that shipped and crashed the page.
   *
   * Three `noiseField` calls passed a leaf name — `"localization_drift_m"`
   * — where the full dotted path belongs. `NOISE_DEFAULTS` is keyed by
   * path, so the lookup returned undefined and reading `.step` threw:
   * `/deployments` was dead from the commit that turned the four noises
   * on by default until this test existed.
   *
   * **The schema drift guard could not catch it**, and that is the
   * lesson. `tests/test_form_covers_the_contract.py` asks whether each
   * contract field's path *appears in the file*; all seven did, in
   * `NOISE_DEFAULTS` itself. Presence is not wiring. This checks the
   * argument at each call site instead.
   *
   * A crash was the lucky outcome. Had a fallback step existed, the three
   * controls would have rendered fine while reading and writing a
   * top-level key no deployment has — three of the four noises the form
   * claims to switch on would have been decorative, and nothing on screen
   * would have said so.
   */
  const CALLS = [...FORM.matchAll(/noiseField\(\s*"([^"]+)"/g)].map((match) => match[1]);
  const KEYS = [...FORM.matchAll(/^\s{2}"(environment\.sensor_noise\.[^"]+)":/gm)].map(
    (match) => match[1],
  );

  it("finds every call and every default, so the comparison means something", () => {
    /* Both regexes can silently match nothing; an empty set would make
       every assertion below vacuously true. */
    expect(CALLS.length).toBeGreaterThanOrEqual(7);
    expect(KEYS.length).toBeGreaterThanOrEqual(7);
  });

  it("passes a full dotted path, never a leaf name", () => {
    for (const path of CALLS) {
      expect(path, `noise control path ${path} is not dotted`).toMatch(
        /^environment\.sensor_noise\./,
      );
    }
  });

  it("names a path that has an amplitude and a step", () => {
    for (const path of CALLS) {
      expect(KEYS, `NOISE_DEFAULTS has no entry for ${path}`).toContain(path);
    }
  });

  it("leaves no default without a control", () => {
    /* The other direction: an amplitude the form fills into the draft but
       offers no way to see or switch off would be a condition applied
       silently. */
    for (const key of KEYS) {
      expect(CALLS, `${key} has a default but no control`).toContain(key);
    }
  });

  it("fails by name rather than by TypeError if it ever happens again", () => {
    expect(FORM).toContain("has no NOISE_DEFAULTS entry");
    expect(FORM).not.toContain("NOISE_DEFAULTS[path].step");
  });
});

describe("the traffic comes with the map it belongs to", () => {
  /** The bug An hit: a deployment built from `sudden_stop` had no cart.
   *
   * The library picker advertises `sudden_stop · 1 traffic`, so somebody
   * chooses that scenario *because* of the cart. The form then wrote only
   * `environment.map` and `environment.map_yaml`, and the deployment ran
   * on an empty lane — the robot drove straight through, which reads as a
   * planner that ignores obstacles rather than a form that forgot them.
   *
   * `Scenario.dynamic_obstacles` and `TaskEnvironment.dynamic_obstacles`
   * are the same type (`tuple[DynamicObstacle, ...]`), so carrying them
   * is a copy, not a translation.
   */
  const EN_FORM = en as Record<string, string>;

  it("writes the scenario's obstacles into the deployment", () => {
    expect(FORM).toContain('withValue(next, "environment.dynamic_obstacles"');
    expect(FORM).toContain("scenario?.dynamic_obstacles ?? []");
  });

  it("clears them for a map with no scenario behind it", () => {
    /* A cart at `sudden_stop`'s coordinates means nothing on somebody
       else's walls. `?? []` is what makes a drawn or stored map arrive
       empty rather than inheriting the last scenario's traffic. */
    expect(FORM).toContain("?? []");
    const adopt = FORM.slice(FORM.indexOf("const adopt = useCallback"), FORM.indexOf("// Open on the default"));
    expect(adopt).toContain("environment.dynamic_obstacles");
  });

  it("lets the author change what it carried", () => {
    /* Carrying was only ever half of it. A map somebody drew arrived
       with no traffic and no way to add any, and the only place to write
       a cart was the YAML tab. */
    expect(FORM).toContain("<TrafficEditor");
    expect(FORM).toContain('set("environment.dynamic_obstacles", next)');
  });

  it("draws the route while it is being written, not only after a preview", () => {
    /* Placing three waypoints used to draw nothing at all: the canvas
       only ever showed positions the backend had computed, so authoring
       a route meant clicking into an empty map and pressing Preview to
       find out what had been written. The overlay comes from the
       document itself. */
    expect(FORM).toContain("authoredTraffic={overlayOf(");
    expect(FORM).toContain("trafficUi.selectedObstacleIndex");
  });

  it("says which of the two drawings the author can move", () => {
    /* Two pictures of the same obstacles sit on one canvas — the
       declared route and the previewed instant — and only the first is
       editable. Left to colour alone, a click on the amber marker reads
       as a broken control. */
    expect(FORM).toContain("deployments.form.traffic.legend");
    expect(EN_FORM["deployments.form.traffic.legend"]).toMatch(/not a control/i);
  });

  it("lets the map be edited directly, and decides each press in one place", () => {
    /* Placing used to be the only thing a press could mean, so moving a
       waypoint meant re-placing it from the toolbar. The three meanings
       a press now has — place, grab, select — are decided by one table
       rather than by whichever handler ran first. */
    expect(FORM).toContain("interpretPointer(");
    expect(FORM).toContain("onPointerDownFirst={claimPress}");
    expect(FORM).toContain("moveHandle(");
  });

  it("writes a drag through the document as it is now, not as it was", () => {
    /* One write per frame, each onto `draftRef.current`. A handler
       closed over the render's `draft` would rebuild from the state
       before the previous frame and the point would jitter between two
       positions — the same class of stale write the map adoption had
       across its await. */
    expect(FORM).toContain("requestAnimationFrame");
    const live = FORM.slice(FORM.indexOf("const setLive"), FORM.indexOf("// The defaults, from"));
    expect(live).toContain("draftRef.current");
    expect(live).toContain("flushDrag");
  });

  it("never lets a press that did not travel move anything", () => {
    /* A press on a waypoint is a candidate drag until it clears
       `dragGate`. Below that it is a click — it selected, or it was
       half of a double-click — and nudging the point under it would be
       an edit nobody asked for. */
    expect(FORM).toContain("dragGate(");
    const finish = FORM.slice(FORM.indexOf("const endDrag"), FORM.indexOf("const removeWaypointUnder"));
    expect(finish).toContain("if (!active.committed) return;");
    /* And a cancel keeps the last position a *move* reported: the
       cancel event itself can arrive from a gesture interruption
       carrying one nobody pointed at. */
    expect(finish).toContain("active.lastWorld");
    /* The last write of a drag happens as the gesture ends, so the
       flush is handed the handle rather than reading it back off the
       ref that has just been cleared. An earlier version did read it
       back, found nothing, and silently threw away the position the
       pointer was released at — a bug with no symptom except that a
       dragged point settled a few pixels behind the mouse. */
    expect(finish).toContain("flushDrag(active.hit,");
    expect(FORM).not.toMatch(/flushDrag\(\s*(current\.)?pending/);
  });

  it("puts the map beside the controls rather than a screen below them", () => {
    /* Thirty fields stacked in one column left the map — the thing most
       of them are about — near the bottom, so choosing a traffic route
       meant scrolling away from the picture of it. */
    expect(FORM).toContain("gridTemplateColumns");
    expect(FORM).toContain("sideBySide(shellWidth)");
    /* Measured, and passed down as a number. `MapCanvas` maps a press
       to world coordinates assuming its surface and its CSS box are the
       same size, so a `width: 100%` stretch would land every click away
       from the pointer while the map still looked right. */
    expect(FORM).toContain("canvasSize(roomForMap");
    expect(FORM).toContain("width={canvas.width}");
    /* And the map's track *is* the map. Two flexible tracks left the
       canvas at the left edge of a wider column and the panel at the
       right edge of another, with a gap between them that belonged to
       neither — which is what made the picker under the map look like
       it was floating between the two. */
    expect(FORM).toContain("`${canvas.width}px minmax(0, 1fr)`");
  });

  it("says which tab a refusal is behind, and jumps there after a check", () => {
    /* A tab is a place to hide things. Without a badge and a jump, a
       refused field on an unopened tab blocks filing while the author
       is shown nothing at all. */
    expect(FORM).toContain("tallyErrors(shownErrors)");
    expect(FORM).toContain("firstTabWithError(addressed)");
    /* And an address no tab claims is printed in full rather than
       counted into whichever tab looked closest. */
    expect(FORM).toContain("tally.unmapped.map");
  });

  it("can take back the change a stray click just made", () => {
    /* One click on the canvas moves the start, and before this there
       was no way back to the old coordinates except remembering them.
       The mission is inside the snapshot for that reason — it is part
       of the document, and the part most often changed by accident. */
    expect(FORM).toContain("pushHistory(");
    expect(FORM).toContain("undoHistory(");
    const memory = FORM.slice(FORM.indexOf("interface FormMemory"), FORM.indexOf("const NOISE_DEFAULTS"));
    expect(memory).toContain("draft");
    expect(memory).toContain("start");
    expect(memory).toContain("goal");
  });

  it("leaves Ctrl-Z alone while the caret is in a text box", () => {
    /* The browser's own undo works there, on the characters being
       typed. Taking it over to rewind the whole profile would answer a
       request for one word back by throwing away a map. */
    const shortcut = FORM.slice(FORM.indexOf("const onKey"), FORM.indexOf("window.addEventListener"));
    expect(shortcut).toContain("input, textarea, select");
    expect(shortcut).toContain("return;");
  });

  it("offers the shortcut as buttons too", () => {
    /* Ctrl-Z is discoverable only to somebody who already suspects it
       is there, and the accident it undoes happens to people who have
       not thought about undo at all. */
    expect(FORM).toContain('t("deployments.form.undo")');
    expect(FORM).toContain("history.length === 0");
    expect(FORM).toContain("future.length === 0");
  });

  it("explains a field beside it rather than under it", () => {
    /* Thirty paragraphs of consequence took more room than the
       controls they described, and a panel that is four-fifths prose
       is one nobody reads. The text is still one sentence per number —
       it is behind a mark now. */
    expect(FORM).toContain("<Hint");
    /* And a refusal is never behind one: a hidden refusal leaves an
       author staring at a form that does nothing when they press the
       button. */
    const field = FORM.slice(FORM.indexOf("function Field({"), FORM.indexOf("function Choice({"));
    expect(field).toContain('<span className="badge err">{error}</span>');
    expect(field).not.toMatch(/<Hint[^/]*error/);
  });

  it("still refuses to judge the obstacles itself", () => {
    /* The rule did not soften when the work moved into its own files.
       `TaskProfile` decides; the browser asks. What would break this is
       a comparison in TypeScript — an offset measured against a period,
       a name checked against another name — so those are what is looked
       for, in both files that could hold one. */
    for (const source of [FORM, TRAFFIC_UI, TRAFFIC_LIB]) {
      expect(source).not.toContain("< motion.period");
      expect(source).not.toContain("seed_time_offset <=");
      expect(source).not.toContain("seed_time_offset ===  0");
      expect(source).not.toMatch(/must be unique|duplicate name/i);
    }
  });

  it("asks the server for the verdict instead", () => {
    expect(FORM).toContain('"/task-profiles/validate"');
    expect(FORM).toContain("fieldErrorsOf(caught)");
  });

  it("has somewhere to show every refusal about the traffic, at either depth", () => {
    /* Pydantic addresses what it can. A rule written as a model
       validator on `EnvironmentSpec` — unique names, a head start, a
       full period, a declared closing speed, a shared clock — lands on
       `environment`; a field constraint lands on
       `environment.dynamic_obstacles.0.radius`. Both are pinned in
       tests/api/test_api_profile_validation.py.

       The first version passed only the block-level path, so a refused
       radius blocked filing while the author was shown nothing at all.
       Hence: the form hands over everything addressed to this block, and
       the editor renders the deep ones beside their row and the rest at
       the top. */
    expect(FORM).toContain('entry.path.startsWith("environment.")');
    expect(TRAFFIC_UI).toContain("rowErrors");
    expect(TRAFFIC_UI).toContain("blockErrors");
  });

  it("keeps a verdict from outliving the document it was about", () => {
    /* A green "the server accepts this" beside a document that has
       changed since is read as current. The clearing lived inside `set`
       at first, so typing in a field invalidated it while moving the
       start pose, adopting a map or applying a vehicle did not. */
    expect(FORM).toContain("invalidateCheck");
    /* Five ways to change the document — a field, the map, the vehicle,
       the mission, and dragging a point on the canvas — across six
       calls, because the map retires the verdict twice: once when it is
       asked for, since the picker already shows something the draft
       does not, and once when the write lands and the draft actually
       changes. Counted rather than named so a further way added later
       fails here instead of silently keeping a stale tick.

       The sixth arrived with handle dragging and is a second *writer*
       rather than a second rule: `setLive` writes onto
       `draftRef.current` instead of the render's `draft`, because a
       drag writes once per animation frame and a closure captured at
       render time would rebuild the document from the state before the
       previous frame. Both writers retire the verdict, which is the
       thing this count is here to protect.

       The seventh came with the two-column layout: the mission is now
       edited from two places — dragging its markers on the canvas in
       one column, typing its coordinates in the Mission tab in the
       other — and each of them is a change to the document.

       Eight and nine are undo and redo. Putting an older document back
       is as much a change as making one: a green "the server accepts
       this" left standing over a rewind would be a verdict about a
       document that is no longer on screen — the exact failure this
       count guards, arriving from the one direction nothing else
       covers. */
    expect(FORM.match(/invalidateCheck\(\)/g) ?? []).toHaveLength(9);
    // And a reply already in flight when the document moved on is an
    // answer to a question nobody is asking any more.
    expect(FORM).toContain("revision.current !== asked");
  });

  it("does not let a reply about an older document draw over a newer one", () => {
    /* Three handlers here finish after an await, and each of them can
       land on a document that has moved on. Clearing the picture was not
       enough for the preview: a request that left before the edit still
       matched its own sequence when it returned, so it drew the old
       world back over the cleared canvas. Adopting a map has the same
       shape — a late answer about map A would put its paths under map
       B's grid, and a `draft` captured before the await would undo
       whatever was typed while it ran. */
    expect(FORM).toContain("previewSeq.supersede()");
    expect(FORM).toContain("adoption.isCurrent(token)");
    expect(FORM).toContain("draftRef.current");
  });

  it("decides which map won when it was chosen, not when it answered", () => {
    /* Claiming the token inside `adopt` — after the grid had been
       fetched — ordered the maps by how fast the server answered. Pick
       A, pick B, B answers first and takes token 1, A answers second and
       takes token 2, and A wins although nobody selected it. The claim
       belongs beside the choice; `sequencer.test.ts` checks that the
       ordering itself behaves. */
    const chooser = FORM.slice(
      FORM.indexOf("const adoptStoredMap"),
      FORM.indexOf("// Open on the default"),
    );
    expect(chooser.indexOf("adoption.claim()")).toBeLessThan(chooser.indexOf("api.getMap(id)"));
  });

  it("freezes from the moment the map is asked for, not from when it lands", () => {
    /* The freezing started inside `adopt`, which runs only once the grid
       has arrived — so for the whole length of the request the picker
       already showed the new map while the draft, the canvas and the
       mission were still the old one, and nothing was disabled. Filing
       in that window stores a deployment nobody is looking at. */
    const chooser = FORM.slice(
      FORM.indexOf("const adoptStoredMap"),
      FORM.indexOf("// Open on the default"),
    );
    expect(chooser.indexOf("beginAdoption()")).toBeLessThan(chooser.indexOf("api.getMap(id)"));
    expect(FORM).toContain("setAdopting(true)");
    // And it lifts again however the request ends, or a failed import
    // leaves the form frozen for good.
    expect(FORM.match(/setAdopting\(false\)/g) ?? []).toHaveLength(4);
  });

  it("treats picking the blank option as a choice too", () => {
    /* It says "not that map". Returning early without claiming left an
       adoption already fetching, and it went on to commit a map the
       picker no longer shows — the same race by the one path that
       starts no request of its own. An unused token still supersedes
       what is in flight, so the claim comes before the branch. */
    const chooser = FORM.slice(
      FORM.indexOf("const adoptStoredMap"),
      FORM.indexOf("// Open on the default"),
    );
    expect(chooser.indexOf("adoption.supersede()")).toBeLessThan(
      chooser.indexOf("beginAdoption()"),
    );
  });

  it("writes a map into the draft only once nothing can still fail", () => {
    /* The old order set the grid, the id and the mission first and then
       awaited the file write. A failure there left the canvas showing
       one map while the draft still named another, with nothing to roll
       it back and nothing saying so. */
    const adopt = FORM.slice(FORM.indexOf("const adopt = useCallback"), FORM.indexOf("// Open on"));
    expect(adopt.indexOf("await materialiseMap")).toBeLessThan(adopt.indexOf("setMapData(data)"));
    expect(adopt).toContain("catch (caught)");
  });

  it("locks filing and checking while a map is being written out", () => {
    /* During that window the canvas already shows the new map and the
       draft still names the old one, so filing would store a deployment
       nobody is looking at. */
    expect(FORM).toContain("busy || checking || adopting");
    expect(FORM).toContain('disabled={frozen || !complete} onClick={() => void submit()}');
    expect(FORM).toContain("disabled={frozen || !complete} onClick={() => void check()}");
  });

  it("retires the picture when the instant it is labelled with changes", () => {
    expect(FORM).toContain("scrubPreview");
    expect(FORM.match(/scrubPreview\(\)/g) ?? []).toHaveLength(2);
  });

  it("disables the preview on the same answer that would make it do nothing", () => {
    /* `previewRequestOf` returns nothing when the draft has not declared
       something the scenario needs. Leaving the button enabled made a
       click silently return, which reads as a broken preview rather than
       as an unfinished deployment. */
    expect(FORM).toContain("disabled={frozen || !previewRequest}");
  });

  it("shows the half of the preview's answer that is not a picture", () => {
    /* The endpoint validates against the *map* — a start inside a wall,
       an obstacle in occupied cells — and none of that reaches
       `POST /task-profiles/validate`, which reads the document and never
       opens the grid. Drawing the traffic while dropping `valid` shows a
       scene that cannot run as though nothing were wrong. */
    expect(FORM).toContain("preview && !preview.valid");
    expect(FORM).toContain("preview.errors.map");
  });

  it("still advertises the count it is now honouring", () => {
    /* The picker's `· N traffic` was true about the scenario and false
       about the deployment it produced. Keeping the label and fixing the
       write is what makes the two agree. */
    expect(FORM).toContain("entry.dynamic_obstacles > 0");
  });
});

describe("deleting a deployment asks only when there is something to lose", () => {
  /** One click for a draft, two when something was measured.
   *
   * A deployment nobody ran is a description. One with stored runs is the
   * *subject* of each of them, which is why the foreign key is
   * `ON DELETE RESTRICT` rather than a cascade: a statement whose subject
   * vanished is unreadable, not merely smaller.
   */
  it("always asks the server first, even for a row that looks untouched", () => {
    /* Whether anything was measured is a fact about the run store. A
       page deciding it from what it had already loaded would be a second
       answer — wrong in the window between the list arriving and the
       button being pressed. */
    expect(PAGE).toContain("const attempt = async (deleteRuns: boolean)");
    expect(PAGE).toContain("deleteTaskProfile(id, { deleteRuns })");
    expect(PAGE).not.toContain("runs.length > 0 ?");
  });

  it("shows the server's counts rather than a bare confirmation", () => {
    /* "Delete 7 runs, 2 of them approved?" is answerable. "Are you
       sure?" is not. */
    expect(PAGE).toContain("blocked.runs");
    expect(PAGE).toContain("blocked.approved");
    expect((en as Record<string, string>)["deployments.delete.blocked"]).toContain("{runs}");
    expect(vi).toHaveProperty("deployments.delete.blocked");
  });

  it("offers no confirm button at all when a run is approved", () => {
    /* Two refusals that look alike and are not. Runs pose a question a
       confirmation answers; an approved run does not. A dialog whose
       confirm button destroys an audit trail is a speed bump, not a
       safeguard — so that button is not rendered, rather than rendered
       and refused by the server. */
    expect(PAGE).toContain("const permanent = (blocked.approved_ids?.length ?? 0) > 0");
    const dialog = PAGE.slice(PAGE.indexOf("if (blocked) {"), PAGE.indexOf("deployments.delete.action"));
    expect(dialog).toContain("permanent ? (");
    expect((en as Record<string, string>)["deployments.delete.approvedBlocked"]).toContain("HĐ-14");
  });

  it("points at the runs holding it instead of leaving somebody hunting", () => {
    expect(PAGE).toContain("deployments.delete.openRuns");
    expect(vi).toHaveProperty("deployments.delete.openRuns");
  });

  it("keeps a non-refusal error out of the confirmation path", () => {
    /* A network fault must not open a dialog offering to delete
       measurements that are still there. */
    const client = readFileSync(join(process.cwd(), "src", "lib", "decisions.ts"), "utf8");
    expect(client).toContain("if (blocked) return blocked;");
    expect(client).toContain("throw caught;");
  });

  it("reads the counts off the raw refusal, not the field-shaped list", () => {
    /* `errorBody` filters `details` to `{path, message}` for forms; the
       counts are a different shape and were being dropped by that filter
       until `raw` existed. */
    const auth = readFileSync(join(process.cwd(), "src", "lib", "auth.ts"), "utf8");
    expect(auth).toContain("public raw: unknown[]");
    const client = readFileSync(join(process.cwd(), "src", "lib", "decisions.ts"), "utf8");
    expect(client).toContain("error instanceof FieldError ? error.raw[0]");
  });

  it("refreshes the list rather than trusting its own copy", () => {
    expect(PAGE).toContain("onDeleted={refresh}");
  });
});

describe("an approval can be taken back, and taking it back is itself recorded", () => {
  /** The door the delete refusal points at.
   *
   * `decide_config` treats every state but `pending` as terminal — "that
   * decision stands" — so before this the refusal would have told
   * somebody to withdraw an approval they could not withdraw: a wall
   * with a sign on it.
   *
   * Withdrawing is not an undo. The approve event stays in the journal
   * and a withdraw event lands beside it with a name and a reason, which
   * is what keeps HĐ-14 whole: an approval that could vanish silently
   * would be an approval nobody could rely on.
   */
  const DETAIL_PAGE = readFileSync(
    join(process.cwd(), "src", "app", "decisions", "[id]", "page.tsx"),
    "utf8",
  );

  it("offers the control only on an approved run", () => {
    const branch = DETAIL_PAGE.slice(
      DETAIL_PAGE.indexOf('run.config_state === "approved" ? ('),
      DETAIL_PAGE.indexOf("decisions.acts.whyNoConfig"),
    );
    expect(branch).toContain("withdrawConfig(run.id, comment)");
  });

  it("returns the run to undecided rather than to rejected", () => {
    /* "Undecided again" and "decided against" are different claims, and
       writing the second would record a verdict nobody reached. */
    const client = readFileSync(join(process.cwd(), "src", "lib", "decisions.ts"), "utf8");
    expect(client).toContain("export function withdrawConfig(");
    expect(client).toContain('"undecided again" rather than');
  });

  it("says the approval is kept, not erased", () => {
    expect((en as Record<string, string>)["decisions.withdraw.note"]).toContain("not erased");
    expect(vi).toHaveProperty("decisions.withdraw.note");
  });

  it("has a name for the new journal entry", () => {
    /* An audit row rendering as a raw enum is an audit row nobody
       reads. */
    expect(en).toHaveProperty("decisions.audit.withdraw_config");
    expect(vi).toHaveProperty("decisions.audit.withdraw_config");
  });
});

describe("replanning is declared by the deployment, and has no budget", () => {
  /** The half that was missing until now.
   *
   * Replanning existed in the simulator and no profile could declare it,
   * so every measured episode ran with it off and nothing on screen said
   * so. It is a *deployment* condition — applied on the path every
   * candidate goes through, one trigger for all of them — which is what
   * stops it being a capability one stack has and another does not.
   */
  const EN_REPLAN = en as Record<string, string>;
  const V_OBSTACLE_MAX_PATH = "environment.v_obstacle_max";

  it("offers the switch", () => {
    expect(FORM).toContain('at(draft, "replanning.enabled")');
    expect(FORM).toContain('set("replanning.enabled", event.target.checked)');
  });

  it("stays beside the map rather than up with the other conditions", () => {
    /* Where it belongs by category is beside the constraints; where it
       belongs by use is next to the map. Deciding whether the robot may
       replan is a thought you have *while looking at the traffic you
       just picked*, and up with the constraints it was a scroll away
       from the moment it occurs to anybody.

       In the single column that meant "directly under the map picker".
       Now the map is a column of its own and the controls are tabs
       beside it, so the same rule means "on the Policies tab, in view
       of the map" — with the closing speed, which is the other thing
       moving traffic makes you decide. */
    const policies = FORM.slice(
      FORM.indexOf("const policiesTab"),
      FORM.indexOf("const hardwareTab"),
    );
    expect(policies).toContain('set("replanning.enabled"');
    expect(policies).toContain('set("recovery.enabled"');
    expect(policies).toContain(V_OBSTACLE_MAX_PATH);
  });

  it("stands out when the chosen scenario has traffic", () => {
    expect(FORM).toContain('traffic > 0 ? "notice warn" : ""');
    expect(EN_REPLAN["deployments.form.replanningTraffic"]).toContain("local controller");
    expect(vi).toHaveProperty("deployments.form.replanningTraffic");
  });

  it("highlights without ticking", () => {
    /* Ticking would be the form deciding an evaluation condition for the
       author, and the reason this field lives on the deployment at all
       is that such decisions are declared rather than inferred.
       Highlighting says "this is the choice you are about to skip";
       ticking would say "we made it for you". */
    const block = FORM.slice(
      FORM.indexOf('traffic > 0 ? "notice warn"'),
      FORM.indexOf("const hardwareTab"),
    );
    expect(block).not.toContain('set("replanning.enabled", true)');
    expect(block).toContain("event.target.checked");
  });

  it("counts the traffic off the draft, not off the library entry", () => {
    /* The draft is what will be measured, and it is the only source that
       also covers a stored or drawn map — where there is no library
       entry to ask. */
    expect(FORM).toContain('at(draft, "environment.dynamic_obstacles")');
  });

  it("offers no budget field, and that is the point", () => {
    /* A cap is a number somebody chose. Under a budget of three, a stack
       that would have escaped on its fourth try is scored as a failure
       of the cap rather than of the planner — the same class of artifact
       as the replan information privilege (HĐ-4.1). */
    expect(FORM).not.toContain("max_replans");
  });

  it("says what pays for it instead", () => {
    /* Unlimited is only defensible because each replan is charged to the
       control step it delayed. Without that sentence the switch reads as
       a free capability. */
    expect(EN_REPLAN["deployments.form.replanningNote"]).toContain("charged");
    expect(EN_REPLAN["deployments.form.replanningNote"]).toContain("p99");
    expect(vi).toHaveProperty("deployments.form.replanningNote");
  });

  it("warns that switching it on is a different deployment", () => {
    /* `episode_context_id` does not hash it, so the same seeds under two
       settings produce identical context ids for two experiments — the
       trap `sensor_noise` sprang. */
    expect(EN_REPLAN["deployments.form.replanningNote"]).toContain("HĐ-3.1");
  });
});
