"use client";

/** Scenario editor (plan 2.3): author a scenario against a real map.
 *
 * The rules this page follows, and why:
 *
 * - **The browser never decides a scenario is valid.** Every check comes
 *   from `POST /scenarios/validate`, which runs the same engine that
 *   `create` and `update` run. A frontend that pre-approves geometry
 *   would eventually approve something the engine rejects, and the
 *   author would meet the real rule only at save time.
 * - **The browser never evaluates motion.** Moving obstacles are drawn
 *   at positions returned by `POST /scenarios/preview`. Re-implementing
 *   the motion laws here would give the editor a second simulator that
 *   drifts from the first — and a preview that disagrees with the
 *   episode is worse than no preview.
 * - **No split, no difficulty.** A scenario authored here is
 *   `unassigned` (P05) and uncalibrated (P03). Neither is editable, and
 *   the page says so rather than leaving two blanks that read as
 *   oversights.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { MapCanvas, type ObstacleMarker } from "@/components/MapCanvas";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import type {
  DynamicObstacle,
  MapResource,
  MapSummary,
  Scenario,
  ScenarioPreview,
  ScenarioResource,
  StaticObstacle,
  ValidationReport,
} from "@/lib/types";

/** What a click on the map does. Explicit modes rather than modifier
 *  keys: the author has to be able to see what the next click will do. */
type PlacementMode = "none" | "start" | "goal" | "circle" | "rectangle" | "waypoint";

const DEFAULT_ROBOT = {
  radius: 0.3,
  max_linear_velocity: 1.0,
  max_angular_velocity: 2.0,
  max_linear_acceleration: 1.0,
  max_angular_acceleration: 3.0,
};

const NEW_SCENARIO: Scenario = {
  name: "",
  description: "",
  robot: DEFAULT_ROBOT,
  start_pose: { x: 1.5, y: 1.5, theta: 0 },
  goal_pose: { x: 4.0, y: 4.0, theta: 0 },
  goal_tolerance: 0.3,
  timeout_seconds: 120,
  simulation_dt: 0.05,
  static_obstacles: [],
  dynamic_obstacles: [],
  random_seed: 0,
};

const degrees = (radians: number) => (radians * 180) / Math.PI;
const radians = (deg: number) => (deg * Math.PI) / 180;
const round2 = (value: number) => Math.round(value * 100) / 100;

export default function ScenarioEditorPage() {
  const { t } = useTranslation();
  const session = useSession();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const scenarioId = params?.id ?? "new";
  const isNew = scenarioId === "new";

  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [mapId, setMapId] = useState<string>("");
  const [mapResource, setMapResource] = useState<MapResource | null>(null);
  const [draft, setDraft] = useState<Scenario>(NEW_SCENARIO);
  const [mode, setMode] = useState<PlacementMode>("none");
  const [pendingCorner, setPendingCorner] = useState<{ x: number; y: number } | null>(null);
  const [pendingWaypoints, setPendingWaypoints] = useState<{ x: number; y: number }[]>([]);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [preview, setPreview] = useState<ScenarioPreview | null>(null);
  const [previewTime, setPreviewTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(isNew ? null : scenarioId);
  const [split, setSplit] = useState<string>("unassigned");

  useEffect(() => {
    (async () => {
      try {
        const list = await authFetch<MapSummary[]>("/maps");
        setMaps(list);
        if (!isNew) {
          const stored = await authFetch<ScenarioResource>(`/scenarios/${scenarioId}`);
          setDraft(stored.scenario);
          setMapId(stored.map_id);
          setSplit(stored.split);
        } else if (list.length > 0) {
          setMapId(list[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [isNew, scenarioId]);

  useEffect(() => {
    if (!mapId) return;
    (async () => {
      try {
        setMapResource(await authFetch<MapResource>(`/maps/${mapId}`));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [mapId]);

  const patch = useCallback((changes: Partial<Scenario>) => {
    setDraft((current) => ({ ...current, ...changes }));
    // Any edit invalidates the previous verdict. Leaving a stale "valid"
    // badge on screen while the geometry has moved is the one failure
    // this whole flow exists to prevent.
    setValidation(null);
  }, []);

  const onWorldClick = useCallback(
    (x: number, y: number) => {
      const point = { x: round2(x), y: round2(y) };
      if (mode === "start") {
        patch({ start_pose: { ...draft.start_pose, x: point.x, y: point.y } });
      } else if (mode === "goal") {
        patch({ goal_pose: { ...draft.goal_pose, x: point.x, y: point.y } });
      } else if (mode === "circle") {
        patch({
          static_obstacles: [
            ...(draft.static_obstacles ?? []),
            { type: "circle", center: point, radius: 0.4 },
          ],
        });
      } else if (mode === "rectangle") {
        if (!pendingCorner) {
          setPendingCorner(point);
        } else {
          const min_x = Math.min(pendingCorner.x, point.x);
          const max_x = Math.max(pendingCorner.x, point.x);
          const min_y = Math.min(pendingCorner.y, point.y);
          const max_y = Math.max(pendingCorner.y, point.y);
          setPendingCorner(null);
          // A zero-extent rectangle is rejected by the schema; catching
          // the double-click here keeps the error out of the author's way
          // rather than teaching them a validator rule.
          if (max_x - min_x < 0.1 || max_y - min_y < 0.1) return;
          patch({
            static_obstacles: [
              ...(draft.static_obstacles ?? []),
              { type: "rectangle", min_x, min_y, max_x, max_y },
            ],
          });
        }
      } else if (mode === "waypoint") {
        setPendingWaypoints((current) => [...current, point]);
      }
    },
    [mode, draft, patch, pendingCorner],
  );

  const addDynamicObstacle = useCallback(() => {
    if (pendingWaypoints.length < 2) return;
    const obstacle: DynamicObstacle = {
      name: `obstacle-${(draft.dynamic_obstacles?.length ?? 0) + 1}`,
      radius: 0.35,
      motion: { kind: "waypoint", waypoints: pendingWaypoints, speed: 0.6, ping_pong: true },
      // Non-zero by default: with no seed-derived head start every seed
      // replays identical traffic, and a benchmark over 30 seeds then
      // reports a variance of zero that is an artefact, not a finding.
      seed_time_offset: 10,
      seed_offset: (draft.dynamic_obstacles?.length ?? 0) + 1,
    };
    patch({ dynamic_obstacles: [...(draft.dynamic_obstacles ?? []), obstacle] });
    setPendingWaypoints([]);
    setMode("none");
  }, [pendingWaypoints, draft, patch]);

  const updateDynamic = useCallback(
    (index: number, changes: Partial<DynamicObstacle>) => {
      const list = [...(draft.dynamic_obstacles ?? [])];
      list[index] = { ...list[index], ...changes };
      patch({ dynamic_obstacles: list });
    },
    [draft, patch],
  );

  const removeStatic = useCallback(
    (index: number) => {
      const list = [...(draft.static_obstacles ?? [])];
      list.splice(index, 1);
      patch({ static_obstacles: list });
    },
    [draft, patch],
  );

  const removeDynamic = useCallback(
    (index: number) => {
      const list = [...(draft.dynamic_obstacles ?? [])];
      list.splice(index, 1);
      patch({ dynamic_obstacles: list });
    },
    [draft, patch],
  );

  const validate = useCallback(async () => {
    if (!mapId) return;
    setBusy(true);
    setError(null);
    try {
      setValidation(
        await authFetch<ValidationReport>("/scenarios/validate", {
          method: "POST",
          body: JSON.stringify({ map_id: mapId, scenario: draft }),
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [mapId, draft]);

  const refreshPreview = useCallback(
    async (time: number) => {
      if (!mapId) return;
      try {
        setPreview(
          await authFetch<ScenarioPreview>("/scenarios/preview", {
            method: "POST",
            body: JSON.stringify({
              map_id: mapId,
              scenario: draft,
              time,
              seed: draft.random_seed ?? 0,
            }),
          }),
        );
      } catch (err) {
        // A preview is an aid, not the work: losing it must not stop
        // anyone from editing or saving.
        setPreview(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [mapId, draft],
  );

  const save = useCallback(async () => {
    if (!mapId) return;
    setBusy(true);
    setError(null);
    try {
      const body = JSON.stringify({ map_id: mapId, scenario: draft });
      const stored = savedId
        ? await authFetch<ScenarioResource>(`/scenarios/${savedId}`, { method: "PUT", body })
        : await authFetch<ScenarioResource>("/scenarios", { method: "POST", body });
      setSavedId(stored.id);
      setSplit(stored.split);
      setValidation({ valid: true, errors: [] });
      if (isNew) router.replace(`/scenarios/${stored.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [mapId, draft, savedId, isNew, router]);

  const markers: ObstacleMarker[] = useMemo(
    () =>
      (preview?.dynamic_obstacles ?? []).map((item) => ({
        name: item.name,
        radius: item.radius,
        position: item.position,
      })),
    [preview],
  );

  const canEdit = Boolean(session);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{isNew ? t("scenarios.newTitle") : t("scenarios.editTitle")}</h2>
          <p>{t("scenarios.editorSubtitle")}</p>
        </div>
        <div>
          <Link href="/scenarios">{t("scenarios.backToList")}</Link>
        </div>
      </div>

      {!session ? (
        <div className="notice">
          <Link href="/login">{t("topbar.signIn")}</Link> — {t("common.signInRequired")}
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      {/* Stated up front, not discovered after saving: what this editor
          deliberately does not control. */}
      <div className="notice">{t("scenarios.protocolNotice", { split })}</div>

      <div className="panel">
        <h3>{t("scenarios.basics")}</h3>
        <label>
          {t("common.name")}
          <input
            value={draft.name}
            onChange={(event) => patch({ name: event.target.value })}
            placeholder="my_scenario"
          />
        </label>
        <label>
          {t("algorithms.description")}
          <input
            value={draft.description ?? ""}
            onChange={(event) => patch({ description: event.target.value })}
          />
        </label>
        <label>
          {t("common.map")}
          <select
            value={mapId}
            onChange={(event) => {
              setMapId(event.target.value);
              setValidation(null);
            }}
          >
            {maps.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("scenarios.timeout")}
          <input
            type="number"
            value={draft.timeout_seconds}
            onChange={(event) => patch({ timeout_seconds: Number(event.target.value) })}
          />
        </label>
        <label>
          {t("scenarios.goalTolerance")}
          <input
            type="number"
            step="0.05"
            value={draft.goal_tolerance}
            onChange={(event) => patch({ goal_tolerance: Number(event.target.value) })}
          />
        </label>
        <label>
          {t("scenarios.robotRadius")}
          <input
            type="number"
            step="0.05"
            value={draft.robot.radius}
            onChange={(event) =>
              patch({ robot: { ...draft.robot, radius: Number(event.target.value) } })
            }
          />
        </label>
      </div>

      <div className="panel">
        <h3>{t("scenarios.canvas")}</h3>
        <p className="muted">{t(`scenarios.mode.${mode}`)}</p>
        <div className="toolbar">
          {(["start", "goal", "circle", "rectangle", "waypoint"] as PlacementMode[]).map((item) => (
            <button
              key={item}
              type="button"
              className={mode === item ? "active" : undefined}
              onClick={() => {
                setMode(mode === item ? "none" : item);
                setPendingCorner(null);
              }}
            >
              {t(`scenarios.place.${item}`)}
            </button>
          ))}
        </div>
        {mapResource ? (
          <MapCanvas
            map={mapResource.map_data}
            width={720}
            height={480}
            startPose={draft.start_pose}
            goalPose={draft.goal_pose}
            goalTolerance={draft.goal_tolerance}
            robotRadius={draft.robot.radius}
            staticObstacles={(draft.static_obstacles ?? []) as StaticObstacle[]}
            dynamicObstacles={markers}
            previewTime={preview ? preview.time : undefined}
            onWorldClick={onWorldClick}
          />
        ) : (
          <p className="muted">{t("common.loading")}</p>
        )}

        <div className="dashboard-columns">
          <label>
            {t("scenarios.startHeading")}
            <input
              type="number"
              value={Math.round(degrees(draft.start_pose.theta))}
              onChange={(event) =>
                patch({
                  start_pose: { ...draft.start_pose, theta: radians(Number(event.target.value)) },
                })
              }
            />
          </label>
          <label>
            {t("scenarios.goalHeading")}
            <input
              type="number"
              value={Math.round(degrees(draft.goal_pose.theta))}
              onChange={(event) =>
                patch({
                  goal_pose: { ...draft.goal_pose, theta: radians(Number(event.target.value)) },
                })
              }
            />
          </label>
        </div>

        <div className="dashboard-columns">
          <p className="muted">
            {t("scenarios.startAt", {
              x: draft.start_pose.x.toFixed(2),
              y: draft.start_pose.y.toFixed(2),
            })}
          </p>
          <p className="muted">
            {t("scenarios.goalAt", {
              x: draft.goal_pose.x.toFixed(2),
              y: draft.goal_pose.y.toFixed(2),
            })}
          </p>
        </div>
      </div>

      <div className="panel">
        <h3>{t("scenarios.staticObstacles")}</h3>
        {(draft.static_obstacles ?? []).length === 0 ? (
          <p className="muted">{t("common.none")}</p>
        ) : (
          <div className="table-scroll">
            <table>
              <tbody>
                {(draft.static_obstacles ?? []).map((obstacle, index) => (
                  <tr key={`${obstacle.type}-${index}`}>
                    <td>
                      <code>{obstacle.type}</code>
                    </td>
                    <td className="muted">
                      {obstacle.type === "circle"
                        ? `(${obstacle.center.x.toFixed(2)}, ${obstacle.center.y.toFixed(2)}) r=${obstacle.radius}`
                        : `(${obstacle.min_x.toFixed(2)}, ${obstacle.min_y.toFixed(2)}) .. (${obstacle.max_x.toFixed(2)}, ${obstacle.max_y.toFixed(2)})`}
                    </td>
                    <td>
                      <button type="button" onClick={() => removeStatic(index)}>
                        {t("scenarios.remove")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>{t("scenarios.dynamicObstacles")}</h3>
        {mode === "waypoint" ? (
          <div className="notice">
            {t("scenarios.waypointHint", { count: String(pendingWaypoints.length) })}{" "}
            <button
              type="button"
              disabled={pendingWaypoints.length < 2}
              onClick={addDynamicObstacle}
            >
              {t("scenarios.addDynamic")}
            </button>{" "}
            <button type="button" onClick={() => setPendingWaypoints([])}>
              {t("scenarios.clearWaypoints")}
            </button>
          </div>
        ) : null}
        {(draft.dynamic_obstacles ?? []).length === 0 ? (
          <p className="muted">{t("common.none")}</p>
        ) : (
          <div className="table-scroll wide">
            <table>
              <thead>
                <tr>
                  <th>{t("common.name")}</th>
                  <th>{t("scenarios.radius")}</th>
                  <th>{t("scenarios.speed")}</th>
                  <th>{t("scenarios.seedOffset")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {(draft.dynamic_obstacles ?? []).map((obstacle, index) => (
                  <tr key={`${obstacle.name}-${index}`}>
                    <td>
                      <input
                        value={obstacle.name}
                        onChange={(event) => updateDynamic(index, { name: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.05"
                        value={obstacle.radius}
                        onChange={(event) =>
                          updateDynamic(index, { radius: Number(event.target.value) })
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.1"
                        value={obstacle.motion.kind === "waypoint" ? obstacle.motion.speed : 0}
                        disabled={obstacle.motion.kind !== "waypoint"}
                        onChange={(event) =>
                          obstacle.motion.kind === "waypoint"
                            ? updateDynamic(index, {
                                motion: { ...obstacle.motion, speed: Number(event.target.value) },
                              })
                            : undefined
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        title={t("scenarios.seedOffsetHint")}
                        value={obstacle.seed_time_offset ?? 0}
                        onChange={(event) =>
                          updateDynamic(index, { seed_time_offset: Number(event.target.value) })
                        }
                      />
                    </td>
                    <td>
                      <button type="button" onClick={() => removeDynamic(index)}>
                        {t("scenarios.remove")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(draft.dynamic_obstacles ?? []).some((item) => (item.seed_time_offset ?? 0) <= 0) ? (
          <div className="notice">{t("scenarios.zeroOffsetWarning")}</div>
        ) : null}
      </div>

      <div className="panel">
        <h3>{t("scenarios.preview")}</h3>
        <label>
          {t("scenarios.previewTime", { time: previewTime.toFixed(1) })}
          <input
            type="range"
            min={0}
            max={Math.max(10, draft.timeout_seconds)}
            step={0.5}
            value={previewTime}
            onChange={(event) => {
              const next = Number(event.target.value);
              setPreviewTime(next);
              void refreshPreview(next);
            }}
          />
        </label>
        <button type="button" onClick={() => void refreshPreview(previewTime)}>
          {t("scenarios.refreshPreview")}
        </button>
        <p className="muted">{t("scenarios.previewHint")}</p>
      </div>

      <div className="panel">
        <h3>{t("scenarios.validation")}</h3>
        <button type="button" disabled={busy || !mapId} onClick={() => void validate()}>
          {t("scenarios.validate")}
        </button>{" "}
        <button
          type="button"
          disabled={!canEdit || busy || !mapId || !draft.name}
          onClick={() => void save()}
        >
          {savedId ? t("scenarios.saveChanges") : t("scenarios.save")}
        </button>
        {validation ? (
          validation.valid ? (
            <div className="notice">{t("scenarios.valid")}</div>
          ) : (
            <div className="error-box">
              <strong>{t("scenarios.invalid")}</strong>
              <ul>
                {validation.errors.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </div>
          )
        ) : (
          <p className="muted">{t("scenarios.notValidatedYet")}</p>
        )}
        {savedId ? (
          <p className="muted">
            {t("scenarios.savedAs", { id: savedId })}{" "}
            <Link href="/decisions">{t("library.openDecisions")}</Link>
          </p>
        ) : null}
      </div>
    </>
  );
}
