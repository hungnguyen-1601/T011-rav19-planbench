"use client";

/** Declaring the moving traffic a deployment runs against.
 *
 * **Why this had to exist.** The form already carried traffic: choosing
 * a library scenario copied its obstacles into the deployment, which is
 * what stopped `sudden_stop` producing a deployment with an empty lane.
 * Carrying is not authoring, though — a map somebody drew arrived with
 * no traffic and no way to add any, and the only place to write a cart
 * was the YAML tab or the retiring scenario editor. That mattered beyond
 * convenience: with no traffic *and* no noise, a deterministic planner
 * replays one episode per seed, so 300 runs carry the information of one
 * and G2's collision bound rests on a sample of one.
 *
 * **This component decides nothing.** It offers shapes and defaults; the
 * refusals come from `TaskProfile` on the server, asked for by name
 * through `POST /task-profiles/validate`. The one thing worth knowing
 * about those refusals is where they land: every traffic rule — unique
 * names, a seed head start, a full period, a declared closing speed, a
 * shared clock — is a model validator on `EnvironmentSpec`, so pydantic
 * addresses it to `environment` and not to the obstacle that caused it.
 * That is why the message renders once at the top of this block rather
 * than beside a row. Without somewhere to put it, all five refusals
 * would be invisible.
 */

import type { ReactNode } from "react";

import { useTranslation } from "@/lib/i18n";
import {
  MOTION_KINDS,
  PLACEMENTS,
  type MotionKind,
  type TrafficPlacement,
  addObstacle,
  changeMotionKind,
  dropLastWaypoint,
  headingDegrees,
  offsetHint,
  removeObstacle,
  updateObstacle,
} from "@/lib/traffic";
import type { DynamicObstacle, Motion, Point2D } from "@/lib/types";

/** Which obstacle the next map click belongs to, and which of its fields.
 *  Null means the map is placing the mission instead. */
export interface TrafficSelection {
  index: number;
  mode: TrafficPlacement;
}

export interface TrafficEditorProps {
  obstacles: DynamicObstacle[];
  onChange: (next: DynamicObstacle[]) => void;
  selection: TrafficSelection | null;
  onSelect: (selection: TrafficSelection | null) => void;
  /** Where a new obstacle appears: somewhere the author is already
   *  looking, rather than the map's origin behind a wall. */
  anchor: Point2D;
  disabled?: boolean;
  /** Every refusal the server addressed to this block — `environment`
   *  itself and anything under it.
   *
   * All of them, not just the block-level one. Pydantic addresses what
   * it can: a rule written as a model validator lands on `environment`,
   * while a field constraint lands on
   * `environment.dynamic_obstacles.0.radius`. Taking only the first kind
   * left the second with nowhere to render, so a refused document
   * blocked filing while showing the author nothing. */
  errors: { path: string; message: string }[];
}

const KIND_LABEL: Record<MotionKind, string> = {
  waypoint: "deployments.form.traffic.kind.waypoint",
  periodic: "deployments.form.traffic.kind.periodic",
  random_walk: "deployments.form.traffic.kind.randomWalk",
  sudden_stop: "deployments.form.traffic.kind.suddenStop",
};

const PLACEMENT_LABEL: Record<TrafficPlacement, string> = {
  waypoint: "deployments.form.traffic.place.waypoint",
  "periodic-start": "deployments.form.traffic.place.periodicStart",
  "periodic-end": "deployments.form.traffic.place.periodicEnd",
  "random-walk-origin": "deployments.form.traffic.place.origin",
  "sudden-stop-start": "deployments.form.traffic.place.suddenStart",
  "sudden-stop-heading": "deployments.form.traffic.place.suddenHeading",
};

export function TrafficEditor({
  obstacles,
  onChange,
  selection,
  onSelect,
  anchor,
  disabled = false,
  errors,
}: TrafficEditorProps) {
  const { t } = useTranslation();

  /** Refusals that name one obstacle, keyed by its position. */
  const rowErrors = (index: number) =>
    errors.filter((entry) => entry.path.startsWith(`environment.dynamic_obstacles.${index}.`));

  /** Everything else this block was told: the model-level rules, and
   *  anything under `environment` that no row here claims. Rendered
   *  rather than filtered away — an unrecognised address is still a
   *  reason somebody's document was refused. */
  const blockErrors = errors.filter(
    (entry) =>
      !obstacles.some((_, index) =>
        entry.path.startsWith(`environment.dynamic_obstacles.${index}.`),
      ),
  );

  const patchMotion = (index: number, motion: Motion) =>
    onChange(updateObstacle(obstacles, index, { motion }));

  const numberField = (
    label: string,
    value: number | undefined,
    onNumber: (next: number) => void,
    options: { step?: number; note?: string; width?: number } = {},
  ) => (
    <label className="field" style={{ width: options.width ?? 120 }}>
      <span>{label}</span>
      <input
        type="number"
        step={options.step ?? 0.1}
        /* A half-typed field parses to NaN, and NaN in `value` is an
           empty box plus a React warning — so it is shown as the empty
           box it already looks like. The number is not corrected on the
           way in: what is legal here is the server's to say, and a form
           that quietly replaced NaN with a plausible figure would be
           filing a deployment nobody typed. */
        value={value === undefined || !Number.isFinite(value) ? "" : value}
        disabled={disabled}
        onChange={(event) => onNumber(Number(event.target.value))}
      />
      {options.note ? <small className="muted">{options.note}</small> : null}
    </label>
  );

  /** The fields one motion law has, and only those.
   *
   * Rendered per kind rather than as a union of every field with the
   * inapplicable ones greyed out: a disabled `period` box beside a
   * waypoint route reads as a number that exists and happens to be
   * unavailable, and it is neither. */
  const motionFields = (obstacle: DynamicObstacle, index: number): ReactNode => {
    const motion = obstacle.motion;
    switch (motion.kind) {
      case "waypoint":
        return (
          <>
            {numberField(t("deployments.form.traffic.speed"), motion.speed, (speed) =>
              patchMotion(index, { ...motion, speed }),
            )}
            <div className="field">
              <span>{t("deployments.form.traffic.waypoints")}</span>
              <div className="row" style={{ gap: 6, alignItems: "center" }}>
                <span className="muted">
                  {t("deployments.form.traffic.waypointCount", { n: motion.waypoints.length })}
                </span>
                <button
                  type="button"
                  disabled={disabled || motion.waypoints.length === 0}
                  onClick={() => patchMotion(index, dropLastWaypoint(motion))}
                >
                  {t("deployments.form.traffic.undoWaypoint")}
                </button>
              </div>
            </div>
            <label className="field" style={{ width: 120 }}>
              <span>{t("deployments.form.traffic.loop")}</span>
              <input
                type="checkbox"
                checked={motion.loop ?? false}
                disabled={disabled}
                onChange={(event) => patchMotion(index, { ...motion, loop: event.target.checked })}
              />
            </label>
            <label className="field" style={{ width: 140 }}>
              <span>{t("deployments.form.traffic.pingPong")}</span>
              <input
                type="checkbox"
                checked={motion.ping_pong ?? false}
                disabled={disabled}
                onChange={(event) =>
                  patchMotion(index, { ...motion, ping_pong: event.target.checked })
                }
              />
            </label>
          </>
        );
      case "periodic":
        return (
          <>
            {numberField(t("deployments.form.traffic.period"), motion.period, (period) =>
              patchMotion(index, { ...motion, period }),
            )}
            {numberField(t("deployments.form.traffic.phase"), motion.phase ?? 0, (phase) =>
              patchMotion(index, { ...motion, phase }),
            )}
            <span className="muted">
              ({motion.start.x.toFixed(1)}, {motion.start.y.toFixed(1)}) ↔ (
              {motion.end.x.toFixed(1)}, {motion.end.y.toFixed(1)})
            </span>
          </>
        );
      case "random_walk":
        return (
          <>
            {numberField(t("deployments.form.traffic.speed"), motion.speed, (speed) =>
              patchMotion(index, { ...motion, speed }),
            )}
            {numberField(
              t("deployments.form.traffic.changeInterval"),
              motion.change_interval,
              (change_interval) => patchMotion(index, { ...motion, change_interval }),
            )}
            {numberField(t("deployments.form.traffic.maxRadius"), motion.max_radius, (max_radius) =>
              patchMotion(index, { ...motion, max_radius }),
            )}
            {numberField(
              t("deployments.form.traffic.walkSeed"),
              motion.seed_offset ?? 0,
              (seed_offset) => patchMotion(index, { ...motion, seed_offset }),
              { step: 1, note: t("deployments.form.traffic.walkSeedNote") },
            )}
          </>
        );
      case "sudden_stop":
        return (
          <>
            {numberField(t("deployments.form.traffic.speed"), motion.speed, (speed) =>
              patchMotion(index, { ...motion, speed }),
            )}
            {numberField(t("deployments.form.traffic.stopTime"), motion.stop_time, (stop_time) =>
              patchMotion(index, { ...motion, stop_time }),
            )}
            {numberField(
              t("deployments.form.traffic.heading"),
              Number(headingDegrees(motion.heading).toFixed(1)),
              (degrees) => patchMotion(index, { ...motion, heading: (degrees * Math.PI) / 180 }),
              { step: 1, note: t("deployments.form.traffic.headingNote") },
            )}
          </>
        );
    }
  };

  return (
    <>
      <h4>{t("deployments.form.traffic.title")}</h4>
      <p className="muted">{t("deployments.form.traffic.note")}</p>

      {/* Every traffic rule the server states as a model validator lands
          here, addressed to `environment`, because that is where those
          validators live. A block with nowhere to show them would hide
          all five. */}
      {blockErrors.map((entry) => (
        <p key={`${entry.path}:${entry.message}`} className="notice warn">
          {entry.message}
        </p>
      ))}

      {obstacles.length === 0 ? (
        <p className="muted">{t("deployments.form.traffic.empty")}</p>
      ) : null}

      {obstacles.map((obstacle, index) => {
        const hint = offsetHint(obstacle.motion);
        const mine = rowErrors(index);
        return (
          <div key={index} className="card" style={{ marginTop: 8, padding: 12 }}>
            <div className="row" style={{ gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
              <label className="field" style={{ width: 160 }}>
                <span>{t("deployments.form.traffic.name")}</span>
                <input
                  value={obstacle.name}
                  disabled={disabled}
                  onChange={(event) =>
                    onChange(updateObstacle(obstacles, index, { name: event.target.value }))
                  }
                />
              </label>
              {numberField(t("deployments.form.traffic.radius"), obstacle.radius, (radius) =>
                onChange(updateObstacle(obstacles, index, { radius })),
              )}
              <label className="field" style={{ width: 180 }}>
                <span>{t("deployments.form.traffic.kind")}</span>
                <select
                  value={obstacle.motion.kind}
                  disabled={disabled}
                  onChange={(event) => {
                    onSelect(null);
                    onChange(
                      obstacles.map((each, at) =>
                        at === index
                          ? changeMotionKind(each, event.target.value as MotionKind, anchor)
                          : each,
                      ),
                    );
                  }}
                >
                  {MOTION_KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {t(KIND_LABEL[kind])}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                disabled={disabled}
                onClick={() => {
                  onSelect(null);
                  onChange(removeObstacle(obstacles, index));
                }}
              >
                {t("deployments.form.traffic.remove")}
              </button>
            </div>

            <div
              className="row"
              style={{ gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}
            >
              {motionFields(obstacle, index)}
            </div>

            <div className="row" style={{ gap: 12, alignItems: "flex-end", marginTop: 8 }}>
              {numberField(
                t("deployments.form.traffic.seedTimeOffset"),
                obstacle.seed_time_offset,
                (seed_time_offset) =>
                  onChange(updateObstacle(obstacles, index, { seed_time_offset })),
                { width: 170 },
              )}
              {/* A suggestion, not a rule: one full cycle is what makes
                  different seeds meet this obstacle at different points
                  of its route. When there is no number to offer, *why*
                  there is none decides what to say — a random walk is
                  seeded through its headings and may legitimately sit at
                  zero, which is the opposite of what a route driven once
                  needs to hear. */}
              {hint.kind === "suggestion" ? (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    onChange(
                      updateObstacle(obstacles, index, { seed_time_offset: hint.seconds }),
                    )
                  }
                >
                  {t("deployments.form.traffic.seedTimeOffsetSuggest")} ({hint.seconds}s)
                </button>
              ) : (
                <small className="muted" style={{ maxWidth: 320 }}>
                  {t(`deployments.form.traffic.seedTimeOffset.${hint.kind}`)}
                </small>
              )}
              {numberField(
                t("deployments.form.traffic.obstacleSeed"),
                obstacle.seed_offset ?? 0,
                (seed_offset) => onChange(updateObstacle(obstacles, index, { seed_offset })),
                { step: 1, width: 150, note: t("deployments.form.traffic.obstacleSeedNote") },
              )}
            </div>

            {/* One button per field this motion has a point for, so a
                sudden stop never offers an end it does not own. */}
            <div className="toolbar" style={{ marginTop: 8 }}>
              {PLACEMENTS[obstacle.motion.kind].map((mode) => {
                const active = selection?.index === index && selection.mode === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    disabled={disabled}
                    className={active ? "active" : undefined}
                    aria-pressed={active}
                    onClick={() => onSelect(active ? null : { index, mode })}
                  >
                    {t(PLACEMENT_LABEL[mode])}
                  </button>
                );
              })}
            </div>

            {/* What the server said about this obstacle in particular. A
                field constraint keeps its own address, so it belongs
                beside the row it names rather than in the block's pile. */}
            {mine.map((entry) => (
              <p key={`${entry.path}:${entry.message}`} className="notice warn">
                {entry.path.split(".").slice(3).join(".")}: {entry.message}
              </p>
            ))}
          </div>
        );
      })}

      <div className="toolbar" style={{ marginTop: 8 }}>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(addObstacle(obstacles, anchor))}
        >
          {t("deployments.form.traffic.add")}
        </button>
      </div>
      <p className="muted">{t("deployments.form.traffic.flatOnly")}</p>
    </>
  );
}

/** The caption for whichever traffic field the map is placing. */
export function placementNote(
  selection: TrafficSelection | null,
  obstacles: DynamicObstacle[],
  t: (key: string, vars?: Record<string, string | number>) => string,
): string | undefined {
  if (!selection) return undefined;
  const name = obstacles[selection.index]?.name ?? "";
  const key: Record<TrafficPlacement, string> = {
    waypoint: "deployments.form.traffic.mode.waypoint",
    "periodic-start": "deployments.form.traffic.mode.periodicStart",
    "periodic-end": "deployments.form.traffic.mode.periodicEnd",
    "random-walk-origin": "deployments.form.traffic.mode.origin",
    "sudden-stop-start": "deployments.form.traffic.mode.suddenStart",
    "sudden-stop-heading": "deployments.form.traffic.mode.suddenHeading",
  };
  return t(key[selection.mode], { name });
}
