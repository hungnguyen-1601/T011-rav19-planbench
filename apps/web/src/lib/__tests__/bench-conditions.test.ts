/** The condition cards, checked against the contract they claim to show.
 *
 * **What this file is actually for.** The test bench used to render four
 * cards covering eleven of a deployment's fields; the other thirty were
 * off the page and nothing could tell you which. That is not a bug you
 * find by reading the page — the page looks complete either way — so the
 * inventory is compared against the pydantic schemas themselves, parsed
 * out of `packages/schemas` on every run. A field added to `TaskProfile`
 * and not placed in a group turns this red, which is the only mechanism
 * that survives the next person adding a field.
 *
 * The second half is the honesty of an absent value, and it is finer
 * than it first looks. A profile is stored as a complete model dump, so
 * a missing key means the profile predates the field — and the episode
 * still ran, under the schema's default. Printing "not declared" there
 * answers a question about the document while every row beside it
 * answers one about the run. But some absences have no number behind
 * them at all: `v_obstacle_max: null` is *no braking claim*, not a
 * standing obstacle, and `cost_per_mission_max: null` is a customer who
 * would not name a budget, not one who will pay nothing. So the tests
 * below check both directions — that a default is shown where the
 * contract has one, and that a refusal is never rendered as a zero.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  CONDITION_GROUPS,
  conditionValue,
  describeCondition,
  type ConditionField,
} from "@/lib/benchConditions";
import { DICTIONARIES } from "@/lib/i18n";

const SCHEMAS = join(process.cwd(), "..", "..", "packages", "schemas", "planbench_schemas");

const SOURCES: Record<string, string> = {
  task_profile: readFileSync(join(SCHEMAS, "task_profile.py"), "utf8"),
  robot: readFileSync(join(SCHEMAS, "robot.py"), "utf8"),
  sensor: readFileSync(join(SCHEMAS, "sensor.py"), "utf8"),
  replanning: readFileSync(join(SCHEMAS, "replanning.py"), "utf8"),
  recovery: readFileSync(join(SCHEMAS, "recovery.py"), "utf8"),
};

/** The annotated attributes of one pydantic model.
 *
 * Docstrings are stripped first: `task_profile.py` documents its fields
 * in prose containing tables, and a line of prose that happens to read
 * `word: something` would otherwise be collected as a field. Everything
 * kept is indented exactly four spaces, which is a class body and not a
 * method body — `model_config = ConfigDict(…)` has no annotation and is
 * skipped for free.
 */
function fieldsOf(source: string, className: string): string[] {
  const start = source.indexOf(`class ${className}(`);
  expect(start, `${className} is no longer declared where this test looks`).toBeGreaterThan(-1);
  const rest = source.slice(start);
  const next = rest.slice(1).search(/\nclass \w/);
  const body = next === -1 ? rest : rest.slice(0, next + 1);
  const clean = body.replace(/"""[\s\S]*?"""/g, "");
  return [...new Set([...clean.matchAll(/^ {4}([a-z_][a-z0-9_]*): /gm)].map((m) => m[1]))];
}

/** Every model a deployment is made of, and where it is declared.
 *
 * `CapabilityGrant`, `DynamicObstacle` and `Pose2D` are absent on
 * purpose and the reason differs: the first two are *elements of a
 * collection* the deployment declares any number of, so they are
 * summarised rather than given a row each, and `Pose2D` is three
 * coordinates rendered as one. `CapabilityGrant` is still checked below,
 * one test down, because its provider fields do reach the screen.
 */
const MODELS: [file: string, className: string][] = [
  ["task_profile", "TaskProfile"],
  ["task_profile", "EnvironmentSpec"],
  ["task_profile", "Mission"],
  ["task_profile", "TaskRobotSpec"],
  ["task_profile", "TaskConstraints"],
  ["task_profile", "HardwareSpec"],
  ["task_profile", "RamBudgetItem"],
  ["robot", "RobotConfig"],
  ["sensor", "SensorNoise"],
  ["replanning", "ReplanningConfig"],
  ["recovery", "RecoveryConfig"],
];

const ALL_FIELDS = new Set(MODELS.flatMap(([file, cls]) => fieldsOf(SOURCES[file], cls)));

const ALL_ROWS: ConditionField[] = CONDITION_GROUPS.flatMap((group) => [...group.fields]);

/** Every name a path walks through — containers included, because
 *  `environment` and `constraints` are fields of `TaskProfile` too and a
 *  card that dropped one of those blocks entirely has to be caught. */
const REACHED = new Set(ALL_ROWS.flatMap((field) => field.path.split(".")));

describe("the seven cards cover the whole deployment", () => {
  it("is seven groups, not four", () => {
    expect(CONDITION_GROUPS).toHaveLength(7);
    expect(CONDITION_GROUPS.map((group) => group.tone)).toEqual([
      "scope",
      "mission",
      "robot",
      "thresholds",
      "environment",
      "sensing",
      "behaviour",
    ]);
  });

  it("leaves no field of the contract off the page", () => {
    /* The test that matters. A field added to any of the schemas above
       and not given a row appears here by name, so the failure says what
       is missing rather than that something is. */
    const missing = [...ALL_FIELDS].filter((name) => !REACHED.has(name)).sort();
    expect(missing).toEqual([]);
  });

  it("invents no row the contract does not have", () => {
    /* The other direction, and it is the one that catches a typo: a path
       misspelt reads `undefined` off every profile and renders as "not
       declared" forever, which looks exactly like a deployment that
       never filled the field in. */
    const invented = ALL_ROWS.map((field) => field.path.split(".").at(-1) ?? "")
      .filter((name) => !ALL_FIELDS.has(name))
      .sort();
    expect(invented).toEqual([]);
  });

  it("puts each field in exactly one group", () => {
    const paths = ALL_ROWS.map((field) => field.path);
    expect(paths).toHaveLength(new Set(paths).size);
  });

  it("shows what a capability grant names, rather than counting grants", () => {
    /* Grants are summarised into one row, so the four fields of
       `CapabilityGrant` cannot be checked as paths. They are checked as
       what the formatter reads instead — including `provider_config`,
       which reaches the execution fingerprint: a tracker retuned between
       two sweeps is a different experimental condition (§5.2). */
    const module = readFileSync(join(process.cwd(), "src", "lib", "benchConditions.ts"), "utf8");
    for (const field of fieldsOf(SOURCES.task_profile, "CapabilityGrant")) {
      expect(module, `capability grants drop ${field}`).toContain(field);
    }
  });

  it("labels every row in both languages", () => {
    /* A row whose key is missing renders the key itself, which on a card
       of thresholds reads as a field nobody can identify. */
    for (const field of ALL_ROWS) {
      expect(DICTIONARIES.en, field.path).toHaveProperty(field.labelKey);
      expect(DICTIONARIES.vi, field.path).toHaveProperty(field.labelKey);
    }
    for (const group of CONDITION_GROUPS) {
      expect(DICTIONARIES.en).toHaveProperty(group.titleKey);
      expect(DICTIONARIES.vi).toHaveProperty(group.titleKey);
    }
  });
});

describe("a row with nothing to fall back on says so", () => {
  /* **What these assertions used to claim, and why they now say less.**
     This block was written as "an undeclared field is not a zero and not
     an off switch", and it made that claim of every row on the page: an
     absent flag read as "not declared", never as Off, and an absent
     number never printed the schema default, on the reasoning that a
     default on screen is a threshold the gates were never held to.

     Half of that reasoning was wrong, and the card's own heading is what
     shows it — *conditions taken from the deployment and kept unchanged
     for this episode*. The gates **were** held to the default: a profile
     with no `clearance_preference` planned at 4.0, one with no
     `replanning` block ran with replanning off, and `TaskProfile` says
     so. The row was describing how complete the paperwork was while
     every row beside it described the run.

     So the rule moved onto the field, as `whenAbsent` — and these
     assertions kept their intent by narrowing to the rows that have no
     such answer. Every field of the sensing card is one: `SensorNoise`
     amplitudes are a measurement of the site, and a zero is the claim
     that somebody measured it as silent. The two halves that must not
     collapse into each other are still checked, one block down. */
  const t = (key: string) => key;
  const field = (kind: ConditionField["kind"], unit?: string): ConditionField => ({
    path: "x",
    labelKey: "x",
    kind,
    unit,
  });

  it("reads a missing flag as undeclared rather than as off", () => {
    /* Still true of a row that names no default. What changed is that
       `replanning.enabled` is no longer such a row: it has one, because
       `TaskProfile.replanning` defaults to `NO_REPLANNING` and the
       episode ran under it. */
    expect(describeCondition(field("flag"), undefined, t)).toEqual({ state: "undeclared" });
    expect(describeCondition(field("flag"), false, t)).toEqual({ state: "off" });
    expect(describeCondition(field("flag"), true, t)).toEqual({ state: "on" });
  });

  it("keeps a declared zero as a value", () => {
    /* Zero is the off switch for a noise amplitude — `SensorNoise` says
       so in as many words — so it is a choice and has to read as one. */
    expect(describeCondition(field("number", "m"), 0, t)).toEqual({
      state: "value",
      text: "0 m",
    });
  });

  it("never lets a null become a zero", () => {
    /* The assertion this file exists to keep. `v_obstacle_max: null`
       means "no braking claim against moving traffic" and
       `cost_per_mission_max: null` means business mode refuses rather
       than inventing a budget; both are the absence of a commitment,
       and `0` is a commitment — that nothing at the site moves, that
       the site will pay nothing. A row with no fallback still reports
       the silence; the rows that carry those two fields give it words,
       checked below. */
    expect(describeCondition(field("number", "m/s"), null, t)).toEqual({ state: "undeclared" });
  });

  it("separates an empty list from a missing one", () => {
    /* `dynamic_obstacles: []` is a site with no traffic — a legal and
       consequential statement, because with no traffic and no noise a
       deterministic planner replays one episode per seed. A missing key
       is not that statement, and a row with no `whenAbsent` cannot make
       it one. The traffic row does have one, because `default=()` says
       an empty site is exactly what the omission meant. */
    expect(describeCondition(field("count"), [], t)).toEqual({ state: "value", text: "0" });
    expect(describeCondition(field("count"), undefined, t)).toEqual({ state: "undeclared" });
  });

  it("says unlimited where the replan budget is null", () => {
    /* `ReplanningConfig` promotes an unset budget to `None` when
       replanning is switched on, and unlimited is the opposite of the
       `0` a naive renderer would print. */
    expect(describeCondition(field("budget"), null, t)).toEqual({
      state: "value",
      text: "bench.cond.unlimited",
    });
    expect(describeCondition(field("budget"), 3, t)).toEqual({ state: "value", text: "3" });
    expect(describeCondition(field("budget"), undefined, t)).toEqual({ state: "undeclared" });
  });

  it("keeps one decimal on a rate, so two thresholds do not print as one", () => {
    /* `no_path_rate_max` defaults to 0.02; rounding to whole percent
       would show 0.02 and 0.024 as the same 2%. */
    expect(describeCondition(field("rate"), 0.024, t)).toEqual({ state: "value", text: "2.4 %" });
  });
});

describe("environment, thresholds and behaviour answer for the episode", () => {
  /* **The three cards a reader checks a run against.** A profile is
     filed through `TaskProfile.model_validate` and stored as a full
     `model_dump(mode="json")`, so a key is missing only when the profile
     predates the field. The episode still ran, and it ran under the
     schema default — which is what these cards now print, rather than
     reporting that the document is old. */
  const t = (key: string) => key;
  const TONES = ["environment", "thresholds", "behaviour"] as const;
  const rows = CONDITION_GROUPS.filter((group) =>
    (TONES as readonly string[]).includes(group.tone),
  ).flatMap((group) => [...group.fields]);

  /** Fields the schema makes required with no default of their own.
   *
   * A gap here is not an old profile, it is a broken record: pydantic
   * refuses to file one without them, so nothing that ever ran can be
   * missing them. "Not declared" is the honest word for a record that
   * should be impossible, and inventing a success floor or a map path
   * for it would be the one thing these cards must never do. */
  const REQUIRED_WITH_NO_DEFAULT = [
    "environment.map",
    "environment.map_yaml",
    "constraints.success_rate_min",
    "constraints.collision_probability_max",
    "constraints.stuck_threshold_s",
    "constraints.clearance_warning_m",
  ];

  it("resolves an absent field to the value the episode ran under", () => {
    /* Each expectation is a default read out of the pydantic source, not
       a number picked here: `no_path_rate_max=0.02` and
       `clearance_preference=4.0` in `task_profile.py`, `enabled=False`
       with `max_replans=0` in `replanning.py`, `enabled=False` with
       `max_escalation=len(LADDER)` and `max_forgets=1` in
       `recovery.py`, `dynamic_obstacles=()` on `EnvironmentSpec`. */
    const shown = (path: string) => {
      const found = rows.find((field) => field.path === path);
      expect(found, `${path} has no row`).toBeDefined();
      return describeCondition(found as ConditionField, undefined, t);
    };
    expect(shown("environment.dynamic_obstacles")).toEqual({ state: "value", text: "0" });
    expect(shown("constraints.no_path_rate_max")).toEqual({ state: "value", text: "2.0 %" });
    expect(shown("replanning.enabled")).toEqual({ state: "off" });
    expect(shown("replanning.max_replans")).toEqual({ state: "value", text: "0" });
    expect(shown("recovery.enabled")).toEqual({ state: "off" });
    expect(shown("recovery.max_escalation")).toEqual({ state: "value", text: "4" });
    expect(shown("recovery.max_forgets")).toEqual({ state: "value", text: "1" });
    expect(shown("clearance_preference")).toEqual({ state: "value", text: "4" });
  });

  it("says the absence in words where the contract has no number for it", () => {
    /* The half of the old rule that survives, and the reason it had to
       be moved onto the field rather than dropped. `v_obstacle_max`'s
       docstring enumerates three meanings and puts `None` outside the
       numbers: the loader skips its braking check entirely, so `0` would
       assert the opposite — that nothing here moves — which the same
       loader refuses beside declared traffic. `cost_per_mission_max` is
       the money anchor business mode declines to invent (HĐ-8.3 law 4);
       a `0` ceiling would fail every candidate instead. Different
       sentences for different fields, because they are not saying the
       same thing. */
    const unbounded = (path: string) => {
      const found = rows.find((field) => field.path === path);
      return describeCondition(found as ConditionField, null, t);
    };
    expect(unbounded("environment.v_obstacle_max")).toEqual({
      state: "value",
      text: "bench.cond.noBrakingClaim",
    });
    expect(unbounded("constraints.cost_per_mission_max")).toEqual({
      state: "value",
      text: "bench.cond.noCostCeiling",
    });
    for (const key of ["bench.cond.noBrakingClaim", "bench.cond.noCostCeiling"]) {
      expect(DICTIONARIES.en).toHaveProperty(key);
      expect(DICTIONARIES.vi).toHaveProperty(key);
      expect(DICTIONARIES.en[key as keyof typeof DICTIONARIES.en]).not.toMatch(/\b0\b/);
      expect(DICTIONARIES.vi[key as keyof typeof DICTIONARIES.vi]).not.toMatch(/\b0\b/);
    }
  });

  it("leaves exactly the required fields with no answer, and nothing else", () => {
    /* Written as a set comparison rather than a loop of allowances so a
       row that quietly loses its `whenAbsent` shows up by name, and so
       does one that acquires a default for a field the schema requires —
       which would be the page inventing a threshold. */
    const silent = rows
      .filter((field) => describeCondition(field, undefined, t).state === "undeclared")
      .map((field) => field.path);
    expect(silent.sort()).toEqual([...REQUIRED_WITH_NO_DEFAULT].sort());
  });

  it("keeps the sensing card on the old rule", () => {
    /* Decided deliberately and worth pinning: a noise amplitude has a
       schema default of zero too, but zero there is the statement that
       the site was measured as silent, and the seven amplitudes are the
       difference between a run under a drift somebody chose and a run
       under a drift nobody noticed. */
    const sensing = CONDITION_GROUPS.find((group) => group.tone === "sensing");
    expect(sensing).toBeDefined();
    for (const field of sensing?.fields ?? []) {
      expect(field.whenAbsent, `${field.path} acquired a fallback`).toBeUndefined();
    }
  });
});

describe("reading a value off a stored profile", () => {
  const t = (key: string) => key;
  const profile = {
    id: "warehouse_a",
    constraints: { success_rate_min: 0.95 },
    environment: { sensor_noise: { lidar_range_sigma_m: 0.02 } },
  };
  const mission = { id: "aisle_run", start: [1, 2, 0] };

  const rowFor = (path: string) => {
    const found = ALL_ROWS.find((field) => field.path === path);
    expect(found, `${path} has no row`).toBeDefined();
    return found as ConditionField;
  };

  it("walks a nested path without throwing on a gap", () => {
    expect(
      describeCondition(
        rowFor("environment.sensor_noise.lidar_range_sigma_m"),
        conditionValue(profile, mission, rowFor("environment.sensor_noise.lidar_range_sigma_m")),
        t,
      ),
    ).toEqual({ state: "value", text: "0.02 m" });
    expect(conditionValue(profile, mission, rowFor("hardware.available_ram_mb"))).toBeUndefined();
  });

  it("reads a mission row off the mission the reader picked", () => {
    /* Not `missions[0]`: the page lets a reader choose which mission to
       watch, and a card describing a different one would be describing a
       different episode. */
    expect(conditionValue(profile, mission, rowFor("mission.id"))).toBe("aisle_run");
    expect(describeCondition(rowFor("mission.start"), conditionValue(profile, mission, rowFor("mission.start")), t)).toEqual({
      state: "value",
      text: "1.00, 2.00 m",
    });
  });
});
