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
import { Icon } from "@/components/Icon";
import { MapView } from "@/components/MapView";
import { MetricsPanel } from "@/components/MetricsPanel";
import { api } from "@/lib/api";
import { authFetch, useSession } from "@/lib/auth";
import {
  CONDITION_GROUPS,
  conditionValue,
  describeCondition,
  type ConditionDisplay,
  type ConditionGroupSpec,
  type Translate,
} from "@/lib/benchConditions";
import {
  listLocalControllers,
  listTaskProfiles,
  stageTestBenchEpisode,
  type LocalControllerConfig,
  type StagedEpisode,
  type TaskProfileSummary,
} from "@/lib/decisions";
import { poseOf } from "@/lib/deployments";
import { Hint } from "@/components/Hint";
import { plannedRouteColour } from "@/lib/evidence";
import { useTranslation } from "@/lib/i18n";
import { useEpisodeStream } from "@/lib/useEpisodeStream";
import type { MapData, PlanResult, Point2D } from "@/lib/types";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";
import type { ProfileDraft } from "@/lib/deployments";
import { safetyEnvelope } from "@/lib/keepOut";
import { trafficOf } from "@/lib/traffic";
import { overlayOf } from "@/lib/trafficOverlay";

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

/** Which of the page's two screens is on.
 *
 * `setup` prepares an episode — deployment, mission, candidate, seed,
 * and the world those resolve to. `results` shows the episode being run
 * in it. They are two questions asked minutes apart, and one column
 * holding both meant the reader scrolled past the form they had finished
 * with to reach the canvas they were waiting on.
 */
type BenchStage = "setup" | "results";

/** The parts of a stored deployment this page reads. */
/** The parts of a task profile this page reads.
 *
 * Every field optional, and that is not laziness: the profile arrives as
 * stored JSON, and a run filed before a field existed genuinely does not
 * carry it. These are the few the page needs *as values* — the map, the
 * keep-out ring, the collapsed one-line summary. Everything the
 * condition cards read comes off the stored record by path, through
 * `lib/benchConditions`, which is why adding a field to this interface
 * is not how a field reaches the screen.
 */
interface Deployment {
  missions?: Mission[];
  replanning?: { enabled?: boolean };
  constraints?: {
    goal_tolerance_m?: number;
    episode_timeout_s?: number;
    success_rate_min?: number;
    collision_probability_max?: number;
    no_path_rate_max?: number;
    clearance_warning_m?: number;
    stuck_threshold_s?: number;
  };
  robot?: { radius?: number; max_linear_velocity?: number; control_period?: number };
  /** G5's threshold lives here rather than with the constraints: it is
   *  an allocation decision about the target board, not a limit on the
   *  mission. */
  hardware?: { available_ram_mb?: number };
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
  const [showGrid, setShowGrid] = useState(false);
  const [showPlan, setShowPlan] = useState(true);
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [conditionsExpanded, setConditionsExpanded] = useState(true);

  /** Which screen is on — held as its own state rather than read off the
   *  data, which is the whole point.
   *
   * Three values look like they answer "is there a result yet", and each
   * answers a different question. `map` is set by Show world too, so it
   * says "a world is on screen", not "an episode ran". `plan` arrives
   * only after the server replies, so it is blank for the entire run —
   * the minute the reader most wants to be watching. `stream.frames` is
   * non-empty only when the robot actually moved, so an episode that
   * planned nothing (`no_path`) never sets it, and a screen chosen by
   * that value would strand exactly the reader who needs to be told why.
   *
   * The switch is a fact about the click, not about what came back.
   */
  const [stage, setStage] = useState<BenchStage>("setup");

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

  /** Which planned route is on screen, given where the playhead is.
   *
   * **The same rule as the decisions canvas, on a different key.**
   * `routeAt` there walks routes stamped with a step index, because a
   * trace is a list of rows. This socket stamps them with seconds,
   * because that is what the engine records against an event and what
   * the frames carry — so the walk is the same and the comparison is
   * `from_time` instead of `from_index`. Converting one to the other to
   * share a function would put a clock conversion between two things
   * that already agree.
   *
   * `plannedRouteColour` *is* shared, so an attempt that is orange on
   * one screen is orange on the other.
   */
  const currentRoute = useMemo(() => {
    if (stream.planRoutes.length === 0) return null;
    const now = stream.currentFrame?.time ?? stream.playhead;
    let current: (typeof stream.planRoutes)[number] | null = null;
    for (const route of stream.planRoutes) {
      if (route.from_time > now) break;
      current = route;
    }
    // A refused attempt has no route. Recorded so the canvas can say the
    // plan went away rather than silently keeping the previous one.
    return current && current.points.length > 0 ? current : null;
  }, [stream.planRoutes, stream.currentFrame, stream.playhead]);

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
    /* The deployment picker only exists on the setup screen, so today
       this cannot fire from the results screen. Stated anyway, because
       it is the same decision as clearing the map: a results screen kept
       up after its deployment was swapped would be describing a run that
       nothing on the page still refers to. */
    setStage("setup");
    stream.reset();
    // `stream` is a new object every render; the deployment is the trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, profiles]);

  /** Put the world on screen without running anything.
   *
   * **The map used to arrive only as a side effect of pressing Run.**
   * Until it did there was no canvas at all, so the traffic a
   * deployment declares — the whole reason somebody opens this page
   * before committing to a 300-episode comparison — was invisible
   * until after the episode it was supposed to inform. Staging is what
   * resolves the deployment to a map, and it is the same call Run
   * makes; doing it on its own costs one staged episode and answers
   * "what am I about to measure" before the measuring.
   */
  const prepare = useCallback(async () => {
    if (!profileId || !mission || !choice.stack || !choice.local_config) return null;
    const episode = await stageTestBenchEpisode(profileId, {
      mission_id: mission.id,
      seed,
      stack: choice.stack,
      local_config: choice.local_config,
    });
    setStaged(episode);
    const resource = await api.getMap(episode.map_id);
    setMap(resource.map_data);
    return episode;
  }, [profileId, mission, choice, seed]);

  /* Deliberately leaves the stage alone. Looking at the world is part of
     preparing an episode, not of watching one: the reader who presses
     this is still deciding whether the deployment is the one they meant,
     and moving them to a results screen with no result on it would
     answer a question they have not asked yet. The map appears where
     they are, under the form. */
  const showTheWorld = useCallback(async () => {
    setBusy(true);
    setError(null);
    setPlan(null);
    stream.reset();
    try {
      await prepare();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prepare]);

  const runOne = useCallback(async () => {
    if (!profileId || !mission || !choice.stack || !choice.local_config) return;
    /* Before the first await, not after the last one. The reader pressed
       Run to watch something happen, so the screen that shows it has to
       be up while it is happening — and it has to be up even when
       nothing moves, because "the planner refused" is a result too and
       the setup form is not where it is reported. */
    setStage("results");
    setBusy(true);
    setError(null);
    setPlan(null);
    stream.reset();
    try {
      const episode = await prepare();
      if (!episode) return;
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
  }, [prepare, t]);

  /** Back to the setup screen, with every field exactly as it was left.
   *
   * **Nothing is cleared.** Deployment, mission, candidate and seed are
   * why the reader is here: they came back to change *one* of them and
   * run again, and a blank form would make them retype the three they
   * were happy with. The staged world stays up for the same reason — it
   * is the world they are about to edit the conditions of.
   *
   * **The frames are left where they are, and that is deliberate.**
   * `stream.reset()` rewinds the playhead and stops the clock; it cannot
   * drop the frames, because only `connect` does that
   * (`useEpisodeStream.ts`) and calling it would mean running another
   * episode. So the previous trajectory is still held by the hook while
   * the setup screen is up. It is never drawn there: the setup screen's
   * canvas is fed the deployment's world and none of the stream, and the
   * console that draws a run is hidden. The next Run clears them through
   * `connect` before the first new frame arrives. A reader who comes
   * back and then runs nothing keeps a trajectory in memory that nothing
   * on screen claims belongs to what they are looking at.
   */
  const anotherBench = () => {
    setStage("setup");
    // The failure belonged to the run being left. Left standing over a
    // form the reader is now editing, it reads as a complaint about the
    // edit.
    setError(null);
    stream.reset();
  };

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

  const showingRun = stage === "results";
  const ready = Boolean(profileId && mission && choice.stack && choice.local_config);
  const episodeStatus = stream.status ?? (busy ? "running" : stream.frames.length > 0 ? "paused" : "ready");
  const statusTone = episodeStatus === "success"
    ? "success"
    : episodeStatus === "collision" || episodeStatus === "failed"
      ? "failed"
      : episodeStatus === "timeout"
        ? "timeout"
        : episodeStatus === "running"
          ? "running"
          : episodeStatus === "paused"
            ? "paused"
            : "ready";
  const runDisabledReason = session === null
    ? t("bench.signedOut")
    : !profileId
      ? t("bench.disabled.deployment")
      : !mission
        ? t("bench.disabled.mission")
        : !choice.stack || !choice.local_config
          ? t("bench.disabled.candidate")
          : null;

  return (
    <main className="simulate-page">
      <header className="page-head simulate-page-head">
        <span className="simulate-page-icon" aria-hidden="true"><Icon name="play" size={21} /></span>
        <div className="simulate-page-heading">
          <h2>{t("bench.title")}</h2>
          <p>{t("bench.subtitle")}</p>
        </div>
        {/* An episode's status, so it belongs to the screen that shows
            one. On the setup screen it would either say `ready`, which
            is not news, or still be reporting the run the reader has
            just stepped away from. */}
        <span className={`simulate-status simulate-status--${statusTone}`} hidden={!showingRun}>
          <span className="simulate-status-dot" aria-hidden="true" />
          {episodeStatus}
        </span>
      </header>

      {/* Stated before anything is run, not after. A reader who watches a
          clean episode and then finds out it counted for nothing has been
          told too late to have made a decision with it. */}
      <details className="simulate-notice">
        <summary>
          <span className="simulate-notice-icon" aria-hidden="true"><Icon name="info" size={18} /></span>
          <span><strong>{t("bench.noticeTitle")}</strong><small>{t("bench.noticeSummary")}</small></span>
          <Icon name="chevronDown" size={16} />
        </summary>
        <p>{t("bench.notEvidence")}</p>
      </details>

      {error ? <div className="error-box simulate-error"><Icon name="alert" size={18} /><span>{error}</span></div> : null}
      {stream.error ? (
        <div className="error-box simulate-error"><Icon name="alert" size={18} /><span>{t("simulate.stream", { message: stream.error })}</span></div>
      ) : null}

      {profiles.length === 0 ? (
        <div className="simulate-empty-banner">
          <EmptyState
            icon="cpu"
            title={t("bench.empty.title")}
            body={t("bench.empty.body")}
            actionHref="/deployments"
            actionLabel={t("bench.empty.action")}
          />
        </div>
      ) : null}

      {/* ---- The setup screen. ----
          Hidden rather than unmounted, like `DecisionTabs` does it: every
          field on it is a choice the reader made, and the way back from
          the results screen is meant to land them on the form they left
          rather than on an empty one. */}
      <section className="panel simulate-setup" aria-labelledby="simulate-setup-title" hidden={showingRun}>
        <div className="simulate-section-head">
          <span className="simulate-section-icon"><Icon name="cpu" size={18} /></span>
          <div><h3 id="simulate-setup-title">{t("bench.setupTitle")}</h3><p>{t("bench.setupSubtitle")}</p></div>
        </div>
        <div className="simulate-setup-grid">
          <fieldset className="simulate-setup-group simulate-setup-group--conditions">
            <legend>{t("bench.group.conditions")}</legend>
            <label className="field simulate-field">
              <span>
                {t("bench.deployment")}
                <Hint text={t("bench.help.deployment")} label={t("bench.deployment")} />
              </span>
            <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              {profiles.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.id}
                </option>
              ))}
            </select>
            </label>

            <label className="field simulate-field">
              <span>
                {t("bench.mission")}
                <Hint text={t("bench.help.mission")} label={t("bench.mission")} />
              </span>
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
          </fieldset>

          <fieldset className="simulate-setup-group simulate-setup-group--candidate">
            <legend>{t("bench.group.candidate")}</legend>
            <CandidatePicker
              label={t("bench.candidate")}
              value={choice}
              onChange={setChoice}
              stacks={stacks}
              configs={configs}
              disabled={busy}
              detailed
            />
          </fieldset>

          <fieldset className="simulate-setup-group simulate-setup-group--seed">
            <legend>{t("bench.group.reproducibility")}</legend>
            <label className="field simulate-field">
              <span>
                {t("bench.seed")}
                <Hint text={t("bench.seedNote")} label={t("bench.seed")} />
              </span>
              <input
                type="number"
                min={0}
                step={1}
                value={seed}
                onChange={(event) => setSeed(Math.max(0, Math.trunc(Number(event.target.value))))}
              />
            </label>
          </fieldset>
        </div>

        <div className="simulate-run-actions">
          <button
            type="button"
            className="primary simulate-run-button"
            disabled={busy || !ready || session === null}
            onClick={() => void runOne()}
          >
            {busy ? <span className="simulate-spinner" aria-hidden="true" /> : <Icon name="play" size={18} />}
            {busy ? t("bench.running") : t("bench.run")}
          </button>
          {/* Answering "what am I about to measure" before measuring
              it. The map and the declared traffic arrived only as a
              side effect of running, which is the wrong way round for
              a page whose job is to check a deployment before a
              300-episode comparison commits to it. */}
          <button className="simulate-world-button"
            type="button"
            disabled={busy || !ready || session === null}
            onClick={() => void showTheWorld()}
          >
            <Icon name="map" size={17} />
            {t("bench.showWorld")}
          </button>
          {runDisabledReason ? <p className="simulate-disabled-reason"><Icon name="info" size={15} />{runDisabledReason}</p> : null}
        </div>
      </section>

      {/* The world, on the screen that is choosing it.
       *
       * Show world stages a map without running anything, so its answer
       * has to arrive where the reader pressed it. The console's canvas
       * is the *episode*, and it is on the other screen now — sending
       * somebody there to look at a map would make previewing
       * indistinguishable from running, which is the one distinction
       * that button exists to draw.
       *
       * A second `MapView` rather than the console's, and it is a
       * smaller thing: the deployment's map, the mission's poses, the
       * traffic the document declares. Nothing from the stream, so the
       * frames the hook is still holding from a previous run cannot
       * surface here — and mounted only while there is a world, so the
       * setup form is not sitting under an empty frame. It carries no
       * state worth preserving across the switch, which is why this one
       * is a conditional and the panels below are `hidden`.
       */}
      {!showingRun && map ? (
        <section className="panel simulate-preview" aria-label={t("bench.previewTitle")}>
          <div className="simulate-map-head">
            <div>
              <strong>{t("bench.previewTitle")}</strong>
              <span>{staged ? `${profileId} · seed ${seed}` : t("bench.previewSubtitle")}</span>
            </div>
          </div>
          <MapView
            map={map}
            startPose={start ?? undefined}
            goalPose={goal ?? undefined}
            goalTolerance={deployment?.constraints?.goal_tolerance_m}
            robotRadius={deployment?.robot?.radius}
            positionUncertainty={safetyEnvelope(deployment?.environment?.sensor_noise)}
            robotPose={start}
            authoredTraffic={overlayOf(trafficOf(deployment as ProfileDraft | null), null)}
            showGrid={showGrid}
          />
        </section>
      ) : null}

      {/* What the deployment fixed, shown rather than editable. Every one
          of these is a condition the comparison will run under, and a
          field that let you nudge one "just for the preview" would make
          this a different experiment. */}
      {deployment ? (
        <section className={`panel deployment-conditions${conditionsExpanded ? " is-expanded" : " is-collapsed"}`} hidden={showingRun}>
          <header className="deployment-conditions-header">
            <span className="deployment-conditions-title-icon"><Icon name="check" size={18} /></span>
            <div><h3>{t("bench.conditions")}</h3><p>{t("bench.conditionsNote")}</p></div>
            <span className="deployment-conditions-lock" title={t("bench.conditionsLockedHint")}><Icon name="check" size={13} />{t("bench.conditionsLocked")}</span>
            <button type="button" className="deployment-conditions-toggle" aria-expanded={conditionsExpanded} onClick={() => setConditionsExpanded((current) => !current)}>{conditionsExpanded ? t("bench.conditionsCollapse") : t("bench.conditionsExpand")}<Icon name="chevronDown" size={14} /></button>
          </header>

          {!conditionsExpanded ? (
            <p className="deployment-conditions-summary">
              {t("bench.conditionsSummary", {
                start: start ? `${start.x.toFixed(2)}, ${start.y.toFixed(2)}` : "—",
                goal: goal ? `${goal.x.toFixed(2)}, ${goal.y.toFixed(2)}` : "—",
                radius: deployment.robot?.radius === undefined ? "—" : `${deployment.robot.radius} m`,
                /* Three answers here too. The collapsed line is the one
                   a reader sees first, so it is the worst place to
                   report a silence as a decision. */
                replanning:
                  deployment.replanning?.enabled === undefined
                    ? t("bench.notDeclared")
                    : deployment.replanning.enabled
                      ? t("bench.on")
                      : t("bench.off"),
                traffic: String(deployment.environment?.dynamic_obstacles?.length ?? 0),
              })}
            </p>
          ) : (
            <div className="deployment-conditions-grid">
              {/* Seven cards, from the table in `lib/benchConditions` rather
                  than from seven blocks written here. Rows written by hand
                  covered eleven of the profile's forty-odd fields and
                  nothing said which thirty were missing; declared as data,
                  the inventory is checked against the schema itself. */}
              {CONDITION_GROUPS.map((group) => (
                <ConditionGroup
                  key={group.tone}
                  group={group}
                  deployment={deployment}
                  mission={mission}
                  t={t}
                />
              ))}
            </div>
          )}
          {staged ? (
            <footer className="deployment-condition-footer" title={staged.episode_context_id}><span>{t("bench.contextId")}</span><code>{shortContextId(staged.episode_context_id)}</code><span>{t("bench.contextIdNote")}</span></footer>
          ) : null}
        </section>
      ) : null}

      {/* ---- The results screen. ----
          The way back sits above it, because the reader arrives at the
          top of it and the thing they want after "that was not it" is
          the form, not another scroll. */}
      <div className="simulate-stage-bar" hidden={!showingRun}>
        <button type="button" className="simulate-another-button" onClick={anotherBench}>
          <Icon name="refresh" size={16} />
          {t("bench.another")}
        </button>
        <p><Icon name="info" size={14} />{t("bench.anotherNote")}</p>
      </div>

      <section className="simulate-console" aria-label={t("bench.consoleTitle")} hidden={!showingRun}>
        <div className="simulate-playback">
          <div className="simulate-playback-buttons">
            <button className="simulate-play" onClick={stream.play} disabled={stream.frames.length === 0 || stream.playing} aria-label={t("simulate.play")}>
              <Icon name="play" size={17} /><span>{t("simulate.play")}</span>
            </button>
            <button onClick={stream.pause} disabled={!stream.playing} aria-label={t("simulate.pause")}>
              <span className="simulate-pause-icon" aria-hidden="true" /><span>{t("simulate.pause")}</span>
            </button>
            <button onClick={stream.reset} disabled={stream.frames.length === 0} aria-label={t("bench.replay")}>
              <Icon name="refresh" size={17} /><span>{t("bench.replay")}</span>
            </button>
          </div>
          <label className="simulate-speed">
            <span>{t("bench.speed")}</span>
            <select value={stream.speed} onChange={(event) => stream.setSpeed(Number(event.target.value))}>
              {[0.25, 0.5, 1, 2, 4, 8].map((value) => <option key={value} value={value}>{value}×</option>)}
            </select>
          </label>
          <div className="simulate-timeline">
            <input
              type="range"
              min={0}
              max={Math.max(stream.duration, 0.001)}
              step={0.01}
              value={stream.playhead}
              onChange={(event) => stream.seek(Number(event.target.value))}
              aria-label={t("simulate.timeline")}
              aria-valuetext={`${stream.playhead.toFixed(2)} / ${stream.duration.toFixed(2)} s`}
            />
            <span>{stream.playhead.toFixed(2)} / {stream.duration.toFixed(2)} s</span>
          </div>
          <span className={`simulate-status simulate-status--${statusTone}`}><span className="simulate-status-dot" aria-hidden="true" />{episodeStatus}</span>
          {stream.reason ? <span className="simulate-stop-reason">{stream.reason}</span> : null}
        </div>

        <div className="simulate-layers" role="group" aria-label={t("bench.layersTitle")}>
          <strong>{t("bench.layersTitle")}</strong>
          <label className="simulate-layer simulate-layer--grid">
            <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
            <span className="simulate-layer-swatch" aria-hidden="true" />{t("simulate.grid")}
          </label>
          <label className="simulate-layer simulate-layer--plan">
            <input type="checkbox" checked={showPlan} onChange={(e) => setShowPlan(e.target.checked)} />
            <span className="simulate-layer-swatch" aria-hidden="true" />{t("simulate.globalPath")}
          </label>
          <label className="simulate-layer simulate-layer--trajectory">
            <input type="checkbox" checked={showTrajectory} onChange={(e) => setShowTrajectory(e.target.checked)} />
            <span className="simulate-layer-swatch" aria-hidden="true" />{t("simulate.trajectory")}
          </label>
        </div>

        <div className={`simulate-workspace${busy ? " is-simulating" : ""}`}>
          <div className="panel simulate-map-panel">
            <div className="simulate-map-head">
              <div><strong>{t("bench.worldTitle")}</strong><span>{staged ? `${profileId} · seed ${seed}` : t("bench.worldSubtitle")}</span></div>
              <span className={`simulate-status simulate-status--${statusTone}`}><span className="simulate-status-dot" aria-hidden="true" />{episodeStatus}</span>
            </div>
          {map ? (
            <MapView
              map={map}
              startPose={start ?? undefined}
              goalPose={goal ?? undefined}
              goalTolerance={deployment?.constraints?.goal_tolerance_m}
              robotRadius={deployment?.robot?.radius}
              positionUncertainty={safetyEnvelope(deployment?.environment?.sensor_noise)}
              /* **The route in force at this instant, not the one the
                 episode set out on.** The socket used to send one plan
                 and nothing after it, so a replanning episode drew its
                 opening route for the whole run — a dashed line sitting
                 still while the robot drove somewhere else, which reads
                 as a controller ignoring its plan rather than as a plan
                 that was replaced.

                 Falls back to `planPath` when the replans could not be
                 placed or the server predates them: the opening route is
                 still true, and drawing nothing would lose the plan
                 entirely over a decoration. */
              plannedPath={currentRoute?.points ?? (stream.planPath.length > 0 ? stream.planPath : plan?.path)}
              plannedPathColour={currentRoute ? plannedRouteColour(currentRoute.attempt) : undefined}
              trajectory={visibleTrajectory}
              robotPose={robotPose}
              collisionPoint={collisionPoint}
              dynamicObstacles={traffic}
              obstacleSnapshots={stream.currentFrame?.obstacles ?? []}
              /* The routes the deployment declares, drawn from the
                 document rather than from a run.
               *
               * Before this the only traffic on screen came out of the
               * episode stream, so a deployment's obstacles did not
               * exist until after it had been simulated — and an
               * obstacle that starts parked at its stopping place
               * looked like a stray circle rather than like a route
               * somebody wrote. Teal says what was declared; the amber
               * markers say where the engine actually had them. */
              authoredTraffic={overlayOf(trafficOf(deployment as ProfileDraft | null), null)}
              previewTime={stream.playhead}
              showGrid={showGrid}
              showPlan={showPlan}
              showTrajectory={showTrajectory}
            />
          ) : (
            <div className="simulate-map-placeholder">
              <span><Icon name="map" size={28} /></span>
              <strong>{t("bench.worldEmptyTitle")}</strong>
              <p>{t("bench.selectDeployment")}</p>
            </div>
          )}
          {/* **The wait has a face now.** `runOne` awaits the whole
              episode before the socket opens, so between the press and
              the first frame the canvas sits there holding the world as
              it was — indistinguishable from an app that has stopped.
              The overlay covers the canvas rather than replacing it: the
              map underneath is still the answer to "did it take my
              deployment", and blanking it would throw that away to say
              something the spinner already says.

              `aria-live="polite"` because a screen reader gets nothing
              from a spinner; `role="status"` announces the line once
              when it appears and once when it goes. */}
          {busy ? (
            <div className="simulate-map-busy" role="status" aria-live="polite">
              <span className="simulate-map-busy-spinner" aria-hidden="true" />
              <p>{t("bench.simulating")}</p>
            </div>
          ) : null}
          </div>

          <aside className="simulate-side-panel">
          <div className={`panel simulate-status-panel simulate-status-panel--${statusTone}`}>
            <div className="simulate-section-head simulate-section-head--compact"><span className="simulate-section-icon"><Icon name="cpu" size={17} /></span><div><h3>{t("simulate.robotState")}</h3><p>{t("bench.robotStateSubtitle")}</p></div></div>
            {stream.currentFrame ? (
              <dl className="simulate-telemetry">
                <div><dt>{t("bench.telemetry.time")}</dt><dd>{stream.currentFrame.time.toFixed(2)} <small>s</small></dd></div>
                <div><dt>X</dt><dd>{stream.currentFrame.x.toFixed(2)} <small>m</small></dd></div>
                <div><dt>Y</dt><dd>{stream.currentFrame.y.toFixed(2)} <small>m</small></dd></div>
                <div><dt>θ</dt><dd>{stream.currentFrame.theta.toFixed(2)} <small>rad</small></dd></div>
                <div><dt>{t("bench.telemetry.linear")}</dt><dd>{stream.currentFrame.linear_velocity.toFixed(2)} <small>m/s</small></dd></div>
                <div><dt>{t("bench.telemetry.angular")}</dt><dd>{stream.currentFrame.angular_velocity.toFixed(2)} <small>rad/s</small></dd></div>
                <div className="simulate-telemetry-status"><dt>{t("bench.telemetry.status")}</dt><dd><span className={`simulate-status simulate-status--${statusTone}`}>{episodeStatus}</span></dd></div>
                {stream.reason ? <div className="simulate-telemetry-reason"><dt>{t("bench.telemetry.reason")}</dt><dd>{stream.reason}</dd></div> : null}
              </dl>
            ) : (
              <div className="simulate-mini-empty"><Icon name="cpu" size={22} /><p>{t("simulate.noEpisode")}</p></div>
            )}
          </div>

          <div className="panel simulate-next-card">
            <span className="simulate-next-icon"><Icon name="benchmark" size={19} /></span>
            <h3>{t("bench.nextTitle")}</h3>
            <p className="muted">{t("bench.nextNote")}</p>
            <Link href="/decisions" className={`button-link${stream.frames.length > 0 ? " primary" : ""}`}>
              {t("bench.toComparison")}<Icon name="chevronRight" size={16} />
            </Link>
          </div>
          </aside>
        </div>
      </section>

      {/* Read off the run itself, not off a trace — so they are the right
          numbers for "did that look sane" and the wrong ones for any
          claim, which is what HĐ-5 means by the trace being the sole
          input of the Metrics Engine. */}
      <section className="simulate-metrics" hidden={!showingRun}>
        <MetricsPanel
          metrics={stream.metrics}
          plan={plan}
          // Straight from the deployment rather than from the run: it is
          // the same value the episode was staged with, and it is the one
          // that answers "did the setting arrive at all".
          replanning={deployment ? { enabled: Boolean(deployment.replanning?.enabled) } : undefined}
        />
        <p className="simulate-metrics-note"><Icon name="info" size={15} />{t("bench.metricsNote")}</p>
      </section>
    </main>
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
  const on = activeNoiseNames(noise);
  return on.length > 0 ? on.join(", ") : t("bench.noiseNone");
}

function activeNoiseNames(noise: Record<string, number | boolean> | undefined): string[] {
  if (!noise) return [];
  return Object.entries(noise)
    .filter(([key, value]) => key !== "active" && typeof value === "number" && value > 0)
    .map(([key]) => key);
}

function shortContextId(value: string): string {
  return value.length <= 16 ? value : `${value.slice(0, 8)}…${value.slice(-6)}`;
}

/** One row of a condition card, with absence as its own answer.
 *
 * **The three states are the point.** A row that printed `Off` for a
 * flag the profile never carried would say the author chose to switch
 * replanning off, and `0` for a missing amplitude would say they
 * measured the site as silent. Both are statements nobody made. So an
 * undeclared field gets a chip of its own, visually unlike both the
 * on badge and a number.
 */
function ConditionCell({ display, t }: { display: ConditionDisplay; t: Translate }) {
  if (display.state === "undeclared") {
    return (
      <span className="condition-status is-unset" title={t("bench.notDeclaredHint")}>
        {t("bench.notDeclared")}
      </span>
    );
  }
  if (display.state === "on" || display.state === "off") {
    const on = display.state === "on";
    return (
      <span className={`condition-status ${on ? "is-on" : "is-off"}`}>
        <Icon name={on ? "check" : "close"} size={12} />
        {on ? t("bench.on") : t("bench.off")}
      </span>
    );
  }
  return <>{display.text}</>;
}

/** One card: a group of the inventory, resolved against this profile.
 *
 * The noise summary is the one row not in the table, and deliberately:
 * the seven amplitudes above it answer "what is declared", and this
 * answers "which of them are actually on" — which is what tells
 * somebody at a glance that the episode runs under a drift they forgot
 * they declared.
 */
function ConditionGroup({
  group,
  deployment,
  mission,
  t,
}: {
  group: ConditionGroupSpec;
  deployment: Deployment;
  mission: Mission | null;
  t: Translate;
}) {
  return (
    <section className={`deployment-condition-group deployment-condition-group--${group.tone}`}>
      <header><span><Icon name={group.icon} size={16} /></span><h4>{t(group.titleKey)}</h4></header>
      <dl className="deployment-condition-list">
        {group.fields.map((field) => (
          <div className="deployment-condition-row" key={field.path}>
            <dt>{t(field.labelKey)}</dt>
            <dd><ConditionCell display={describeCondition(field, conditionValue(deployment, mission, field), t)} t={t} /></dd>
          </div>
        ))}
        {group.tone === "sensing" ? (
          <div className="deployment-condition-row deployment-condition-row--noise">
            <dt>{t("bench.noise")}</dt>
            <dd className="condition-noise-tags">{activeNoiseNames(deployment.environment?.sensor_noise).length > 0 ? activeNoiseNames(deployment.environment?.sensor_noise).map((name) => <span key={name} title={name}>{name}</span>) : <span className="condition-status is-off">{t("bench.noiseNone")}</span>}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
