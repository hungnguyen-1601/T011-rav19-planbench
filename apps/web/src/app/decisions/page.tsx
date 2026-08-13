"use client";

/** Selection runs. Every run, not only the ones that ranked.
 *
 * The default filter is deliberately *no* filter. Four of the first five
 * comparisons produced no Decision Card, and a list that showed only the
 * ranked ones would present a platform where almost nothing happened —
 * while hiding exactly the runs that eliminated candidates. The "no
 * card" rows carry a reason chip instead of a recommendation, because
 * the three ways to end up without a card ask for three different next
 * actions.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { MapCanvas } from "@/components/MapCanvas";
import { api } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  cancelDecisionJob,
  coverage,
  deriveTaskProfile,
  jobIsLive,
  listDecisionJobs,
  listDecisions,
  listTaskProfiles,
  noCardReason,
  queueDecision,
  runOutcome,
  type CandidateChoice,
  type DecisionJob,
  type DecisionRun,
  type NoCardReason,
  type TaskProfileSummary,
} from "@/lib/decisions";
import type { MapData, MapSummary, Pose2D } from "@/lib/types";

type RankedFilter = "all" | "ranked" | "unranked";

/** The tone of a "no card" chip. Never `err`: none of these is a
 *  failure, and colouring them red is how a gate table starts reading
 *  like a broken run. */
const REASON_TONE: Record<Exclude<NoCardReason, null>, string> = {
  interrupted: "warn",
  gate_only: "muted-badge",
  no_survivors: "muted-badge",
};

export default function DecisionsPage() {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<DecisionRun[]>([]);
  const [profiles, setProfiles] = useState<TaskProfileSummary[]>([]);
  const [profileId, setProfileId] = useState("");
  const [rankedFilter, setRankedFilter] = useState<RankedFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [runList, profileList] = await Promise.all([
        listDecisions({
          taskProfileId: profileId || undefined,
          ranked: rankedFilter === "all" ? undefined : rankedFilter === "ranked",
        }),
        listTaskProfiles(),
      ]);
      setRuns(runList);
      setProfiles(profileList);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, [profileId, rankedFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section>
      <div className="page-head">
        <h1>{t("decisions.title")}</h1>
        <p className="muted">{t("decisions.subtitle")}</p>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <LaunchPanel profiles={profiles} onFinished={refresh} />

      <div className="panel">
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field">
            <span>{t("decisions.filter.deployment")}</span>
            <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              <option value="">{t("decisions.filter.allDeployments")}</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.id}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("decisions.filter.outcome")}</span>
            <select
              value={rankedFilter}
              onChange={(event) => setRankedFilter(event.target.value as RankedFilter)}
            >
              <option value="all">{t("decisions.filter.all")}</option>
              <option value="ranked">{t("decisions.filter.ranked")}</option>
              <option value="unranked">{t("decisions.filter.unranked")}</option>
            </select>
          </label>
        </div>
        {/* Said out loud rather than left to be inferred from the row
            count: a reader who filters to "ranked" and sees one row
            should know the others still exist. */}
        <p className="muted" style={{ marginTop: 8 }}>
          {t("decisions.filter.note")}
        </p>
      </div>

      {loading ? (
        <p className="muted">{t("common.loading")}</p>
      ) : runs.length === 0 ? (
        <EmptyState
          icon="benchmark"
          title={t("decisions.empty.title")}
          body={t("decisions.empty.body")}
        />
      ) : (
        <div className="panel">
          <div className="table-scroll">
            <table>
            <thead>
              <tr>
                <th>{t("decisions.column.deployment")}</th>
                <th>{t("decisions.column.scope")}</th>
                <th>{t("decisions.column.episodes")}</th>
                <th>{t("decisions.column.outcome")}</th>
                <th>{t("decisions.column.review")}</th>
                <th>{t("decisions.column.created")}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <DecisionRow key={run.id} run={run} />
              ))}
            </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

/** Start a sweep, and watch the one that is running.
 *
 * **Queued, never inline.** The episode count comes from the
 * deployment's declared collision risk (HĐ-7.1), so a warehouse at 1%
 * risk is 300 episodes and hours of simulation. A button that held the
 * browser open for that is not a design.
 *
 * **One at a time, and the reason is not capacity.** HĐ-7.4 forbids two
 * evaluation runs on one machine at once: both pin the same cores, each
 * becomes the other's background load, and G4 — which reads wall-clock
 * latency — then measures a machine that does not exist. The server's
 * queue holds one job; this panel says so rather than letting a second
 * click look ignored.
 */
function LaunchPanel({
  profiles,
  onFinished,
}: {
  profiles: TaskProfileSummary[];
  onFinished: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const session = useSession();
  const [profileId, setProfileId] = useState("");
  const [first, setFirst] = useState<CandidateChoice>({
    stack: "astar+dwa",
    local_config: "dwa_coarse",
  });
  const [second, setSecond] = useState<CandidateChoice>({
    stack: "rrtstar+dwa",
    local_config: "dwa_coarse",
  });
  const [episodes, setEpisodes] = useState("");
  const [jobs, setJobs] = useState<DecisionJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [custom, setCustom] = useState<CustomMap>(NO_CUSTOM_MAP);

  const live = jobs.filter(jobIsLive);
  const base = profiles.find((profile) => profile.id === profileId);
  const customReady =
    custom.mapId !== "" &&
    custom.newProfileId.trim() !== "" &&
    custom.start !== null &&
    custom.goal !== null;

  // Poll only while something is live. A page that keeps asking after
  // everything finished is a page that keeps a laptop awake.
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const fetched = await listDecisionJobs();
        if (cancelled) return;
        const wasLive = jobs.some(jobIsLive);
        setJobs(fetched);
        if (wasLive && !fetched.some(jobIsLive)) await onFinished();
      } catch {
        // A failed poll is not worth a red banner: the next one may
        // succeed, and the launch button reports its own errors.
      }
    };
    void tick();
    if (!jobs.some(jobIsLive)) return;
    const timer = setInterval(() => void tick(), 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.some(jobIsLive)]);

  const launch = async () => {
    setBusy(true);
    setError(null);
    try {
      const parsed = Number.parseInt(episodes, 10);
      // A custom map files a **new** deployment first, and the sweep
      // runs on that one. Editing the chosen deployment in place is what
      // the server refuses: the map is the world, `episode_context_id`
      // does not hash it (HĐ-3.1), and two worlds under one id would
      // give trace reuse episodes driven on walls that are gone.
      const target = customReady
        ? (
            await deriveTaskProfile({
              base_task_profile_id: profileId,
              new_id: custom.newProfileId.trim(),
              map_id: custom.mapId,
              missions: [
                {
                  id: "custom_route",
                  // [x, y, theta] — the contract's own YAML form. The
                  // start's heading is the direction the robot faces at
                  // t = 0, so it is part of the mission and not a
                  // drawing detail.
                  start: [custom.start!.x, custom.start!.y, custom.start!.theta],
                  goal: [custom.goal!.x, custom.goal!.y, custom.goal!.theta],
                  probability: 1,
                },
              ],
            })
          ).id
        : profileId;
      await queueDecision({
        task_profile_id: target,
        candidates: [first, second],
        // Omitted rather than sent as a number when blank: the default
        // is N_min from the deployment's declared risk, and inventing a
        // count here would quietly override the contract's arithmetic.
        ...(Number.isFinite(parsed) && parsed > 0 ? { episodes: parsed } : {}),
      });
      setJobs(await listDecisionJobs());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  if (!session) return null;

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.launch.title")}</h3>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="row" style={{ alignItems: "flex-end" }}>
        <label className="field">
          <span>{t("decisions.launch.deployment")}</span>
          <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
            <option value="">{t("decisions.launch.pick")}</option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.id}
              </option>
            ))}
          </select>
        </label>
        <CandidateFields
          label={t("decisions.launch.candidateA")}
          value={first}
          onChange={setFirst}
        />
        <CandidateFields
          label={t("decisions.launch.candidateB")}
          value={second}
          onChange={setSecond}
        />
        <label className="field">
          <span>{t("decisions.launch.episodes")}</span>
          <input
            value={episodes}
            onChange={(event) => setEpisodes(event.target.value)}
            placeholder={t("decisions.launch.episodesDefault")}
            inputMode="numeric"
          />
        </label>
        <button
          type="button"
          className="primary"
          disabled={
            busy ||
            !profileId ||
            live.length > 0 ||
            // Half-filled is worse than absent: it would silently run on
            // the deployment's own map while the reader believes they
            // chose another one.
            (custom.mapId !== "" && !customReady)
          }
          onClick={() => void launch()}
        >
          {customReady ? t("decisions.launch.submitDerived") : t("decisions.launch.submit")}
        </button>
      </div>

      <MapChoice
        base={base}
        value={custom}
        onChange={setCustom}
        disabled={busy || live.length > 0}
      />

      <p className="muted" style={{ marginTop: 8 }}>
        {live.length > 0 ? t("decisions.launch.oneAtATime") : t("decisions.launch.note")}
      </p>

      {jobs.length > 0 ? (
        <JobList
          jobs={jobs}
          onCancel={async (jobId) => {
            await cancelDecisionJob(jobId);
            setJobs(await listDecisionJobs());
          }}
        />
      ) : null}
    </div>
  );
}

/** The map a sweep runs on, when it should not be the deployment's own.
 *
 * **Empty `mapId` means "leave the deployment alone", and that is the
 * default.** Every existing flow keeps working without a click.
 */
/** What the next click on the map does.
 *
 * An explicit mode with a button and a caption, the way the scenario
 * editor has always done it, rather than a hidden alternation: the
 * author has to be able to *see* what the next click will do, or nudging
 * a start two pixels lands a goal instead.
 */
type PlacementMode = "none" | "start" | "goal";

interface CustomMap {
  mapId: string;
  newProfileId: string;
  /** Full poses, not points. The start's heading is the direction the
   *  robot is actually facing when the episode begins — the simulator
   *  seeds `RobotState(pose=start_pose)` from it — so a robot pointed
   *  away from its goal spends the first second turning around. */
  start: Pose2D | null;
  goal: Pose2D | null;
  placing: PlacementMode;
}

const NO_CUSTOM_MAP: CustomMap = {
  mapId: "",
  newProfileId: "",
  start: null,
  goal: null,
  placing: "start",
};

/** Pick a different map, and say where the robot drives on it.
 *
 * **Why this files a new deployment rather than editing one.** A map is
 * the world. `episode_context_id` hashes `(task_profile_id, mission_id,
 * environment_variant, seed)` and HĐ-3.1 freezes that payload — the map
 * is not in it. Swapping walls under an existing id would produce
 * contexts hashing identically to the old world's, and trace reuse would
 * serve episodes recorded somewhere that no longer exists. Nothing
 * warns; the ids match. So the panel asks for a new id, and the server
 * refuses the base's.
 *
 * **Why start and goal are required with a custom map.** A start and
 * goal that fit the reference hall are rarely on free floor in a
 * warehouse somebody drew. A goal inside a shelf gives 0% success for
 * *every* candidate, and the comparison then reports a tie between
 * stacks on a question none of them was asked — every column a plausible
 * 0.00, nothing in the numbers wrong. The server checks the pair against
 * the map before storing, so the mistake costs a refusal instead of
 * hours of simulation.
 *
 * **No editor here.** Drawing cells is `/maps`, which already versions
 * and checksums what it stores. A second editor would be a second
 * definition of the same thing.
 */
function MapChoice({
  base,
  value,
  onChange,
  disabled,
}: {
  base: TaskProfileSummary | undefined;
  value: CustomMap;
  onChange: (next: CustomMap) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const listed = await api.listMaps();
        if (!cancelled) setMaps(listed);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // The grid itself, only once a map is chosen. A map is a few hundred
  // thousand cells and this panel is on a page whose main job is a list.
  useEffect(() => {
    let cancelled = false;
    if (!value.mapId) {
      setMapData(null);
      return;
    }
    void (async () => {
      try {
        const resource = await api.getMap(value.mapId);
        if (!cancelled) {
          setMapData(resource.map_data);
          setError(null);
        }
      } catch (caught) {
        if (!cancelled) {
          setMapData(null);
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [value.mapId]);

  const robotRadius = readRobotRadius(base);
  const goalTolerance = readGoalTolerance(base);

  /** Move whichever pose the mode names, keeping its heading.
   *
   * Advances to `goal` only while the goal is still unset — the first
   * pass places two poses without a trip to the toolbar, and after that
   * the mode stays where the author put it. Otherwise correcting a start
   * would drop a goal on top of it.
   */
  const place = (x: number, y: number) => {
    if (disabled || value.placing === "none") return;
    if (value.placing === "start") {
      onChange({
        ...value,
        start: { x, y, theta: value.start?.theta ?? 0 },
        placing: value.goal === null ? "goal" : "start",
      });
    } else {
      onChange({ ...value, goal: { x, y, theta: value.goal?.theta ?? 0 } });
    }
  };

  return (
    <div style={{ marginTop: 12 }}>
      {error ? <div className="error-box">{error}</div> : null}

      <div className="row" style={{ alignItems: "flex-end" }}>
        <label className="field">
          <span>{t("decisions.map.label")}</span>
          <select
            value={value.mapId}
            disabled={disabled || !base}
            onChange={(event) =>
              // Reset the poses with the map. Keeping a start from the
              // previous map would leave a coordinate that means
              // something else here, and it might still be on free
              // floor — so nothing would catch it.
              onChange({ ...NO_CUSTOM_MAP, newProfileId: value.newProfileId, mapId: event.target.value })
            }
          >
            <option value="">{t("decisions.map.sameAsDeployment")}</option>
            {maps.map((map) => (
              <option key={map.id} value={map.id}>
                {map.name} · {map.width}×{map.height} · v{map.version}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">
          <Link href="/maps">{t("decisions.map.drawOne")}</Link>
        </span>
      </div>

      {/* Why the control is off, in words. A greyed-out select with no
          explanation reads as a broken page — and both reasons here are
          fixable by the reader in one click, so saying which one it is
          is the whole difference between stuck and not. */}
      {!base ? (
        <p className="muted" style={{ marginTop: 4 }}>
          {t("decisions.map.pickDeploymentFirst")}
        </p>
      ) : maps.length === 0 ? (
        <p className="muted" style={{ marginTop: 4 }}>
          {t("decisions.map.noMapsYet")}
        </p>
      ) : null}

      {value.mapId ? (
        <>
          <div className="row" style={{ alignItems: "flex-end", marginTop: 12 }}>
            <label className="field">
              <span>{t("decisions.map.newId")}</span>
              <input
                value={value.newProfileId}
                disabled={disabled}
                onChange={(event) => onChange({ ...value, newProfileId: event.target.value })}
                placeholder={base ? `${base.id}_custom` : "warehouse_b_v1"}
              />
            </label>
          </div>

          <p className="muted" style={{ marginTop: 8 }}>
            {t("decisions.map.note")}
          </p>

          {/* Explicit modes, and a caption saying what the next click
              does. The same shape the scenario editor uses, and for the
              same reason: a hidden alternation makes nudging a start
              land a goal. */}
          <div className="toolbar" style={{ marginTop: 12 }}>
            {(["start", "goal"] as const).map((which) => (
              <button
                key={which}
                type="button"
                disabled={disabled}
                className={value.placing === which ? "active" : undefined}
                aria-pressed={value.placing === which}
                onClick={() =>
                  onChange({ ...value, placing: value.placing === which ? "none" : which })
                }
              >
                {t(`decisions.map.place.${which}`)}
              </button>
            ))}
            <span className="muted">{t(`decisions.map.mode.${value.placing}`)}</span>
          </div>

          {mapData ? (
            <div style={{ marginTop: 8 }}>
              <MapCanvas
                map={mapData}
                startPose={value.start ?? undefined}
                goalPose={value.goal ?? undefined}
                robotRadius={robotRadius}
                goalTolerance={goalTolerance}
                onWorldClick={(x, y) => place(x, y)}
                onWorldDrag={(x, y) => place(x, y)}
              />
            </div>
          ) : (
            <p className="muted">{t("common.loading")}</p>
          )}

          {/* Typed as well as clicked. A canvas cannot land on 2.00
              exactly, and a deployment written down to two decimals is
              the one somebody can repeat from the report. */}
          <PoseFields
            label={t("decisions.map.start")}
            value={value.start}
            disabled={disabled}
            onChange={(pose) => onChange({ ...value, start: pose })}
            note={t("decisions.map.startHeadingNote")}
          />
          <PoseFields
            label={t("decisions.map.goal")}
            value={value.goal}
            disabled={disabled}
            onChange={(pose) => onChange({ ...value, goal: pose })}
            note={t("decisions.map.goalHeadingNote")}
          />
        </>
      ) : null}
    </div>
  );
}

const DEGREES = (radians: number) => (radians * 180) / Math.PI;
const RADIANS = (degrees: number) => (degrees * Math.PI) / 180;

/** One pose as three numbers, beside the canvas that draws it.
 *
 * Heading in **degrees**, like the scenario editor: the contract stores
 * radians and nobody types 1.5708 for a quarter turn.
 *
 * Both fields exist for both poses, and the difference between them is
 * in the note rather than in the controls — see the two note strings.
 * Hiding the goal's heading would leave the arrow the canvas draws
 * unexplained, which is a worse silence than an inert dial with a label.
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

/** The deployment's robot radius, for drawing the poses at true size.
 *
 * A start that looks clear at one pixel per cell can be a start the
 * robot does not fit in — which is one of the five disagreements the
 * server refuses, and the one that is invisible without the circle.
 */
function readRobotRadius(profile: TaskProfileSummary | undefined): number | undefined {
  const robot = profile?.profile?.robot as { radius?: unknown } | undefined;
  return typeof robot?.radius === "number" ? robot.radius : undefined;
}

/** How close counts as arrived, drawn as the goal's circle.
 *
 * The deployment's number, not a display default: an episode ends the
 * moment the robot is inside it, so a goal placed a tolerance-width from
 * a shelf is a different mission from one placed a metre out.
 */
function readGoalTolerance(profile: TaskProfileSummary | undefined): number | undefined {
  const constraints = profile?.profile?.constraints as { goal_tolerance_m?: unknown } | undefined;
  return typeof constraints?.goal_tolerance_m === "number"
    ? constraints.goal_tolerance_m
    : undefined;
}

function CandidateFields({
  label,
  value,
  onChange,
}: {
  label: string;
  value: CandidateChoice;
  onChange: (next: CandidateChoice) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={value.stack}
        onChange={(event) => onChange({ ...value, stack: event.target.value })}
        placeholder="astar+dwa"
      />
      <input
        value={value.local_config}
        onChange={(event) => onChange({ ...value, local_config: event.target.value })}
        placeholder="dwa_coarse"
      />
    </label>
  );
}

function JobList({
  jobs,
  onCancel,
}: {
  jobs: DecisionJob[];
  onCancel: (jobId: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  return (
    <div className="table-scroll" style={{ marginTop: 12 }}>
      <table>
        <thead>
          <tr>
            <th>{t("decisions.job.state")}</th>
            <th>{t("decisions.job.progress")}</th>
            <th>{t("decisions.job.detail")}</th>
            <th>{t("decisions.job.started")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>
                <span
                  className={`badge ${
                    job.state === "succeeded"
                      ? "ok"
                      : job.state === "failed"
                        ? "err"
                        : job.state === "cancelled"
                          ? "muted-badge"
                          : "warn"
                  }`}
                >
                  {t(`decisions.job.${job.state}`)}
                </span>
              </td>
              <td>
                {/* Episodes, from the sweep's own counter — the same
                    numbers it writes to the run journal. `total` is 0
                    until the first episode reports, and "0/0" is honest
                    where "0%" would be a claim. */}
                {job.total > 0 ? `${job.progress}/${job.total}` : "—"}
              </td>
              <td className="muted">
                {job.error ? job.error : job.run_id ? (
                  <Link href={`/decisions/${job.run_id}`}>{t("decisions.job.open")}</Link>
                ) : (
                  job.message || "—"
                )}
              </td>
              <td className="muted">
                {(job.started_at ?? job.created_at).slice(0, 16).replace("T", " ")}
              </td>
              <td>
                {/* Episodes already written stay written, and that is
                    the point rather than a leak: traces are keyed by
                    content hash, so re-running the same candidates on
                    the same deployment reuses every one of them. */}
                {jobIsLive(job) ? (
                  <button type="button" onClick={() => void onCancel(job.id)}>
                    {t("decisions.job.cancel")}
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DecisionRow({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const reason = noCardReason(run);
  const outcome = runOutcome(run);
  const covered = coverage(run);
  const requested = run.report?.sample?.n_episodes_requested;
  const measured = run.report?.sample?.n_episodes ?? 0;

  return (
    <tr>
      <td>
        <Link href={`/decisions/${run.id}`}>{run.task_profile_id}</Link>
      </td>
      <td className="muted">{run.experiment_scope ?? "—"}</td>
      <td>
        {/* Both counts when they differ. "245" alone reads as a
            deliberate 245-episode run, which is a different claim from
            "the machine was taken back at 245". */}
        {requested && requested !== measured ? (
          <span title={t("decisions.episodes.partial")}>
            {measured}/{requested}
            {covered !== undefined ? ` (${Math.round(covered * 100)}%)` : ""}
          </span>
        ) : (
          measured
        )}
      </td>
      <td>
        {/* The winner by name, not by hash. `recommended_candidate_id`
            is the right identity for a trace path and the wrong thing
            to put in front of somebody scanning ten rows for the run
            that chose something.
            The gate count travels with it either way: a recommendation
            out of two survivors and one out of five are different
            claims, and a run where nobody cleared the gates is not a
            failed run — it is a result (HĐ-7). */}
        {run.ranked ? (
          <>
            <span className="badge ok" title={run.status ?? undefined}>
              {outcome.winner}
            </span>
            <br />
            <span className="muted">
              {t("decisions.outcome.cleared", {
                cleared: String(outcome.cleared),
                total: String(outcome.total),
              })}
            </span>
          </>
        ) : (
          <>
            <span className={`badge ${REASON_TONE[reason!]}`}>
              {t(`decisions.reason.${reason}`)}
            </span>
            {outcome.total > 0 ? (
              <>
                <br />
                <span className="muted">
                  {t("decisions.outcome.cleared", {
                    cleared: String(outcome.cleared),
                    total: String(outcome.total),
                  })}
                </span>
              </>
            ) : null}
          </>
        )}
      </td>
      <td>
        <span className={`badge ${run.review_state === "reviewed" ? "ok" : "warn"}`}>
          {t(`decisions.review.${run.review_state}`)}
        </span>
        {run.config_state !== "not_applicable" ? (
          <span className="badge" style={{ marginLeft: 6 }}>
            {t(`decisions.config.${run.config_state}`)}
          </span>
        ) : null}
      </td>
      <td className="muted">{run.created_at.slice(0, 16).replace("T", " ")}</td>
    </tr>
  );
}
