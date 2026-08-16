"use client";

/** Say where the robot starts and where it has to get to.
 *
 * **One placer, and the reason is the same as the painter's.** The
 * launch panel on `/decisions` grew this to put a custom map under a
 * comparison; the deployment form needs the identical thing. A second
 * copy would be a second answer to "what does clicking the map do".
 *
 * **Two-way by construction, not by wiring.** The canvas and the number
 * fields hold *no state of their own* — both read and write the same
 * `Pose2D` owned by the caller. Dragging updates the numbers and typing
 * moves the marker because there is only one place the pose lives. The
 * moment somebody adds a local `useState` here "so the input feels
 * snappier", the two halves start disagreeing and one of them wins
 * silently. A test pins this.
 *
 * The only state this component does own is which mode the toolbar is
 * in, and that is a tool selection rather than data.
 */

import { useRef, useState } from "react";

import type { ObstacleMarker } from "@/components/MapCanvas";
import { MapView } from "@/components/MapView";
import { useTranslation } from "@/lib/i18n";
import type { TrafficPlacement } from "@/lib/traffic";
import type { TrafficOverlay } from "@/lib/trafficOverlay";
import type { MapData, ObstacleSnapshot, Point2D, Pose2D } from "@/lib/types";

/** What the next click on the map does.
 *
 * An explicit mode with a button and a caption, the way the scenario
 * editor has always done it, rather than a hidden alternation: the
 * author has to be able to *see* what the next click will do, or nudging
 * a start two pixels lands a goal instead.
 */
export type PlacementMode = "none" | "start" | "goal" | TrafficPlacement;

export const DEGREES = (radians: number) => (radians * 180) / Math.PI;
export const RADIANS = (degrees: number) => (degrees * Math.PI) / 180;

export interface MissionPlacerProps {
  map: MapData;
  /** Null means "not placed yet" — drawn as a line of text rather than a
   *  row of zeroes, because 0,0 is a coordinate somebody could mean. */
  start: Pose2D | null;
  goal: Pose2D | null;
  onChange: (next: { start: Pose2D | null; goal: Pose2D | null }) => void;
  /** The deployment's own numbers, so the preview is to scale: a start
   *  that looks clear at one pixel per cell can be one the robot does
   *  not fit in, and an episode ends the moment the robot is inside the
   *  goal circle. */
  robotRadius?: number;
  /** Safety envelope in metres; see `lib/keepOut`. */
  positionUncertainty?: number;
  goalTolerance?: number;
  disabled?: boolean;
  startNote: string;
  goalNote: string;
  /** Lift the mode out when something else on the page also wants the
   *  next click.
   *
   * The deployment form does: its traffic editor places waypoints on
   * this same canvas. Two components each holding their own idea of what
   * a click means is how a nudge to a start lands a waypoint instead —
   * the failure the explicit mode was introduced to prevent, reappearing
   * one level up. Uncontrolled when omitted, which is how the decisions
   * page still uses it. */
  mode?: PlacementMode;
  onModeChange?: (next: PlacementMode) => void;
  /** Where a click goes when the mode is not one of this component's
   *  own two. Called with world coordinates. */
  onPlace?: (x: number, y: number) => void;
  /** Replaces the caption while somebody else's mode is active — this
   *  component has nothing true to say about placing a waypoint. */
  modeNote?: string;
  /** First refusal on a press, for a caller that drags its own things.
   *
   * Returning `true` means "handled" and the placer does nothing else
   * with that press — the deployment form uses it to grab a waypoint
   * without also moving the start pose. Returning `false` leaves the
   * gesture exactly as it was before this prop existed.
   *
   * **This component still does not know what a waypoint is.** It asks
   * whoever passed the callback and obeys the answer; the hit-testing,
   * the drag state and the document edit all live in the caller. A
   * placer that understood routes would be a second home for them. */
  onPointerDownFirst?: (press: {
    world: Point2D;
    /** Screen position of the press — the origin a drag threshold is
     *  measured from. World units would make the threshold change with
     *  the zoom, and a steady hand is a property of the screen. */
    client: Point2D;
    worldPerPixel: number;
    pointerId: number;
    /** Click count: 1 for the first press of a sequence, 2 for the
     *  second half of a double-click. */
    detail: number;
  }) => boolean;
  onPointerMoveWhileDown?: (move: { world: Point2D; client: Point2D }) => void;
  onPointerFinished?: (end: { world: Point2D; cancelled: boolean }) => void;
  onDoubleClickMap?: (at: { world: Point2D; worldPerPixel: number }) => void;
  dynamicObstacles?: ObstacleMarker[];
  obstacleSnapshots?: ObstacleSnapshot[];
  /** The traffic as declared, for the flat view to draw. Passed
   *  straight through: this component knows what a *pose* is and
   *  deliberately not what a waypoint is — the deployment form owns
   *  that, and a placer that understood routes would be a second home
   *  for them. */
  authoredTraffic?: TrafficOverlay;
  previewTime?: number;
}

export function MissionPlacer({
  map,
  start,
  goal,
  onChange,
  robotRadius,
  positionUncertainty,
  goalTolerance,
  disabled = false,
  startNote,
  goalNote,
  mode,
  onModeChange,
  onPlace,
  modeNote,
  onPointerDownFirst,
  onPointerMoveWhileDown,
  onPointerFinished,
  onDoubleClickMap,
  dynamicObstacles,
  obstacleSnapshots,
  authoredTraffic,
  previewTime,
}: MissionPlacerProps) {
  const { t } = useTranslation();
  const [own, setOwn] = useState<PlacementMode>("start");
  const placing = mode ?? own;
  const setPlacing = onModeChange ?? setOwn;

  /** Move whichever pose the mode names, keeping its heading.
   *
   * Advances to `goal` only while the goal is still unset — the first
   * pass places two poses without a trip to the toolbar, and after that
   * the mode stays where the author put it. Otherwise correcting a start
   * would drop a goal on top of it.
   */
  const place = (x: number, y: number) => {
    if (disabled || placing === "none") return;
    if (placing === "start") {
      onChange({ start: { x, y, theta: start?.theta ?? 0 }, goal });
      if (goal === null) setPlacing("goal");
    } else if (placing === "goal") {
      onChange({ start, goal: { x, y, theta: goal?.theta ?? 0 } });
    } else {
      // Somebody else's mode. This component does not know what a
      // waypoint is, and guessing would place a pose on top of one.
      onPlace?.(x, y);
    }
  };
  /** Dragging belongs to the poses and to nothing else.
   *
   * `MapCanvas` fires a click on mouse-down and then a drag per
   * mouse-move, which is what makes nudging a start feel continuous. In
   * a waypoint mode that same gesture appends a waypoint per pixel
   * travelled, so one careless drag writes a route of two hundred
   * points. The canvas is left without a drag handler while somebody
   * else's mode is active. */
  const missionMode = placing === "none" || placing === "start" || placing === "goal";

  /** Whether the caller took the press that is in flight.
   *
   * A ref rather than state: it is read by the move and up handlers of
   * the same gesture, and a re-render between them would be both
   * unnecessary and too late. */
  const takenByCaller = useRef(false);
  /** Does anybody want the full pointer lifecycle? Passing the handlers
   *  through unconditionally would turn on pointer capture for every
   *  screen using this placer — including `/decisions`, which has
   *  always ended a drag by leaving the canvas. */
  const lifted = onPointerDownFirst !== undefined;

  return (
    <>
      {/* Explicit modes, and a caption saying what the next click does.
          The same shape the scenario editor uses, and for the same
          reason: a hidden alternation makes nudging a start land a
          goal. */}
      <div className="toolbar" style={{ marginTop: 12 }}>
        {(["start", "goal"] as const).map((which) => (
          <button
            key={which}
            type="button"
            disabled={disabled}
            className={placing === which ? "active" : undefined}
            aria-pressed={placing === which}
            onClick={() => setPlacing(placing === which ? "none" : which)}
          >
            {t(`decisions.map.place.${which}`)}
          </button>
        ))}
        <span className="muted">
          {missionMode ? t(`decisions.map.mode.${placing}`) : (modeNote ?? "")}
        </span>
      </div>

      <div style={{ marginTop: 8 }}>
        <MapView
          map={map}
          startPose={start ?? undefined}
          goalPose={goal ?? undefined}
          robotRadius={robotRadius}
          positionUncertainty={positionUncertainty}
          goalTolerance={goalTolerance}
          dynamicObstacles={dynamicObstacles}
          obstacleSnapshots={obstacleSnapshots}
          authoredTraffic={authoredTraffic}
          previewTime={previewTime}
          {...(lifted
            ? {
                /* The caller sees every press first and says whether it
                   took it. Only what it declines reaches the poses, so
                   grabbing a waypoint never also nudges the start. */
                onWorldPointerDown: (point, info) => {
                  takenByCaller.current =
                    onPointerDownFirst?.({
                      world: point,
                      client: { x: info.event.clientX, y: info.event.clientY },
                      worldPerPixel: info.worldPerPixel,
                      pointerId: info.pointerId,
                      detail: info.event.detail,
                    }) ?? false;
                  if (!takenByCaller.current) place(point.x, point.y);
                },
                onWorldPointerMove: (point, info) => {
                  if (takenByCaller.current) {
                    onPointerMoveWhileDown?.({
                      world: point,
                      client: { x: info.event.clientX, y: info.event.clientY },
                    });
                    return;
                  }
                  /* Dragging belongs to the poses and to nothing else:
                     `MapCanvas` fires a move per pixel travelled, so in
                     a waypoint mode the same gesture would append a
                     route of two hundred points. */
                  if (missionMode && info.event.buttons !== 0) place(point.x, point.y);
                },
                onWorldPointerUp: (point) => {
                  if (takenByCaller.current) {
                    onPointerFinished?.({ world: point, cancelled: false });
                  }
                  takenByCaller.current = false;
                },
                onWorldPointerCancel: (point) => {
                  if (takenByCaller.current) {
                    onPointerFinished?.({ world: point, cancelled: true });
                  }
                  takenByCaller.current = false;
                },
                onWorldDoubleClick: (point, worldPerPixel) =>
                  onDoubleClickMap?.({ world: point, worldPerPixel }),
              }
            : {
                onWorldClick: (x: number, y: number) => place(x, y),
                ...(missionMode
                  ? { onWorldDrag: (x: number, y: number) => place(x, y) }
                  : {}),
              })}
        />
      </div>

      {/* Typed as well as clicked. A canvas cannot land on 2.00 exactly,
          and a deployment written down to two decimals is the one
          somebody can repeat from the report. */}
      <PoseFields
        label={t("decisions.map.start")}
        value={start}
        disabled={disabled}
        onChange={(pose) => onChange({ start: pose, goal })}
        note={startNote}
      />
      <PoseFields
        label={t("decisions.map.goal")}
        value={goal}
        disabled={disabled}
        onChange={(pose) => onChange({ start, goal: pose })}
        note={goalNote}
      />
    </>
  );
}

/** One pose as three numbers, beside the canvas that draws it.
 *
 * Heading in **degrees**, like the scenario editor: the contract stores
 * radians and nobody types 1.5708 for a quarter turn.
 *
 * Both fields exist for both poses, and the difference between them is
 * in the note rather than in the controls — see the two note strings the
 * caller supplies. Hiding the goal's heading would leave the arrow the
 * canvas draws unexplained, which is a worse silence than an inert dial
 * with a label.
 */
function PoseFields({
  label,
  value,
  disabled,
  onChange,
  note,
}: {
  label: string;
  value: Pose2D | null;
  disabled: boolean;
  onChange: (pose: Pose2D) => void;
  note: string;
}) {
  const { t } = useTranslation();
  if (value === null) {
    return (
      <p className="muted" style={{ marginTop: 8 }}>
        {label}: {t("decisions.map.unset")}
      </p>
    );
  }
  const number = (key: "x" | "y", step: number) => (
    <label className="field" key={key}>
      <span>{key}</span>
      <input
        type="number"
        step={step}
        disabled={disabled}
        value={value[key]}
        onChange={(event) => onChange({ ...value, [key]: Number(event.target.value) })}
      />
    </label>
  );

  return (
    <div style={{ marginTop: 8 }}>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        <strong style={{ minWidth: 90 }}>{label}</strong>
        {number("x", 0.1)}
        {number("y", 0.1)}
        <label className="field">
          <span>{t("decisions.map.heading")}</span>
          <input
            type="number"
            step={5}
            disabled={disabled}
            value={Math.round(DEGREES(value.theta))}
            onChange={(event) => onChange({ ...value, theta: RADIANS(Number(event.target.value)) })}
          />
        </label>
      </div>
      <p className="muted">{note}</p>
    </div>
  );
}
