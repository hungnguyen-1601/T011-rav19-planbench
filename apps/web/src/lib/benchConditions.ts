/** Everything a deployment declares, laid out as seven groups.
 *
 * **Why this is a table and not JSX.** The test bench used to show four
 * hand-written cards covering eleven of the profile's fields; the other
 * thirty were simply not on the page, and nothing anywhere said so. A
 * reader checking a configuration before spending two hours of machine
 * time on it was checking a quarter of it. Rows written by hand cannot
 * be audited — a field added to `TaskProfile` next month would be
 * missing here and no test could tell. Declared as data, the inventory
 * can be compared against the schema itself, which is what
 * `bench-conditions.test.ts` does: a field added to the contract and not
 * placed in a group turns that test red.
 *
 * **The grouping, and the two judgements in it.** HĐ-2 gives eleven
 * top-level keys and no grouping; seven cards is a reading decision.
 * Five of them are the schema's own blocks (mission, robot, thresholds,
 * environment, sensing). The other two are the judgements:
 *
 * - **Scope** collects the four keys that describe *what this deployment
 *   is* rather than what it contains — `id`, `claim_level`,
 *   `deployment_role`, `min_episodes_before_stop`. They had no card at
 *   all before, which is how a reader could watch an episode of an
 *   `instrument` deployment believing it was a customer site.
 * - **Behaviour** holds `replanning`, `recovery` and
 *   `clearance_preference` together, because all three are the same kind
 *   of statement: a rule the deployment applies identically to every
 *   candidate, which is exactly why none of them lives on the candidate
 *   (HĐ-4.1). Splitting replanning from recovery would have made eight
 *   cards out of one idea.
 *
 * The target board rides with the robot rather than with the thresholds,
 * where `available_ram_mb` used to sit alone. G4's control period and
 * G5's RAM budget are both about the computer bolted to the vehicle, and
 * the RAM arithmetic — total minus the breakdown leaves available — is
 * only checkable if the four breakdown rows are beside the two numbers
 * they reconcile.
 *
 * **Units live in the value, never in the label.** The deployment form
 * writes `Radius (m)` because it is labelling an input; a read-only row
 * reads better as `Radius … 0.25 m`, and a shared label would have put
 * the unit in both places on half the rows and neither on the rest.
 */

import type { IconName } from "@/components/Icon";
import { poseOf } from "@/lib/deployments";

export type Translate = (key: string, vars?: Record<string, string | number>) => string;

/** How one declared value turns into something a reader can check.
 *
 * `count` and `number` are deliberately different: a missing array and
 * an empty one are `not declared` and `0`, and collapsing them would
 * print a traffic-free site for a profile that never mentioned traffic.
 */
export type ConditionKind =
  | "text"
  | "number"
  | "rate"
  | "flag"
  | "count"
  | "pose"
  | "budget"
  | "tokens"
  | "grants";

/** What a row shows when the stored profile does not carry the field.
 *
 * **Why an absent field can still have an answer.** A profile is filed
 * through `TaskProfile.model_validate` and stored as a full
 * `model_dump(mode="json")`, so every default is written down at filing
 * time; a key is missing only when the profile predates the field. The
 * episode still ran, and it ran under the schema default — `replanning`
 * off, `clearance_preference` 4.0, `no_path_rate_max` 0.02. This card
 * says *"conditions kept unchanged for this episode"*, so those are the
 * conditions, and printing `not declared` beside them would answer a
 * question about the paperwork while every other row answers a question
 * about the run.
 *
 * **The two silences are not the same silence**, which is the whole
 * reason this is a tagged union rather than a default value:
 *
 * - `effective` — the schema names a value, so the run had one.
 * - `unbounded` — `None` is the contract's own meaning and there is no
 *   number behind it. `v_obstacle_max: null` makes the loader skip its
 *   braking check outright (`task_profile.py`), so rendering `0` would
 *   assert that nothing at the site ever moves — the opposite claim, and
 *   the one the schema says is refused beside declared traffic.
 */
export type ConditionAbsence =
  | { kind: "effective"; value: unknown }
  | { kind: "unbounded"; textKey: string };

export interface ConditionField {
  /** Dotted path into the stored profile. `mission.` reads the mission
   *  the reader picked, not `missions[0]`. */
  path: string;
  labelKey: string;
  kind: ConditionKind;
  /** Appended to the rendered number. Omitted where the quantity has
   *  none — a count, a probability, a ratio. */
  unit?: string;
  /** What the episode ran under when the profile omits this field.
   *  Left off where the omission itself is the honest answer — every
   *  row of the sensing card, and every field the schema makes
   *  required, where a gap is a broken record rather than a default. */
  whenAbsent?: ConditionAbsence;
}

export type ConditionTone =
  | "scope"
  | "mission"
  | "robot"
  | "thresholds"
  | "environment"
  | "sensing"
  | "behaviour";

export interface ConditionGroupSpec {
  tone: ConditionTone;
  titleKey: string;
  icon: IconName;
  fields: readonly ConditionField[];
}

/** What a row shows, with `undeclared` as its own state.
 *
 * **The distinction this type exists for.** A row cannot invent a
 * value the reader would take for a decision somebody made. Absence is
 * therefore a state rather than a silent fallback, and where a field
 * genuinely has no answer — every row of the sensing card — the
 * renderer says so out loud.
 *
 * **Where it does not apply, and why that is not a retreat.** The
 * environment, threshold and behaviour cards resolve an absent field
 * through {@link ConditionAbsence} instead. That is not the renderer
 * guessing: the schema *names* those values, the episode ran under
 * them, and this card's own heading promises the conditions the episode
 * ran under. The thing to protect against was never showing a default —
 * it was showing `0` where the contract means *no commitment at all*,
 * and that case is now spelled out per field rather than left to a
 * blanket rule that also swallowed the answerable ones.
 */
export type ConditionDisplay =
  | { state: "undeclared" }
  | { state: "on" }
  | { state: "off" }
  | { state: "value"; text: string };

export const UNDECLARED: ConditionDisplay = { state: "undeclared" };

/** The seven groups, in reading order. */
export const CONDITION_GROUPS: readonly ConditionGroupSpec[] = [
  {
    tone: "scope",
    titleKey: "bench.conditionsScope",
    icon: "library",
    fields: [
      { path: "id", labelKey: "bench.cond.id", kind: "text" },
      { path: "claim_level", labelKey: "bench.cond.claimLevel", kind: "text" },
      { path: "deployment_role", labelKey: "bench.cond.role", kind: "text" },
      {
        path: "min_episodes_before_stop",
        labelKey: "bench.cond.minEpisodes",
        kind: "number",
      },
    ],
  },
  {
    tone: "mission",
    titleKey: "bench.conditionsMission",
    icon: "map",
    fields: [
      { path: "mission.id", labelKey: "bench.cond.missionId", kind: "text" },
      { path: "mission.start", labelKey: "simulate.start", kind: "pose" },
      { path: "mission.goal", labelKey: "simulate.goal", kind: "pose" },
      { path: "mission.probability", labelKey: "bench.cond.probability", kind: "rate" },
      { path: "missions", labelKey: "bench.cond.missions", kind: "count" },
      {
        path: "constraints.goal_tolerance_m",
        labelKey: "bench.tolerance",
        kind: "number",
        unit: "m",
      },
      {
        path: "constraints.goal_tolerance_rad",
        labelKey: "bench.cond.goalToleranceRad",
        kind: "number",
        unit: "rad",
      },
      {
        path: "constraints.episode_timeout_s",
        labelKey: "library.timeout",
        kind: "number",
        unit: "s",
      },
    ],
  },
  {
    tone: "robot",
    titleKey: "bench.conditionsRobot",
    icon: "cpu",
    fields: [
      { path: "robot.type", labelKey: "bench.cond.robotType", kind: "text" },
      { path: "robot.radius", labelKey: "simulate.robotRadius", kind: "number", unit: "m" },
      {
        path: "robot.max_linear_velocity",
        labelKey: "simulate.maxSpeed",
        kind: "number",
        unit: "m/s",
      },
      {
        path: "robot.max_angular_velocity",
        labelKey: "bench.cond.maxTurn",
        kind: "number",
        unit: "rad/s",
      },
      {
        path: "robot.max_linear_acceleration",
        labelKey: "bench.cond.maxAccel",
        kind: "number",
        unit: "m/s²",
      },
      {
        path: "robot.max_angular_acceleration",
        labelKey: "bench.cond.maxAngularAccel",
        kind: "number",
        unit: "rad/s²",
      },
      { path: "robot.control_period", labelKey: "bench.controlPeriod", kind: "number", unit: "s" },
      { path: "hardware.target_device", labelKey: "bench.cond.targetDevice", kind: "text" },
      { path: "hardware.total_ram_mb", labelKey: "bench.cond.totalRam", kind: "number", unit: "MB" },
      {
        path: "hardware.ram_budget_breakdown.os_and_middleware_mb",
        labelKey: "deployments.form.ramOs",
        kind: "number",
        unit: "MB",
      },
      {
        path: "hardware.ram_budget_breakdown.perception_stack_mb",
        labelKey: "deployments.form.ramPerception",
        kind: "number",
        unit: "MB",
      },
      {
        path: "hardware.ram_budget_breakdown.localization_mapping_mb",
        labelKey: "deployments.form.ramLocalisation",
        kind: "number",
        unit: "MB",
      },
      {
        path: "hardware.ram_budget_breakdown.logging_and_reserve_mb",
        labelKey: "deployments.form.ramLogging",
        kind: "number",
        unit: "MB",
      },
      /* G5's threshold. It stays with the board it is an allocation on
         rather than with the thresholds, because it is only checkable
         beside the total and the breakdown it is the remainder of. */
      {
        path: "hardware.available_ram_mb",
        labelKey: "deployments.form.availableRam",
        kind: "number",
        unit: "MB",
      },
    ],
  },
  {
    /* **The numbers the episode will be judged against.** The other
       cards say what the world *is*. None of them says what counts as a
       pass, and that is the half a reader watching one episode is
       actually checking it against: a run that reaches the goal is not a
       run that cleared G3 unless the success floor is known. */
    tone: "thresholds",
    titleKey: "bench.conditionsThresholds",
    icon: "benchmark",
    fields: [
      {
        path: "constraints.success_rate_min",
        labelKey: "bench.cond.successMin",
        kind: "rate",
      },
      {
        path: "constraints.collision_probability_max",
        labelKey: "bench.cond.risk",
        kind: "rate",
      },
      {
        /* `TaskConstraints.no_path_rate_max` defaults to 0.02, so G1 held
           a pre-field profile to 2 % whether or not it said so. */
        path: "constraints.no_path_rate_max",
        labelKey: "bench.cond.noPathMax",
        kind: "rate",
        whenAbsent: { kind: "effective", value: 0.02 },
      },
      {
        path: "constraints.stuck_threshold_s",
        labelKey: "bench.cond.stuck",
        kind: "number",
        unit: "s",
      },
      {
        path: "constraints.clearance_warning_m",
        labelKey: "bench.cond.clearanceWarning",
        kind: "number",
        unit: "m",
      },
      {
        /* `float | None = None`, and the null is the point: it is the
           scale `business_adjusted` prices effort against, and the
           schema refuses to invent one for the customer (HĐ-8.3 law 4).
           A `0` here would read as a site that will pay nothing per
           mission, which would fail every candidate rather than
           declining to rank them on money. */
        path: "constraints.cost_per_mission_max",
        labelKey: "bench.cond.costPerMission",
        kind: "number",
        whenAbsent: { kind: "unbounded", textKey: "bench.cond.noCostCeiling" },
      },
    ],
  },
  {
    tone: "environment",
    titleKey: "bench.conditionsEnvironment",
    icon: "sparkles",
    fields: [
      { path: "environment.map", labelKey: "bench.cond.map", kind: "text" },
      { path: "environment.map_yaml", labelKey: "bench.cond.mapYaml", kind: "text" },
      {
        /* `default=()`. A profile that never mentioned traffic ran with
           none, which is a consequential fact rather than a gap: with no
           traffic and no noise a deterministic planner replays one
           episode per seed, and `EnvironmentSpec` spends a paragraph on
           it. `0` is that fact; `not declared` hid it. */
        path: "environment.dynamic_obstacles",
        labelKey: "bench.traffic",
        kind: "count",
        whenAbsent: { kind: "effective", value: [] },
      },
      {
        /* The one field whose docstring enumerates its three meanings,
           and `None` is explicitly *not one of the numbers*: no braking
           claim, validator skipped entirely. `0.0` is the opposite
           assertion — nothing here moves — and the loader refuses it
           beside declared traffic. So this absence gets words. */
        path: "environment.v_obstacle_max",
        labelKey: "bench.cond.vObstacleMax",
        kind: "number",
        unit: "m/s",
        whenAbsent: { kind: "unbounded", textKey: "bench.cond.noBrakingClaim" },
      },
    ],
  },
  {
    tone: "sensing",
    titleKey: "bench.conditionsSensing",
    icon: "globe",
    fields: [
      { path: "available_observations", labelKey: "bench.cond.observations", kind: "tokens" },
      { path: "capability_grants", labelKey: "bench.cond.grants", kind: "grants" },
      {
        path: "environment.sensor_noise.lidar_range_sigma_m",
        labelKey: "decisions.conditions.lidarSigma",
        kind: "number",
        unit: "m",
      },
      {
        path: "environment.sensor_noise.wheel_slip_fraction",
        labelKey: "decisions.conditions.wheelSlip",
        kind: "rate",
      },
      {
        path: "environment.sensor_noise.localization_drift_m",
        labelKey: "bench.cond.localizationDrift",
        kind: "number",
        unit: "m",
      },
      {
        path: "environment.sensor_noise.localization_jump_probability",
        labelKey: "bench.cond.localizationJump",
        kind: "rate",
      },
      {
        path: "environment.sensor_noise.lidar_dropout_probability",
        labelKey: "bench.cond.lidarDropout",
        kind: "rate",
      },
      {
        path: "environment.sensor_noise.odometry_bias_fraction",
        labelKey: "bench.cond.odometryBias",
        kind: "rate",
      },
      {
        path: "environment.sensor_noise.command_latency_steps",
        labelKey: "bench.cond.commandLatency",
        kind: "number",
      },
    ],
  },
  {
    tone: "behaviour",
    titleKey: "bench.conditionsBehaviour",
    icon: "refresh",
    fields: [
      /* All six resolve to the value the episode ran under, because
         `TaskProfile` defaults `replanning` to `NO_REPLANNING` and
         `recovery` to `NO_RECOVERY` — both modules say in as many words
         that a run under the default behaves exactly as the engine did
         before the feature existed. A profile missing these keys is a
         profile filed before them, and it ran off-off. */
      {
        path: "replanning.enabled",
        labelKey: "bench.replanning",
        kind: "flag",
        whenAbsent: { kind: "effective", value: false },
      },
      {
        /* `max_replans` is absent only when the whole `replanning` block
           is, because a filed profile is a complete model dump and the
           two fields shipped together. So this is `NO_REPLANNING`'s
           budget, which `ReplanningConfig` declares as `0` and keeps
           there deliberately: the promotion to unlimited fires only when
           replanning is switched *on* with no budget named, and that
           case arrives as a declared `null` and still reads unlimited. */
        path: "replanning.max_replans",
        labelKey: "replanning.maxReplans",
        kind: "budget",
        whenAbsent: { kind: "effective", value: 0 },
      },
      {
        path: "recovery.enabled",
        labelKey: "bench.cond.recovery",
        kind: "flag",
        whenAbsent: { kind: "effective", value: false },
      },
      {
        /* `default=len(LADDER)` — all four rungs are permitted, and the
           cap only bites once recovery is enabled at all. */
        path: "recovery.max_escalation",
        labelKey: "bench.cond.recoveryEscalation",
        kind: "number",
        whenAbsent: { kind: "effective", value: 4 },
      },
      {
        path: "recovery.max_forgets",
        labelKey: "bench.cond.recoveryForgets",
        kind: "number",
        whenAbsent: { kind: "effective", value: 1 },
      },
      {
        /* `default=4.0`, and the schema's own table shows it is the only
           value that gets both pinned scenarios home. A profile without
           it planned under a boundary metre costing five. */
        path: "clearance_preference",
        labelKey: "bench.cond.clearancePreference",
        kind: "number",
        whenAbsent: { kind: "effective", value: 4.0 },
      },
    ],
  },
] as const;

/** One step of a dotted path, stopping rather than throwing on a gap. */
function readPath(root: unknown, path: string): unknown {
  let cursor: unknown = root;
  for (const segment of path.split(".")) {
    if (cursor === null || typeof cursor !== "object") return undefined;
    cursor = (cursor as Record<string, unknown>)[segment];
  }
  return cursor;
}

/** The raw value behind a field, from the profile or the chosen mission. */
export function conditionValue(
  profile: unknown,
  mission: unknown,
  field: ConditionField,
): unknown {
  return field.path.startsWith("mission.")
    ? readPath(mission, field.path.slice("mission.".length))
    : readPath(profile, field.path);
}

/** A finite number, or nothing. `null` counts as nothing on purpose:
 *  the contract uses it for *no commitment* — `v_obstacle_max` says so
 *  in as many words, and `cost_per_mission_max` refuses rather than
 *  inventing a budget. Neither becomes a zero here; both are given
 *  words instead, by the `unbounded` absence on their rows. */
function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** How a value reads, resolving an absent field to what the episode
 *  actually ran under where the schema names one.
 *
 * Pure, and that is what makes the honesty testable: the assertion that
 * an absent `v_obstacle_max` reads as *no braking claim* rather than as
 * `0 m/s` is one call, with no page, no React and no browser between it
 * and the claim.
 *
 * The fallback runs through the same formatter as a declared value on
 * purpose. A default rendered by a second code path is a default that
 * can drift from the thing it is standing in for — the reader would see
 * `4.0` for an absent `clearance_preference` and `4` for one written
 * down, and be left wondering which deployment they were looking at.
 */
export function describeCondition(
  field: ConditionField,
  raw: unknown,
  t: Translate,
): ConditionDisplay {
  const declared = describeDeclared(field, raw, t);
  if (declared.state !== "undeclared" || field.whenAbsent === undefined) return declared;
  return field.whenAbsent.kind === "unbounded"
    ? { state: "value", text: t(field.whenAbsent.textKey) }
    : describeDeclared(field, field.whenAbsent.value, t);
}

/** What one raw value reads as, with nothing standing in for a gap. */
function describeDeclared(
  field: ConditionField,
  raw: unknown,
  t: Translate,
): ConditionDisplay {
  switch (field.kind) {
    case "flag":
      if (typeof raw !== "boolean") return UNDECLARED;
      return raw ? { state: "on" } : { state: "off" };

    case "number": {
      const value = finite(raw);
      if (value === null) return UNDECLARED;
      return { state: "value", text: field.unit ? `${value} ${field.unit}` : String(value) };
    }

    case "rate": {
      /* One decimal, because `no_path_rate_max` defaults to 0.02 and
         rounding to whole percent would print two thresholds as one. */
      const value = finite(raw);
      return value === null ? UNDECLARED : { state: "value", text: `${(value * 100).toFixed(1)} %` };
    }

    case "budget": {
      /* `max_replans: null` is a declared meaning — unlimited, which is
         what `ReplanningConfig` promotes an unset budget to when
         replanning is switched on. Absent is still absent. */
      if (raw === undefined) return UNDECLARED;
      if (raw === null) return { state: "value", text: t("bench.cond.unlimited") };
      const value = finite(raw);
      return value === null ? UNDECLARED : { state: "value", text: String(value) };
    }

    case "count": {
      if (!Array.isArray(raw)) return UNDECLARED;
      return { state: "value", text: String(raw.length) };
    }

    case "pose": {
      const pose = poseOf(raw);
      return pose === null
        ? UNDECLARED
        : { state: "value", text: `${pose.x.toFixed(2)}, ${pose.y.toFixed(2)} m` };
    }

    case "tokens": {
      if (!Array.isArray(raw)) return UNDECLARED;
      const tokens = raw.filter((entry): entry is string => typeof entry === "string");
      return tokens.length === 0
        ? { state: "value", text: t("bench.cond.none") }
        : { state: "value", text: tokens.join(", ") };
    }

    case "grants": {
      /* A grant is a capability plus who provides it, and the provider's
         own configuration reaches the execution fingerprint (§5.2) — a
         tracker retuned between two sweeps is a different experimental
         condition. So the settings are counted rather than dropped. */
      if (!Array.isArray(raw)) return UNDECLARED;
      if (raw.length === 0) return { state: "value", text: t("bench.cond.none") };
      const grants = raw.map((entry) => {
        const grant = (entry ?? {}) as Record<string, unknown>;
        const config = grant.provider_config;
        const settings =
          config && typeof config === "object" ? Object.keys(config as object).length : 0;
        const suffix = settings > 0 ? ` (${t("bench.cond.settings", { n: settings })})` : "";
        return `${String(grant.capability)} — ${String(grant.provider_id)} ${String(
          grant.provider_version,
        )}${suffix}`;
      });
      return { state: "value", text: grants.join(" · ") };
    }

    case "text":
    default: {
      if (typeof raw !== "string" || raw.trim() === "") return UNDECLARED;
      return { state: "value", text: raw };
    }
  }
}
