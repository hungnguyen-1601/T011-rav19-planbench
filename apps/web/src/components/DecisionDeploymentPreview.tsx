"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Hint } from "@/components/Hint";
import { MapView } from "@/components/MapView";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { TaskProfileSummary } from "@/lib/decisions";
import type { MapData, Pose2D } from "@/lib/types";

type Bag = Record<string, unknown>;

function bag(value: unknown): Bag { return value && typeof value === "object" ? value as Bag : {}; }
function number(value: unknown): number | undefined { return typeof value === "number" && Number.isFinite(value) ? value : undefined; }
function pose(value: unknown): Pose2D | undefined {
  if (Array.isArray(value) && value.length >= 2) {
    const x = number(value[0]); const y = number(value[1]); const theta = number(value[2]) ?? 0;
    return x === undefined || y === undefined ? undefined : { x, y, theta };
  }
  const item = bag(value); const x = number(item.x); const y = number(item.y);
  return x === undefined || y === undefined ? undefined : { x, y, theta: number(item.theta) ?? 0 };
}
function display(value: unknown, unit = ""): string {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "boolean") return value ? "✓" : "✕";
  if (typeof value === "number") return `${Number.isInteger(value) ? value : value.toFixed(2)}${unit}`;
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return String(value.length);
  if (typeof value === "object") {
    const active = Object.entries(value as Bag).filter(([, item]) => item !== undefined && item !== null && item !== false && item !== 0).map(([key]) => key);
    return active.length > 0 ? active.join(", ") : "—";
  }
  return "—";
}
function displayPose(value: Pose2D | undefined): string {
  return value ? `${value.x.toFixed(2)}, ${value.y.toFixed(2)} m · ${(value.theta * 180 / Math.PI).toFixed(0)}°` : "—";
}
function mapIdFromPath(value: unknown): string | null {
  if (typeof value !== "string") return null;
  return value.match(/maps\/custom\/(.+?)__v\d+\.(?:pgm|yaml)$/)?.[1] ?? null;
}

export function DecisionDeploymentPreview({ deployment }: { deployment?: TaskProfileSummary }) {
  const { t } = useTranslation();
  const [map, setMap] = useState<MapData | null>(null);
  const [loading, setLoading] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const data = deployment?.profile ?? {};
  const environment = bag(data.environment);
  const robot = bag(data.robot);
  const acceptance = bag(data.acceptance);
  const risk = bag(data.risk);
  const constraints = bag(data.constraints);
  const mission = bag(Array.isArray(data.missions) ? data.missions[0] : undefined);
  const start = pose(mission.start ?? data.start_pose);
  const goal = pose(mission.goal ?? data.goal_pose);
  const goalTolerance = number(constraints.goal_tolerance_m ?? acceptance.goal_tolerance_m ?? data.goal_tolerance);
  const radius = number(robot.radius);
  const noiseEntries = Object.entries(bag(environment.sensor_noise)).filter(([, value]) => value !== undefined && value !== null && value !== false && value !== 0);

  useEffect(() => {
    let cancelled = false;
    setMap(null); setMapError(false);
    if (!deployment) { setLoading(false); return; }
    setLoading(true);
    const storedId = mapIdFromPath(environment.map) ?? mapIdFromPath(environment.map_yaml);
    const artifactStem = typeof environment.map === "string" ? environment.map.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, "") : undefined;
    void (storedId
      ? api.getMap(storedId)
      : api.listMaps().then((maps) => {
          const match = maps.find((item) => item.id === artifactStem || item.name === artifactStem);
          if (!match) throw new Error("map artifact not found");
          return api.getMap(match.id);
        })).then((resource) => {
      if (!cancelled) { setMap(resource.map_data); setMapError(false); }
    }).catch(() => {
      if (!cancelled) { setMap(null); setMapError(true); }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [deployment, environment.map, environment.map_yaml, retry]);

  const groups = useMemo(() => [
    { tone: "mission", title: t("decisions.preview.mission"), rows: [
      [t("decisions.preview.start"), displayPose(start), false], [t("decisions.preview.goal"), displayPose(goal), false],
      [t("decisions.preview.goalTolerance"), display(goalTolerance, " m"), false], [t("decisions.preview.timeout"), display(constraints.episode_timeout_s ?? data.episode_timeout_s ?? data.timeout_seconds, " s"), false],
      [t("decisions.preview.scenario"), display(mission.id ?? data.mission), true], [t("decisions.preview.seed"), display(data.seed_policy), true],
    ]},
    { tone: "robot", title: t("decisions.preview.robot"), rows: [
      [t("decisions.preview.radius"), display(radius, " m"), false], [t("decisions.preview.linearVelocity"), display(robot.max_linear_velocity, " m/s"), false],
      [t("decisions.preview.profile"), display(robot.profile ?? robot.name), true], [t("decisions.preview.angularVelocity"), display(robot.max_angular_velocity, " rad/s"), true],
      [t("decisions.preview.linearAcceleration"), display(robot.max_linear_acceleration, " m/s²"), true],
    ]},
    { tone: "environment", title: t("decisions.preview.environment"), rows: [
      [t("decisions.preview.dynamicObstacles"), display(Array.isArray(environment.dynamic_obstacles) ? environment.dynamic_obstacles.length : environment.dynamic_obstacles), false],
      [t("decisions.preview.replanning"), display(bag(data.replanning).enabled ?? bag(environment.replanning).enabled ?? environment.replanning), false],
      [t("decisions.preview.mapSize"), map ? `${map.width} × ${map.height}` : "—", true], [t("decisions.preview.resolution"), display(map?.resolution, " m/cell"), true],
    ]},
    { tone: "threshold", title: t("decisions.preview.thresholds"), rows: [
      [t("decisions.preview.success"), display(constraints.success_rate_min ?? acceptance.min_success_rate), false], [t("decisions.preview.collisionRisk"), display(constraints.collision_probability_max ?? risk.acceptable_collision_probability ?? acceptance.max_collision_rate), false],
      ["N_min", display(risk.N_min ?? risk.n_min), true],
    ]},
  ], [acceptance, constraints, data, environment, goal, goalTolerance, map, mission, radius, risk, robot, start, t]);

  if (!deployment) return <p className="decision-deployment-empty">{t("decisions.preview.empty")}</p>;

  return <section className="decision-deployment-preview" aria-labelledby="decision-deployment-title">
    <header className="decision-deployment-header">
      <div><h4 id="decision-deployment-title">{t("decisions.preview.title")} <Hint text={t("decisions.preview.sharedNotice")} label={t("decisions.preview.title")} /></h4><code title={deployment.id}>{deployment.id}</code></div>
      <span className="decision-readonly-badge" title={t("decisions.preview.readonlyTip")}>{t("decisions.preview.readonly")}</span>
      <Link href="/deployments">{t("decisions.preview.openDeployment")}</Link>
    </header>
    <div className="decision-deployment-content">
      <div className="decision-deployment-map-column">
        <div className="decision-deployment-map" role="img" aria-label={t("decisions.preview.mapLabel")}>
          {loading ? <div className="decision-deployment-skeleton" aria-live="polite">{t("common.loading")}</div> : map ? <MapView map={map} startPose={start} goalPose={goal} goalTolerance={goalTolerance} robotRadius={radius} showModeSwitch={false} /> : <div className="decision-deployment-map-error"><span>{mapError ? t("decisions.preview.mapUnavailable") : "—"}</span><button type="button" onClick={() => setRetry((value) => value + 1)}>{t("decisions.preview.retry")}</button></div>}
        </div>
        <div className="decision-deployment-legend" aria-label={t("decisions.preview.legend")}><span className="start">{t("decisions.preview.start")}</span><span className="goal">{t("decisions.preview.goal")}</span><span className="static">{t("decisions.preview.staticObstacles")}</span><span className="dynamic">{t("decisions.preview.dynamicObstacles")}</span></div>
      </div>
      <div className="decision-deployment-details">
        {groups.map((group) => <section className={`decision-condition-section decision-condition-section--${group.tone}`} key={group.tone}><h5 className="decision-condition-header"><span aria-hidden="true" />{group.title}</h5><dl className="decision-condition-list">{group.rows.filter((row) => showAdvanced || !row[2]).map(([label, value]) => <div className="decision-condition-row" key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}{group.tone === "environment" ? <div className="decision-condition-row decision-noise-summary"><dt>{t("decisions.preview.noise")}</dt><dd>{noiseEntries.length} {t("decisions.preview.noiseTypes")}</dd></div> : null}</dl>{group.tone === "environment" && showAdvanced && noiseEntries.length > 0 ? <ul className="decision-noise-details">{noiseEntries.map(([name, value]) => <li key={name}><code title={name}>{name}</code><span>{display(value)}</span></li>)}</ul> : null}</section>)}
        <button className="decision-details-toggle" type="button" aria-expanded={showAdvanced} onClick={() => setShowAdvanced((value) => !value)}>{showAdvanced ? t("decisions.preview.showLess") : t("decisions.preview.showMore")}</button>
      </div>
    </div>
  </section>;
}
