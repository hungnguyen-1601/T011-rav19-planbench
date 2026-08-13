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

import { useState } from "react";

import { MapView } from "@/components/MapView";
import { useTranslation } from "@/lib/i18n";
import type { MapData, Pose2D } from "@/lib/types";

/** What the next click on the map does.
 *
 * An explicit mode with a button and a caption, the way the scenario
 * editor has always done it, rather than a hidden alternation: the
 * author has to be able to *see* what the next click will do, or nudging
 * a start two pixels lands a goal instead.
 */
export type PlacementMode = "none" | "start" | "goal";

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
  goalTolerance?: number;
  disabled?: boolean;
  startNote: string;
  goalNote: string;
}

export function MissionPlacer({
  map,
  start,
  goal,
  onChange,
  robotRadius,
  goalTolerance,
  disabled = false,
  startNote,
  goalNote,
}: MissionPlacerProps) {
  const { t } = useTranslation();
  const [placing, setPlacing] = useState<PlacementMode>("start");

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
    } else {
      onChange({ start, goal: { x, y, theta: goal?.theta ?? 0 } });
    }
  };

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
        <span className="muted">{t(`decisions.map.mode.${placing}`)}</span>
      </div>

      <div style={{ marginTop: 8 }}>
        <MapView
          map={map}
          startPose={start ?? undefined}
          goalPose={goal ?? undefined}
          robotRadius={robotRadius}
          goalTolerance={goalTolerance}
          onWorldClick={(x, y) => place(x, y)}
          onWorldDrag={(x, y) => place(x, y)}
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
