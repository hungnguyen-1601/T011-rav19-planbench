"use client";

/** File a deployment by filling fields instead of by pasting a document.
 *
 * **The form decides nothing.** `TaskProfile` on the server is the single
 * statement of HĐ-2, and it is what refuses a heading requirement the
 * platform cannot evaluate, traffic that shifts by less than one period,
 * or a RAM budget that does not add up. Every refusal shown here came
 * back from it; a second opinion in the browser would be free to
 * disagree with the one that actually decides.
 *
 * **The form and the paste box produce the same artifact.** The YAML
 * preview below is exactly what the paste box would accept, and both go
 * to `POST /task-profiles`. Without that, "a deployment" would have two
 * definitions and the second would drift.
 *
 * **Where a number has a consequence, the consequence is next to it.**
 * The accepted collision risk decides the episode count (HĐ-7.1); the
 * success threshold decides whether the deployment can rank at all
 * (HĐ-8.4). Those live in comments in the YAML files, where they are
 * read after the choice rather than during it.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { MapPainter } from "@/components/MapPainter";
import { MissionPlacer } from "@/components/MissionPlacer";
import { api } from "@/lib/api";
import {
  DEFAULT_LIBRARY_SCENARIO,
  at,
  getProfileTemplate,
  importLibraryScenario,
  listScenarioLibrary,
  materialiseMap,
  nMinFor,
  posesFor,
  ramLeftOver,
  withValue,
  type ProfileDraft,
} from "@/lib/deployments";
import { emptyBorderedMap } from "@/lib/demoMap";
import { useTranslation } from "@/lib/i18n";
import type { LibraryEntry } from "@/lib/platformTypes";
import type { MapData, MapSummary, Pose2D } from "@/lib/types";

/** Where the map under this deployment comes from. */
type MapSource = "library" | "stored" | "drawn";

export interface DeploymentFormProps {
  /** Called with the finished profile; the page owns the request so the
   *  YAML tab and this one submit through one code path. */
  onSubmit: (profile: ProfileDraft) => Promise<void>;
  busy: boolean;
  /** Server refusals, addressed by field path (`robot.radius`). Rendered
   *  beside the input rather than as a banner — a banner is what made a
   *  thirty-field form unusable in the first place. */
  fieldErrors: { path: string; message: string }[];
  /** The draft, lifted so the YAML tab can show what this tab built. */
  draft: ProfileDraft | null;
  onDraftChange: (draft: ProfileDraft) => void;
}

export function DeploymentForm({
  onSubmit,
  busy,
  fieldErrors,
  draft,
  onDraftChange,
}: DeploymentFormProps) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<MapSource>("library");
  const [library, setLibrary] = useState<LibraryEntry[]>([]);
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [libraryName, setLibraryName] = useState(DEFAULT_LIBRARY_SCENARIO);
  const [storedMapId, setStoredMapId] = useState("");
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [start, setStart] = useState<Pose2D | null>(null);
  const [goal, setGoal] = useState<Pose2D | null>(null);
  const [showHardware, setShowHardware] = useState(false);

  const set = useCallback(
    (path: string, value: unknown) => {
      if (draft) onDraftChange(withValue(draft, path, value));
    },
    [draft, onDraftChange],
  );

  // The defaults, from the shipped profile rather than a copy in here.
  useEffect(() => {
    if (draft) return;
    let cancelled = false;
    void (async () => {
      try {
        const [template, entries, stored] = await Promise.all([
          getProfileTemplate(),
          listScenarioLibrary().catch(() => [] as LibraryEntry[]),
          api.listMaps().catch(() => [] as MapSummary[]),
        ]);
        if (cancelled) return;
        onDraftChange(template);
        setLibrary(entries);
        setMaps(stored);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [draft, onDraftChange]);

  /** Adopt a map: draw it, write it out, and reset the poses onto it.
   *
   * The poses reset because a coordinate means something else on another
   * map — and it might still land on free floor, so nothing downstream
   * would catch it. Where the replacement pair comes from is the whole
   * subject of `posesFor`: a library scenario brings its own, and
   * anything else gets the map's corners.
   */
  const adopt = useCallback(
    async (data: MapData, mapId: string, scenario: Parameters<typeof posesFor>[1]) => {
      setMapData(data);
      const poses = posesFor(data, scenario);
      setStart(poses.start);
      setGoal(poses.goal);
      const paths = await materialiseMap(mapId);
      if (!draft) return;
      onDraftChange(
        withValue(withValue(draft, "environment.map", paths.map), "environment.map_yaml", paths.map_yaml),
      );
    },
    [draft, onDraftChange],
  );

  // Open on the default library scenario, so the form has a real map and
  // a drivable pair of poses before anybody touches it.
  useEffect(() => {
    if (!draft || mapData || source !== "library") return;
    let cancelled = false;
    void (async () => {
      try {
        const imported = await importLibraryScenario(libraryName);
        if (cancelled) return;
        const resource = await api.getMap(imported.map_id);
        if (cancelled) return;
        setStoredMapId(imported.map_id);
        await adopt(resource.map_data, imported.map_id, imported.scenario);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft !== null, libraryName, source]);

  const errorFor = useCallback(
    (path: string) => fieldErrors.find((entry) => entry.path === path)?.message,
    [fieldErrors],
  );

  const complete = useMemo(() => {
    const id = at(draft ?? {}, "id");
    return (
      typeof id === "string" && id.trim() !== "" && start !== null && goal !== null && !!mapData
    );
  }, [draft, start, goal, mapData]);

  if (!draft) return <p className="muted">{t("common.loading")}</p>;

  const submit = async () => {
    if (!start || !goal) return;
    // The mission is assembled at submit rather than kept in the draft,
    // so the two poses have exactly one home while they are being edited
    // — the same reason the placer holds none of its own.
    await onSubmit(
      withValue(draft, "missions", [
        {
          id: "custom_route",
          start: [start.x, start.y, start.theta],
          goal: [goal.x, goal.y, goal.theta],
          probability: 1.0,
        },
      ]),
    );
  };

  const field = (path: string, label: string, step?: number, note?: string) => (
    <Field
      key={path}
      label={label}
      note={note}
      error={errorFor(path)}
      value={at(draft, path)}
      step={step}
      disabled={busy}
      onChange={(value) => set(path, value)}
    />
  );

  const risk = at(draft, "constraints.collision_probability_max");
  const nMin = nMinFor(risk);
  const leftOver = ramLeftOver(draft);

  return (
    <>
      {error ? <div className="error-box">{error}</div> : null}

      <h4>{t("deployments.form.identity")}</h4>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        {field("id", t("deployments.form.id"), undefined, t("deployments.form.idNote"))}
        <Choice
          label={t("deployments.form.claimLevel")}
          value={at(draft, "claim_level")}
          options={["mission", "deployment", "robust_deployment"]}
          disabled={busy}
          onChange={(value) => set("claim_level", value)}
          error={errorFor("claim_level")}
        />
        <Choice
          label={t("deployments.form.role")}
          value={at(draft, "deployment_role")}
          options={["acceptance", "customer", "instrument"]}
          disabled={busy}
          onChange={(value) => set("deployment_role", value)}
          error={errorFor("deployment_role")}
        />
      </div>

      <h4>{t("deployments.form.robot")}</h4>
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        {field("robot.radius", t("deployments.form.radius"), 0.01)}
        {field("robot.max_linear_velocity", t("deployments.form.vMax"), 0.1)}
        {field("robot.max_angular_velocity", t("deployments.form.wMax"), 0.1)}
        {field("robot.max_linear_acceleration", t("deployments.form.aMax"), 0.1)}
        {field("robot.max_angular_acceleration", t("deployments.form.alphaMax"), 0.1)}
        {field(
          "robot.control_period",
          t("deployments.form.controlPeriod"),
          0.01,
          t("deployments.form.controlPeriodNote"),
        )}
      </div>

      <h4>{t("deployments.form.constraints")}</h4>
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        {field(
          "constraints.success_rate_min",
          t("deployments.form.successMin"),
          0.01,
          t("deployments.form.successMinNote"),
        )}
        {field(
          "constraints.collision_probability_max",
          t("deployments.form.risk"),
          0.01,
          nMin === null ? undefined : t("deployments.form.riskNote", { n: String(nMin) }),
        )}
        {field("constraints.no_path_rate_max", t("deployments.form.noPathMax"), 0.01)}
        {field("constraints.goal_tolerance_m", t("deployments.form.goalToleranceM"), 0.05)}
        {field(
          "constraints.goal_tolerance_rad",
          t("deployments.form.goalToleranceRad"),
          0.01,
          t("deployments.form.goalToleranceRadNote"),
        )}
        {field("constraints.episode_timeout_s", t("deployments.form.timeout"), 5)}
        {field("constraints.stuck_threshold_s", t("deployments.form.stuck"), 1)}
        {field("constraints.clearance_warning_m", t("deployments.form.clearanceWarning"), 0.05)}
      </div>

      <h4>{t("deployments.form.noise")}</h4>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        {field("environment.sensor_noise.lidar_range_sigma_m", t("deployments.form.lidarSigma"), 0.005)}
        {field("environment.sensor_noise.wheel_slip_fraction", t("deployments.form.wheelSlip"), 0.005)}
      </div>
      {/* The consequence of the one block this form cannot write. With no
          traffic *and* no noise, a deterministic planner replays one
          episode per seed and G2's bound rests on a sample of one. */}
      <p className="muted">{t("deployments.form.noiseNote")}</p>

      <h4>
        <button
          type="button"
          className={showHardware ? "active" : undefined}
          onClick={() => setShowHardware(!showHardware)}
        >
          {showHardware ? "▾" : "▸"} {t("deployments.form.hardware")}
        </button>
      </h4>
      {showHardware ? (
        <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
          {field("hardware.target_device", t("deployments.form.targetDevice"))}
          {field("hardware.total_ram_mb", t("deployments.form.totalRam"), 64)}
          {field("hardware.ram_budget_breakdown.os_and_middleware_mb", t("deployments.form.ramOs"), 64)}
          {field("hardware.ram_budget_breakdown.perception_stack_mb", t("deployments.form.ramPerception"), 64)}
          {field(
            "hardware.ram_budget_breakdown.localization_mapping_mb",
            t("deployments.form.ramLocalisation"),
            64,
          )}
          {field("hardware.ram_budget_breakdown.logging_and_reserve_mb", t("deployments.form.ramLogging"), 64)}
          {field(
            "hardware.available_ram_mb",
            t("deployments.form.availableRam"),
            64,
            leftOver === null ? undefined : t("deployments.form.availableRamNote", { left: String(leftOver) }),
          )}
        </div>
      ) : null}

      <h4>{t("deployments.form.map")}</h4>
      <div className="toolbar">
        {(["library", "stored", "drawn"] as MapSource[]).map((option) => (
          <button
            key={option}
            type="button"
            disabled={busy}
            className={source === option ? "active" : undefined}
            aria-pressed={source === option}
            onClick={() => setSource(option)}
          >
            {t(`deployments.form.source.${option}`)}
          </button>
        ))}
        <Link href="/maps">{t("decisions.map.drawOne")}</Link>
      </div>

      {source === "library" ? (
        <label className="field">
          <span>{t("deployments.form.scenario")}</span>
          <select
            value={libraryName}
            disabled={busy}
            onChange={(event) => {
              setMapData(null);
              setLibraryName(event.target.value);
            }}
          >
            {library.map((entry) => (
              <option key={entry.name} value={entry.name}>
                {entry.name} · {entry.map_size_m[0]}×{entry.map_size_m[1]} m
                {entry.dynamic_obstacles > 0 ? ` · ${entry.dynamic_obstacles} traffic` : ""}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {source === "stored" ? (
        <label className="field">
          <span>{t("decisions.map.label")}</span>
          <select
            value={storedMapId}
            disabled={busy}
            onChange={(event) => {
              const id = event.target.value;
              setStoredMapId(id);
              if (!id) return;
              void (async () => {
                try {
                  const resource = await api.getMap(id);
                  await adopt(resource.map_data, id, null);
                } catch (caught) {
                  setError(caught instanceof Error ? caught.message : String(caught));
                }
              })();
            }}
          >
            <option value="">{t("decisions.map.pickDeploymentFirst")}</option>
            {maps.map((map) => (
              <option key={map.id} value={map.id}>
                {map.name} · {map.width}×{map.height} · v{map.version}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {source === "drawn" ? (
        <DrawNewMap
          disabled={busy}
          onSaved={(data, id) => void adopt(data, id, null)}
          onError={setError}
        />
      ) : null}

      {mapData ? (
        <MissionPlacer
          map={mapData}
          start={start}
          goal={goal}
          onChange={(poses) => {
            setStart(poses.start);
            setGoal(poses.goal);
          }}
          robotRadius={numberAt(draft, "robot.radius")}
          goalTolerance={numberAt(draft, "constraints.goal_tolerance_m")}
          disabled={busy}
          startNote={t("decisions.map.startHeadingNote")}
          goalNote={t("decisions.map.goalHeadingNote")}
        />
      ) : (
        <p className="muted">{t("common.loading")}</p>
      )}

      <div className="row" style={{ marginTop: 16, alignItems: "center", gap: 12 }}>
        <button type="button" className="primary" disabled={busy || !complete} onClick={() => void submit()}>
          {t("deployments.file.submit")}
        </button>
        <span className="muted">{t("deployments.file.idRule")}</span>
      </div>
    </>
  );
}

function numberAt(draft: ProfileDraft, path: string): number | undefined {
  const value = at(draft, path);
  return typeof value === "number" ? value : undefined;
}

/** Draw a grid from scratch, save it, and hand it to the form.
 *
 * Three size boxes and the shared painter — the same one `/maps/[id]`
 * uses, so there is one answer to what painting a map means.
 */
function DrawNewMap({
  disabled,
  onSaved,
  onError,
}: {
  disabled: boolean;
  onSaved: (map: MapData, mapId: string) => void;
  onError: (message: string) => void;
}) {
  const { t } = useTranslation();
  const [width, setWidth] = useState(40);
  const [height, setHeight] = useState(30);
  const [resolution, setResolution] = useState(0.25);
  const [name, setName] = useState("");
  const [map, setMap] = useState<MapData>(() => emptyBorderedMap("drawn", 40, 30, 0.25));
  const [saving, setSaving] = useState(false);

  const reshape = (w: number, h: number, r: number) => {
    setWidth(w);
    setHeight(h);
    setResolution(r);
    // A resize cannot keep the painting: cell (3, 4) of a 40-wide grid is
    // somewhere else in a 60-wide one, so carrying the cells over would
    // shear the walls rather than preserve them.
    setMap(emptyBorderedMap(map.name, w, h, r));
  };

  const save = async () => {
    setSaving(true);
    try {
      const created = await api.createMap({ ...map, name: name.trim() || map.name });
      onSaved(created.map_data, created.id);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        <label className="field">
          <span>{t("common.name")}</span>
          <input value={name} disabled={disabled} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>{t("deployments.form.cols")}</span>
          <input
            type="number"
            value={width}
            disabled={disabled}
            onChange={(e) => reshape(Number(e.target.value), height, resolution)}
          />
        </label>
        <label className="field">
          <span>{t("deployments.form.rows")}</span>
          <input
            type="number"
            value={height}
            disabled={disabled}
            onChange={(e) => reshape(width, Number(e.target.value), resolution)}
          />
        </label>
        <label className="field">
          <span>{t("maps.resolution")}</span>
          <input
            type="number"
            step={0.05}
            value={resolution}
            disabled={disabled}
            onChange={(e) => reshape(width, height, Number(e.target.value))}
          />
        </label>
      </div>
      <MapPainter
        map={map}
        onChange={setMap}
        disabled={disabled || saving}
        actions={
          <button type="button" className="primary" disabled={disabled || saving} onClick={() => void save()}>
            {t("deployments.form.saveMap")}
          </button>
        }
      />
    </>
  );
}

/** One input, its consequence, and the server's complaint about it.
 *
 * The complaint sits under the field rather than in a banner at the top:
 * a banner is exactly what makes a thirty-field form unusable, because
 * "2 validation errors for TaskProfile" leaves the reader to find which
 * two.
 */
function Field({
  label,
  note,
  error,
  value,
  step,
  disabled,
  onChange,
}: {
  label: string;
  note?: string;
  error?: string;
  value: unknown;
  step?: number;
  disabled: boolean;
  onChange: (value: unknown) => void;
}) {
  const numeric = step !== undefined;
  return (
    <label className="field" style={{ minWidth: 150 }}>
      <span>{label}</span>
      <input
        type={numeric ? "number" : "text"}
        step={step}
        disabled={disabled}
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(event) =>
          onChange(numeric ? Number(event.target.value) : event.target.value)
        }
        aria-invalid={error ? true : undefined}
      />
      {error ? <span className="badge err">{error}</span> : note ? <span className="muted">{note}</span> : null}
    </label>
  );
}

function Choice({
  label,
  value,
  options,
  disabled,
  onChange,
  error,
}: {
  label: string;
  value: unknown;
  options: string[];
  disabled: boolean;
  onChange: (value: string) => void;
  error?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={typeof value === "string" ? value : options[0]}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {error ? <span className="badge err">{error}</span> : null}
    </label>
  );
}
