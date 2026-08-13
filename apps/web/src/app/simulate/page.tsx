"use client";

/** The test bench — one episode of a deployment, watched.
 *
 * **The gap this fills.** The new flow could run three hundred episodes
 * and replay a recorded trace, but it could not show you *one* episode
 * live. Those are different questions: "what happened" against "let me
 * try this configuration and see". Before spending two hours of machine
 * time on a comparison, watching a single episode is the cheapest way to
 * find a goal placed behind a shelf, a noise amplitude entered a decimal
 * place out, or a robot radius that will not fit the doorway. Each of
 * those costs the whole run and surfaces at the end as a uniform wall of
 * `no_path` that reads like a platform fault.
 *
 * **What changed from the page this replaces.** It used to take a map, a
 * start and a goal placed by clicking, and a scenario invented on the
 * spot. It now takes a **deployment** and one of its missions, and every
 * condition — timeout, tolerance, noise, traffic, physics step — comes
 * from the contract. The clicking is gone on purpose: a start and goal
 * you can drag would make what you are watching a different episode from
 * the one about to be measured, which is exactly the false comfort a
 * test bench must not offer.
 *
 * **The seed is typed, not drawn.** Two runs with the same seed are the
 * same episode down to the obstacle trajectories and the noise draws, so
 * "watch that one again, slower" means something. A seed picked for you
 * would make the one episode worth re-watching the one you cannot get
 * back.
 *
 * **Nothing here is evidence, and the page says so out loud.** No HĐ-5
 * trace is written, so no gate, metric or Decision Card can see this run.
 * That is the entire reason it may run beside a live evaluation (HĐ-7.4)
 * and outside the context-outer order (HĐ-3.2) — and it is also why the
 * numbers below are labelled as something to look at rather than
 * something to conclude from.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { CandidatePicker, type CandidateSelection } from "@/components/CandidatePicker";
import { EmptyState } from "@/components/EmptyState";
import { MapView } from "@/components/MapView";
import { MetricsPanel } from "@/components/MetricsPanel";
import { api } from "@/lib/api";
import { authFetch, useSession } from "@/lib/auth";
import {
  listLocalControllers,
  listTaskProfiles,
  stageTestBenchEpisode,
  type LocalControllerConfig,
  type StagedEpisode,
  type TaskProfileSummary,
} from "@/lib/decisions";
import { poseOf } from "@/lib/deployments";
import { useTranslation } from "@/lib/i18n";
import { useEpisodeStream } from "@/lib/useEpisodeStream";
import type { MapData, PlanResult, Point2D } from "@/lib/types";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";

/** A mission as it comes off the wire.
 *
 * `start` and `goal` are `unknown` on purpose. HĐ-2's YAML form is
 * `[x, y, theta]` and the dumped form is `{x, y, theta}`; both are legal
 * and both are in the store, so a type claiming one of them would be a
 * claim the data does not honour. `poseOf` is the one place that
 * resolves it.
 */
interface Mission {
  id: string;
  start: unknown;
  goal: unknown;
  probability?: number;
}

/** The parts of a stored deployment this page reads. */
interface Deployment {
  missions?: Mission[];
  constraints?: { goal_tolerance_m?: number; episode_timeout_s?: number };
  robot?: { radius?: number; max_linear_velocity?: number; control_period?: number };
  environment?: { sensor_noise?: Record<string, number | boolean>; dynamic_obstacles?: unknown[] };
}

export default function TestBenchPage() {
  const { t } = useTranslation();
  const session = useSession();

  const [profiles, setProfiles] = useState<TaskProfileSummary[]>([]);
  const [profileId, setProfileId] = useState("");
  const [missionId, setMissionId] = useState("");
  const [seed, setSeed] = useState(0);
  const [choice, setChoice] = useState<CandidateSelection>({ stack: "", local_config: "" });
  const [stacks, setStacks] = useState<AlgorithmInfo[]>([]);
  const [configs, setConfigs] = useState<LocalControllerConfig[]>([]);

  const [map, setMap] = useState<MapData | null>(null);
  const [staged, setStaged] = useState<StagedEpisode | null>(null);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showPlan, setShowPlan] = useState(true);
  const [showTrajectory, setShowTrajectory] = useState(true);

  const stream = useEpisodeStream();

  useEffect(() => {
    (async () => {
      try {
        const [deployments, registry, named] = await Promise.all([
          listTaskProfiles(),
          authFetch<AlgorithmInfo[]>("/algorithms"),
          listLocalControllers(),
        ]);
        setProfiles(deployments);
        setStacks(registry);
        setConfigs(named);
        if (deployments.length > 0) setProfileId((current) => current || deployments[0].id);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
  }, []);

  const deployment = useMemo<Deployment | null>(() => {
    const found = profiles.find((entry) => entry.id === profileId);
    return found ? (found.profile as Deployment) : null;
  }, [profiles, profileId]);

  const missions = deployment?.missions ?? [];
  const mission = missions.find((entry) => entry.id === missionId) ?? missions[0] ?? null;
  const start = poseOf(mission?.start);
  const goal = poseOf(mission?.goal);

  /* Switching deployment invalidates the mission, the staged episode and
     everything on the canvas: they described a different world. Leaving
     the old trajectory drawn under a new deployment's map would be the
     most confusing possible screen. */
  useEffect(() => {
    setMissionId(missions[0]?.id ?? "");
    setStaged(null);
    setPlan(null);
    setMap(null);
    stream.reset();
    // `stream` is a new object every render; the deployment is the trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, profiles]);

  const runOne = useCallback(async () => {
    if (!profileId || !mission || !choice.stack || !choice.local_config) return;
    setBusy(true);
    setError(null);
    setPlan(null);
    stream.reset();
    try {
      const episode = await stageTestBenchEpisode(profileId, {
        mission_id: mission.id,
        seed,
        stack: choice.stack,
        local_config: choice.local_config,
      });
      setStaged(episode);
      const resource = await api.getMap(episode.map_id);
      setMap(resource.map_data);
      const result = await api.runSimulation(episode.simulation_id);
      setPlan(result.plan);
      if (result.result && result.result.trajectory.length > 0) {
        stream.connect(episode.simulation_id);
      } else {
        setError(
          result.plan && !result.plan.success
            ? t("bench.noPath", { reason: result.plan.failure_reason ?? "" })
            : t("bench.noTrajectory"),
        );
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, mission, choice, seed, t]);

  const visibleTrajectory = useMemo(() => {
    if (!showTrajectory) return [];
    const upto = stream.frames.filter((frame) => frame.time <= stream.playhead + 1e-9);
    return upto.length > 0 ? upto : stream.frames.slice(0, 1);
  }, [stream.frames, stream.playhead, showTrajectory]);

  /** The traffic at the instant on screen, not at t=0.
   *
   * Ground truth recorded by the engine and shown for replay only — no
   * planner ever sees it (HĐ-4). Absent when the server predates the
   * field, and an absent list is drawn as nothing rather than as an
   * empty aisle: "we did not record it" and "it was clear" are different
   * claims, and only the second is reassuring.
   */
  const traffic = useMemo(
    () =>
      (stream.currentFrame?.obstacles ?? []).map((entry) => ({
        name: entry.name,
        radius: entry.radius,
        position: { x: entry.x, y: entry.y },
      })),
    [stream.currentFrame],
  );

  const collisionPoint: Point2D | null =
    stream.status === "collision" && stream.frames.length > 0
      ? {
          x: stream.frames[stream.frames.length - 1].x,
          y: stream.frames[stream.frames.length - 1].y,
        }
      : null;

  const robotPose = stream.currentFrame
    ? { x: stream.currentFrame.x, y: stream.currentFrame.y, theta: stream.currentFrame.theta }
    : start;

  const ready = Boolean(profileId && mission && choice.stack && choice.local_config);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("bench.title")}</h2>
          <p>{t("bench.subtitle")}</p>
        </div>
      </div>

      {/* Stated before anything is run, not after. A reader who watches a
          clean episode and then finds out it counted for nothing has been
          told too late to have made a decision with it. */}
      <div className="notice">{t("bench.notEvidence")}</div>

      {error ? <div className="error-box">{error}</div> : null}
      {stream.error ? (
        <div className="error-box">{t("simulate.stream", { message: stream.error })}</div>
      ) : null}

      {profiles.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon="cpu"
            title={t("bench.empty.title")}
            body={t("bench.empty.body")}
            actionHref="/deployments"
            actionLabel={t("bench.empty.action")}
          />
        </div>
      ) : null}

      <div className="panel">
        <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
          <label className="field">
            <span>{t("bench.deployment")}</span>
            <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              {profiles.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.id}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>{t("bench.mission")}</span>
            <select
              value={mission?.id ?? ""}
              disabled={missions.length === 0}
              onChange={(event) => setMissionId(event.target.value)}
            >
              {missions.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.id}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>{t("bench.seed")}</span>
            <input
              type="number"
              min={0}
              step={1}
              value={seed}
              onChange={(event) => setSeed(Math.max(0, Math.trunc(Number(event.target.value))))}
            />
          </label>

          <CandidatePicker
            label={t("bench.candidate")}
            value={choice}
            onChange={setChoice}
            stacks={stacks}
            configs={configs}
            disabled={busy}
          />

          <button
            type="button"
            className="primary"
            disabled={busy || !ready || session === null}
            onClick={() => void runOne()}
          >
            {busy ? t("bench.running") : t("bench.run")}
          </button>
        </div>

        {/* The same seed is the same episode. Saying so is what turns the
            number from a mysterious knob into the control that lets you
            re-watch what you just saw. */}
        <p className="muted" style={{ marginTop: 8 }}>
          {t("bench.seedNote")}
        </p>
        {session === null ? <p className="muted">{t("bench.signedOut")}</p> : null}
      </div>

      {/* What the deployment fixed, shown rather than editable. Every one
          of these is a condition the comparison will run under, and a
          field that let you nudge one "just for the preview" would make
          this a different experiment. */}
      {deployment ? (
        <div className="panel">
          <div className="panel-head">
            <h3>{t("bench.conditions")}</h3>
          </div>
          <p className="muted">{t("bench.conditionsNote")}</p>
          <div className="table-scroll wide">
            <table>
              <tbody>
                <tr>
                  <td className="muted">{t("simulate.start")}</td>
                  <td>
                    {start ? `${start.x.toFixed(2)}, ${start.y.toFixed(2)} m` : "—"}
                  </td>
                  <td className="muted">{t("simulate.goal")}</td>
                  <td>
                    {goal ? `${goal.x.toFixed(2)}, ${goal.y.toFixed(2)} m` : "—"}
                  </td>
                </tr>
                <tr>
                  <td className="muted">{t("bench.tolerance")}</td>
                  <td>{deployment.constraints?.goal_tolerance_m ?? "—"} m</td>
                  <td className="muted">{t("library.timeout")}</td>
                  <td>{deployment.constraints?.episode_timeout_s ?? "—"} s</td>
                </tr>
                <tr>
                  <td className="muted">{t("simulate.robotRadius")}</td>
                  <td>{deployment.robot?.radius ?? "—"} m</td>
                  <td className="muted">{t("simulate.maxSpeed")}</td>
                  <td>{deployment.robot?.max_linear_velocity ?? "—"} m/s</td>
                </tr>
                <tr>
                  <td className="muted">{t("bench.traffic")}</td>
                  <td>{deployment.environment?.dynamic_obstacles?.length ?? 0}</td>
                  <td className="muted">{t("bench.noise")}</td>
                  <td>{describeNoise(deployment.environment?.sensor_noise, t)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          {staged ? (
            <p className="muted" style={{ marginTop: 8 }}>
              {t("bench.contextId")} <code>{staged.episode_context_id}</code>{" "}
              {t("bench.contextIdNote")}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="toolbar">
        <button onClick={stream.play} disabled={stream.frames.length === 0 || stream.playing}>
          {t("simulate.play")}
        </button>
        <button onClick={stream.pause} disabled={!stream.playing}>
          {t("simulate.pause")}
        </button>
        <button onClick={stream.reset} disabled={stream.frames.length === 0}>
          {t("bench.replay")}
        </button>
        <label className="inline">
          {t("bench.speed")}
          <select
            value={stream.speed}
            onChange={(event) => stream.setSpeed(Number(event.target.value))}
          >
            {[0.25, 0.5, 1, 2, 4, 8].map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
        </label>
        <input
          type="range"
          min={0}
          max={Math.max(stream.duration, 0.001)}
          step={0.01}
          value={stream.playhead}
          onChange={(event) => stream.seek(Number(event.target.value))}
          style={{ flex: 1, minWidth: 160 }}
          aria-label={t("simulate.timeline")}
        />
        <span className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
          {stream.playhead.toFixed(2)} / {stream.duration.toFixed(2)} s
        </span>
      </div>

      <div className="toolbar">
        <label className="inline">
          <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
          {t("simulate.grid")}
        </label>
        <label className="inline">
          <input type="checkbox" checked={showPlan} onChange={(e) => setShowPlan(e.target.checked)} />
          {t("simulate.globalPath")}
        </label>
        <label className="inline">
          <input
            type="checkbox"
            checked={showTrajectory}
            onChange={(e) => setShowTrajectory(e.target.checked)}
          />
          {t("simulate.trajectory")}
        </label>
        {stream.status ? (
          <span className={`badge ${stream.status === "success" ? "ok" : "err"}`}>
            {stream.status}
          </span>
        ) : null}
        {stream.reason ? <span className="muted">{stream.reason}</span> : null}
      </div>

      <div className="row">
        <div className="panel" style={{ flex: "1 1 auto" }}>
          {map ? (
            <MapView
              map={map}
              startPose={start ?? undefined}
              goalPose={goal ?? undefined}
              goalTolerance={deployment?.constraints?.goal_tolerance_m}
              robotRadius={deployment?.robot?.radius}
              plannedPath={stream.planPath.length > 0 ? stream.planPath : plan?.path}
              trajectory={visibleTrajectory}
              robotPose={robotPose}
              collisionPoint={collisionPoint}
              dynamicObstacles={traffic}
              obstacleSnapshots={stream.currentFrame?.obstacles ?? []}
              previewTime={stream.playhead}
              showGrid={showGrid}
              showPlan={showPlan}
              showTrajectory={showTrajectory}
            />
          ) : (
            <p className="muted">{t("bench.selectDeployment")}</p>
          )}
        </div>

        <div style={{ flex: "0 0 300px", minWidth: 280 }}>
          <div className="panel">
            <h3>{t("simulate.robotState")}</h3>
            {stream.currentFrame ? (
              <table>
                <tbody>
                  <tr>
                    <td className="muted">t</td>
                    <td>{stream.currentFrame.time.toFixed(2)} s</td>
                  </tr>
                  <tr>
                    <td className="muted">pose</td>
                    <td>
                      {stream.currentFrame.x.toFixed(2)}, {stream.currentFrame.y.toFixed(2)},{" "}
                      {stream.currentFrame.theta.toFixed(2)} rad
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">v</td>
                    <td>{stream.currentFrame.linear_velocity.toFixed(2)} m/s</td>
                  </tr>
                  <tr>
                    <td className="muted">ω</td>
                    <td>{stream.currentFrame.angular_velocity.toFixed(2)} rad/s</td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p className="muted">{t("simulate.noEpisode")}</p>
            )}
          </div>

          <div className="panel">
            <h3>{t("bench.next")}</h3>
            <p className="muted">{t("bench.nextNote")}</p>
            <Link href="/decisions" className="button-link">
              {t("bench.toComparison")}
            </Link>
          </div>
        </div>
      </div>

      {/* Read off the run itself, not off a trace — so they are the right
          numbers for "did that look sane" and the wrong ones for any
          claim, which is what HĐ-5 means by the trace being the sole
          input of the Metrics Engine. */}
      <MetricsPanel metrics={stream.metrics} plan={plan} />
      <p className="muted">{t("bench.metricsNote")}</p>
    </>
  );
}

/** One line naming the noise that is switched on, or that none is.
 *
 * A count would be useless and the full table would drown the row that
 * matters. Naming the active streams is what tells you at a glance that
 * the episode you are about to watch is running under localisation drift
 * you forgot you declared.
 */
function describeNoise(
  noise: Record<string, number | boolean> | undefined,
  t: (key: string) => string,
): string {
  if (!noise) return t("bench.noiseNone");
  const on = Object.entries(noise)
    .filter(([key, value]) => key !== "active" && typeof value === "number" && value > 0)
    .map(([key]) => key);
  return on.length > 0 ? on.join(", ") : t("bench.noiseNone");
}
