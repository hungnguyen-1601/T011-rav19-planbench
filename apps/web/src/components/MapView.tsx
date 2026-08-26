"use client";

/** One map, two ways of looking at it, and one place that owns the swap.
 *
 * **Why a component and not a toggle per page.** The raised view existed
 * from early on and exactly one screen used it — the scenario library —
 * so every other map in the app was flat and nobody could say why. Adding
 * a button to each page in turn is how that inconsistency happened in the
 * first place: seven surfaces, seven chances to forget. This makes the
 * choice a property of *rendering a map*, so a new screen gets it by
 * using the same component everyone else does.
 *
 * **Neither view replaces the other.** They answer different questions:
 * top-down is where a coordinate is read, a tolerance circle is measured
 * and a cell is clicked; raised is where "will it fit through there" is
 * felt. Offering only one would be picking which question matters.
 *
 * **Editing lives in the flat view, and that is stated rather than
 * silently enforced.** The raised projection has no inverse — a click at
 * a screen pixel maps to a whole ray through the scene, not to one cell —
 * so a painter or a pose placer cannot take clicks there. Rather than
 * accept clicks and drop them, which reads as a broken canvas, the raised
 * view says where the editing is when a handler was passed to it.
 *
 * Opens flat. That is what every screen did before this component, and
 * changing the default would trade the precise view for the evocative one
 * on every page at once.
 */

import { useState } from "react";

import { MapCanvas, type MapCanvasProps } from "@/components/MapCanvas";
import { Scene25D } from "@/components/Scene25D";
import { useTranslation } from "@/lib/i18n";
import type { ObstacleSnapshot } from "@/lib/types";

export type MapViewMode = "flat" | "raised";

export interface MapViewProps extends MapCanvasProps {
  /** Moving obstacles for the raised view, which takes them as
   *  snapshots rather than as the canvas's marker shape. Both are fed
   *  from one source at the call site; two views showing different
   *  worlds would be worse than one view. */
  obstacleSnapshots?: ObstacleSnapshot[];
  /** Start raised. Only for a screen whose whole point is the shape of
   *  the space; leave it alone otherwise. */
  initialMode?: MapViewMode;
  /** Hide the switch — for a thumbnail, or a screen that has its own. */
  showModeSwitch?: boolean;
}

export function MapView({
  obstacleSnapshots,
  initialMode = "flat",
  showModeSwitch = true,
  ...canvas
}: MapViewProps) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<MapViewMode>(initialMode);
  /** The grid switch, for every caller that does not already have one.
   *
   * **Controlled when the page says so, owned here otherwise.** Two
   * screens keep the grid in a layer strip of their own — the test bench
   * beside its plan and trajectory checkboxes, the deployment form in
   * its map legend — and they pass `showGrid` down. Four more canvases
   * (the scenario library, the scenario editor, the map painter, the
   * decision preview) had no way to turn it off at all, because
   * `MapCanvas` defaults it on and nothing above them offered a control.
   *
   * Putting the fallback here rather than a checkbox on each of those
   * four pages means one switch to maintain, and it lands beside the
   * Top-down / 2.5D buttons, which is the other control that decides
   * what this canvas draws rather than what it contains. */
  const [ownGrid, setOwnGrid] = useState(false);
  const controlled = canvas.showGrid !== undefined;
  const showGrid = controlled ? canvas.showGrid !== false : ownGrid;
  const editable = canvas.onWorldClick !== undefined;
  const hasObstacles =
    (canvas.staticObstacles?.length ?? 0) > 0 ||
    (canvas.dynamicObstacles?.length ?? 0) > 0 ||
    (obstacleSnapshots?.length ?? 0) > 0;

  return (
    <div className="map-view">
      {showModeSwitch ? (
        <div className="toolbar map-view-switch">
          {(["flat", "raised"] as const).map((option) => (
            <button
              key={option}
              type="button"
              className={mode === option ? "active" : ""}
              onClick={() => setMode(option)}
              aria-pressed={mode === option}
            >
              {t(`mapView.${option}`)}
            </button>
          ))}
          {mode === "raised" && editable ? (
            <span className="muted">{t("mapView.editInFlat")}</span>
          ) : null}
          {/* Not rendered when the page controls the flag: a second
              checkbox for one layer is two controls that can disagree
              on screen while agreeing in state. */}
          {controlled ? null : (
            <label className="map-view-grid">
              <input
                type="checkbox"
                /* Named so a reader — and the test that freezes every
                   editing control — can tell a view switch from a field.
                   It draws; it does not edit. */
                className="map-view-control"
                checked={showGrid}
                onChange={(event) => setOwnGrid(event.target.checked)}
              />
              {t("simulate.grid")}
            </label>
          )}
        </div>
      ) : null}

      {mode === "raised" ? (
        <Scene25D
          map={canvas.map}
          width={canvas.width}
          height={canvas.height}
          startPose={canvas.startPose}
          goalPose={canvas.goalPose}
          robotPose={canvas.robotPose}
          robotRadius={canvas.robotRadius}
          /* The keep-out ring has to be the same size in both views. It
             already flows to the flat view through the props spread
             below; forgetting it here would draw two different rings for
             one number, which is the failure this ring exists to make
             visible in the first place. */
          positionUncertainty={canvas.positionUncertainty}
          /* `showPlan`/`showTrajectory`/`showGrid` are the canvas's
             checkboxes, and the raised view has to obey the same ones —
             a layer hidden in one view and drawn in the other is two
             answers to one question.

             `showGrid` used to be withheld here, on the reasoning that
             raising the cells *is* the grid. That was true of the walls
             and never of the floor: the floor is flat quads, and the
             faint lattice on it was the seam between them rather than
             anything the scene had drawn. So the switch reaches this
             view too, and now has something real to switch. */
          showGrid={showGrid}
          plannedPath={canvas.showPlan === false ? [] : canvas.plannedPath}
          trajectory={canvas.showTrajectory === false ? [] : canvas.trajectory}
          obstacles={obstacleSnapshots}
        />
      ) : (
        <MapCanvas {...canvas} showGrid={showGrid} />
      )}

      {/* **Drawn without a word is worse than not drawn.** A faint ring
          round an obstacle reads as "the robot nearly hit that" unless
          somebody says otherwise, and it is the opposite: the controller
          drives through it whenever it squeezes past something, and only
          the global planner refuses to route through it. Shown only when
          there is an obstacle to explain. */}
      {hasObstacles ? <p className="muted">{t("mapView.keepOut")}</p> : null}
    </div>
  );
}
