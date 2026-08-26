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

import { Hint } from "@/components/Hint";
import { useTranslation } from "@/lib/i18n";
import {
  MOTION_KINDS,
  type MotionKind,
  type StopMode,
  type TrafficPlacement,
  cycleSeconds,
  defaultSeedTimeOffset,
  dropLastWaypoint,
  headingDegrees,
  numberFromInput,
  offsetHint,
  parkedFromTheStart,
  placementsFor,
  stopMode,
  updateObstacle,
  withStopMode,
} from "@/lib/traffic";
import type { DynamicObstacle, Motion } from "@/lib/types";

/** Which obstacle field the next map click writes.
 *  Null means the map is placing the mission instead.
 *
 * This used to be called the *selection*, and carried both meanings at
 * once — which obstacle is highlighted and what the next click does. A
 * click on an obstacle's body means "selected, placing nothing", and
 * that state had no legal value under the old shape. The split lives in
 * `lib/trafficUi`; this component just renders both halves. */
export interface TrafficPlacementState {
  index: number;
  mode: TrafficPlacement;
}

export interface TrafficEditorProps {
  obstacles: DynamicObstacle[];
  /** Identity-preserving edits only — a field typed into a row. The
   *  edits that change what the indexes *mean* (add, remove, motion
   *  law) go through their own intents below, because the caller owns
   *  ui-state that must move with them. */
  onChange: (next: DynamicObstacle[]) => void;
  /** Highlighted row. Distinct from `placement`: an obstacle can be
   *  selected while the map places nothing. */
  selectedIndex: number | null;
  placement: TrafficPlacementState | null;
  onSelect: (index: number | null) => void;
  /** The caller flips between begin/end — this component does not know
   *  what is currently active beyond what `placement` says. */
  onPlacementToggle: (index: number, mode: TrafficPlacement) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onKindChange: (index: number, kind: MotionKind) => void;
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
  "sudden-stop-point": "deployments.form.traffic.place.suddenPoint",
};

export function TrafficEditor({
  obstacles,
  onChange,
  selectedIndex,
  placement,
  onSelect,
  onPlacementToggle,
  onAdd,
  onRemove,
  onKindChange,
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
      <span>
        {label}
        {options.note ? <Hint text={options.note} label={label} /> : null}
      </span>
      <input
        type="number"
        step={options.step ?? 0.1}
        /* An emptied box holds `NaN` — see `numberFromInput`, which is
           what puts it there rather than the zero `Number("")` would
           give. Rendered as the empty box it already is: `value={NaN}`
           draws nothing anyway and warns, and the warning is the only
           thing that told the two states apart. */
        value={value === undefined || !Number.isFinite(value) ? "" : value}
        disabled={disabled}
        onChange={(event) => onNumber(numberFromInput(event.target.value))}
      />
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
            {/* Both boxes say what happens at the *end* of the route,
                which is the thing neither name gives away: "loop" and
                "ping-pong" are only distinguishable to somebody who
                already knows, and leaving both unticked is a third
                behaviour nothing on screen mentioned at all. */}
            <label className="field" style={{ width: 120 }}>
              <span>
                {t("deployments.form.traffic.loop")}
                <Hint
                  text={t("deployments.form.traffic.loopNote")}
                  label={t("deployments.form.traffic.loop")}
                />
              </span>
              <input
                type="checkbox"
                checked={motion.loop ?? false}
                disabled={disabled}
                onChange={(event) => patchMotion(index, { ...motion, loop: event.target.checked })}
              />
            </label>
            <label className="field" style={{ width: 140 }}>
              <span>
                {t("deployments.form.traffic.pingPong")}
                <Hint
                  text={t("deployments.form.traffic.pingPongNote")}
                  label={t("deployments.form.traffic.pingPong")}
                />
              </span>
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
      case "sudden_stop": {
        /* Two ways to say where it ends, and the picker is what makes
           them exclusive on screen as well as in the contract: showing
           both sets of fields would offer a document the server
           refuses, and greying one out would suggest the numbers in it
           still count. */
        const mode = stopMode(motion);
        return (
          <>
            {numberField(t("deployments.form.traffic.speed"), motion.speed, (speed) =>
              patchMotion(index, { ...motion, speed }),
            )}
            <label className="field" style={{ width: 190 }}>
              <span>
                {t("deployments.form.traffic.stopMode")}
                <Hint
                  text={t("deployments.form.traffic.stopModeNote")}
                  label={t("deployments.form.traffic.stopMode")}
                />
              </span>
              <select
                value={mode}
                disabled={disabled}
                onChange={(event) => {
                  onSelect(index);
                  patchMotion(index, withStopMode(motion, event.target.value as StopMode));
                }}
              >
                <option value="time">{t("deployments.form.traffic.stopMode.time")}</option>
                <option value="point">{t("deployments.form.traffic.stopMode.point")}</option>
              </select>
            </label>
            {mode === "time" ? (
              <>
                {numberField(
                  t("deployments.form.traffic.stopTime"),
                  motion.stop_time ?? undefined,
                  (stop_time) => patchMotion(index, { ...motion, stop_time }),
                )}
                {numberField(
                  t("deployments.form.traffic.heading"),
                  Number(headingDegrees(motion.heading ?? 0).toFixed(1)),
                  (degrees) =>
                    patchMotion(index, { ...motion, heading: (degrees * Math.PI) / 180 }),
                  { step: 1, note: t("deployments.form.traffic.headingNote") },
                )}
              </>
            ) : (
              /* Read-only on purpose: the point is placed by clicking
                 the map, which is the whole reason this mode exists.
                 Two number boxes for it would be the arithmetic the
                 mode was added to avoid, in a second place. */
              <span className="muted">
                {t("deployments.form.traffic.stopsAt", {
                  x: (motion.stop_point?.x ?? 0).toFixed(1),
                  y: (motion.stop_point?.y ?? 0).toFixed(1),
                })}
              </span>
            )}
          </>
        );
      }
    }
  };

  return (
    <>
      <h4>
        {t("deployments.form.traffic.title")}
        <Hint
          text={t("deployments.form.traffic.note")}
          label={t("deployments.form.traffic.title")}
        />
      </h4>

      {/* Every traffic rule the server states as a model validator lands
          here, addressed to `environment`, because that is where those
          validators live. A block with nowhere to show them would hide
          all five. */}
      {blockErrors.map((entry) => (
        <p key={`${entry.path}:${entry.message}`} className="notice notice--warn">
          {entry.message}
        </p>
      ))}

      {obstacles.length === 0 ? (
        <p className="muted">{t("deployments.form.traffic.empty")}</p>
      ) : null}

      {obstacles.map((obstacle, index) => {
        const hint = offsetHint(obstacle.motion);
        const mine = rowErrors(index);
        const chosen = selectedIndex === index;
        const parked = parkedFromTheStart(obstacle.motion, obstacle.seed_time_offset);
        return (
          <div
            key={index}
            className="card"
            /* Clicking the *background* of a row focuses it — the same
               selection a click on the obstacle's body on the map makes,
               one highlight reachable two ways.
             *
             * **A click on a control inside it is not that click**, and
             * treating it as one broke the feature outright. Arming a
             * placement dispatches `beginPlacement`; the event then
             * bubbled to here, where `chosen` was still the previous
             * render's `false`, and the `select` that followed cleared
             * the placement a millisecond after the button set it. The
             * button lit up and the next click on the map moved the
             * robot's start instead of the obstacle's — the symptom
             * being a form that ignores its own toolbar. */
            onClick={(event) => {
              if (disabled || chosen) return;
              const target = event.target as HTMLElement;
              if (target.closest("button, input, select, textarea, label")) return;
              onSelect(index);
            }}
            aria-current={chosen ? "true" : undefined}
            style={{
              marginTop: 8,
              padding: 12,
              ...(chosen ? { outline: "2px solid #4c9aff", outlineOffset: -2 } : {}),
            }}
          >
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
                  onChange={(event) => onKindChange(index, event.target.value as MotionKind)}
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
                onClick={(event) => {
                  // Not also a row-click: selecting the row about to
                  // vanish would fight the caller's own reindexing.
                  event.stopPropagation();
                  onRemove(index);
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
                { width: 190, note: t("deployments.form.traffic.seedTimeOffsetNote") },
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
                /* Not behind a mark: this one is not a description of
                   the field, it is *why there is no number to offer for
                   this obstacle* — an answer to a button the author
                   just looked for and did not find. */
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
              {placementsFor(obstacle.motion).map((mode) => {
                const active = placement?.index === index && placement.mode === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    disabled={disabled}
                    className={active ? "active" : undefined}
                    aria-pressed={active}
                    onClick={() => onPlacementToggle(index, mode)}
                  >
                    {t(PLACEMENT_LABEL[mode])}
                  </button>
                );
              })}
            </div>

            {/* **A consequence of two numbers, so it goes on the page
                rather than behind a mark.** With a head start longer
                than the trip, some seeds begin after the obstacle has
                already braked — it sits at its stopping place and
                never moves, which reads as broken traffic rather than
                as declared traffic. Not a refusal: the shipped
                `sudden_stop` scenario does exactly this on purpose. */}
            {parked !== null ? (
              <div className="notice notice--warn" style={{ marginTop: 6 }}>
                {t("deployments.form.traffic.parkedFromTheStart", {
                  percent: String(Math.round(parked * 100)),
                  seconds: String(cycleSeconds(obstacle.motion) ?? 0),
                })}
                {/* A way out, not just a diagnosis. Reading that a
                    quarter of the seeds start with the obstacle parked
                    and being left to work out what number fixes it is
                    only half an answer. */}
                {defaultSeedTimeOffset(obstacle.motion) !== null ? (
                  <div className="toolbar" style={{ marginTop: 6 }}>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() =>
                        onChange(
                          updateObstacle(obstacles, index, {
                            seed_time_offset: defaultSeedTimeOffset(obstacle.motion) ?? undefined,
                          }),
                        )
                      }
                    >
                      {t("deployments.form.traffic.parkedFix", {
                        seconds: String(defaultSeedTimeOffset(obstacle.motion)),
                      })}
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* What the server said about this obstacle in particular. A
                field constraint keeps its own address, so it belongs
                beside the row it names rather than in the block's pile. */}
            {mine.map((entry) => (
              <p key={`${entry.path}:${entry.message}`} className="notice notice--warn">
                {entry.path.split(".").slice(3).join(".")}: {entry.message}
              </p>
            ))}
          </div>
        );
      })}

      <div className="toolbar" style={{ marginTop: 8 }}>
        <button type="button" disabled={disabled} onClick={onAdd}>
          {t("deployments.form.traffic.add")}
        </button>
        <Hint
          text={t("deployments.form.traffic.flatOnly")}
          label={t("deployments.form.traffic.title")}
        />
      </div>
    </>
  );
}

/** The caption for whichever traffic field the map is placing. */
export function placementNote(
  placement: TrafficPlacementState | null,
  obstacles: DynamicObstacle[],
  t: (key: string, vars?: Record<string, string | number>) => string,
): string | undefined {
  if (!placement) return undefined;
  const name = obstacles[placement.index]?.name ?? "";
  const key: Record<TrafficPlacement, string> = {
    waypoint: "deployments.form.traffic.mode.waypoint",
    "periodic-start": "deployments.form.traffic.mode.periodicStart",
    "periodic-end": "deployments.form.traffic.mode.periodicEnd",
    "random-walk-origin": "deployments.form.traffic.mode.origin",
    "sudden-stop-start": "deployments.form.traffic.mode.suddenStart",
    "sudden-stop-heading": "deployments.form.traffic.mode.suddenHeading",
    "sudden-stop-point": "deployments.form.traffic.mode.suddenPoint",
  };
  return t(key[placement.mode], { name });
}
