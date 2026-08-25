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
import { Hint } from "@/components/Hint";
import { EmptyState } from "@/components/EmptyState";
import { AdviceListView } from "@/components/AdviceListView";
import { CandidatePicker } from "@/components/CandidatePicker";
import { DecisionDeploymentPreview } from "@/components/DecisionDeploymentPreview";
import { Icon, type IconName } from "@/components/Icon";
import { MissionPlacer } from "@/components/MissionPlacer";
import { api } from "@/lib/api";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  cancelDecisionJob,
  coverage,
  deriveTaskProfile,
  jobIsLive,
  listDecisionJobs,
  listLocalControllers,
  listDecisions,
  listTaskProfiles,
  noCardReason,
  preflightDecision,
  queueDecision,
  runOutcome,
  type CandidateChoice,
  type DecisionJob,
  type DecisionRun,
  type LocalControllerConfig,
  type NoCardReason,
  type TaskProfileSummary,
} from "@/lib/decisions";
import {
  CONFLICT_KEY,
  EXPERIMENT_SCOPES,
  SCOPE_LABEL_KEY,
  SCOPE_NOTE_KEY,
  inferExperimentScope,
  readScopeViolation,
  scopeConflict,
  violationKey,
  type ExperimentScope,
} from "@/lib/experimentScope";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";
import type { MapData, MapSummary, Pose2D } from "@/lib/types";

type RankedFilter = "all" | "ranked" | "unranked";
type ReviewFilter = "all" | "unreviewed" | "reviewed" | "approved";

/** What has been measured, in four numbers.
 *
 * This is the overview `/leaderboard` used to provide, rebuilt on the
 * one thing it may rest on. The old page ranked **across scenarios**,
 * which HĐ-1.4 forbids: a recommendation is scoped to one deployment and
 * says nothing about any other map, mission or robot. Counting runs
 * carries none of that claim — "seven comparisons across three
 * deployments" is a fact about the work, not a ranking of candidates.
 */
function summarise(runs: DecisionRun[]) {
  return {
    runs: runs.length,
    ranked: runs.filter((run) => run.ranked).length,
    reviewed: runs.filter((run) => run.review_state === "reviewed").length,
    approved: runs.filter((run) => run.config_state === "approved").length,
    deployments: new Set(runs.map((run) => run.task_profile_id)).size,
  };
}

/** The tone of a "no card" chip. Never `err`: none of these is a
 *  failure, and colouring them red is how a gate table starts reading
 *  like a broken run. */
const REASON_TONE: Record<Exclude<NoCardReason, null>, string> = {
  interrupted: "warn",
  gate_only: "muted-badge",
  single_survivor: "muted-badge",
  no_survivors: "muted-badge",
};

export default function DecisionsPage() {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<DecisionRun[]>([]);
  const [profiles, setProfiles] = useState<TaskProfileSummary[]>([]);
  const [profileId, setProfileId] = useState("");
  const [rankedFilter, setRankedFilter] = useState<RankedFilter>("all");
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
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

  const shown = runs.filter((run) =>
    reviewFilter === "all"
      ? true
      : reviewFilter === "approved"
        ? run.config_state === "approved"
        : run.review_state === reviewFilter,
  );
  const totals = summarise(shown);
  // The utility column appears only once the list is one deployment.
  // `decision_utility` is comparable **within** a deployment and
  // meaningless across them (HĐ-1.4), and a sortable column of it over a
  // mixed list would rebuild the cross-scenario ranking this page exists
  // to replace — under a different name.
  const oneDeployment = profileId !== "";

  return (
    <section className="decision-page">
      <header className="page-head decision-page-head">
        <span className="decision-page-icon"><Icon name="benchmark" size={21} /></span>
        <div><h1>{t("decisions.title")}</h1><p className="muted">{t("decisions.workspaceSubtitle")}</p></div>
        {loading ? <span className="decision-running-badge"><span className="decision-spinner" />{t("common.loading")}</span> : null}
      </header>

      {error ? <div className="error-box">{error}</div> : null}

      <LaunchPanel profiles={profiles} onFinished={refresh} />

      <div className="decision-tally-panel">
        <div className="stat-grid decision-tallies">
          <Tally icon="benchmark" tone="blue" label={t("decisions.tally.runs")} value={totals.runs} />
          <Tally icon="map" tone="cyan" label={t("decisions.tally.deployments")} value={totals.deployments} />
          <Tally icon="trophy" tone="purple" label={t("decisions.tally.ranked")} value={totals.ranked} />
          <Tally icon="info" tone="orange" label={t("decisions.tally.reviewed")} value={totals.reviewed} />
          <Tally icon="check" tone="green" label={t("decisions.tally.approved")} value={totals.approved} />
        </div>
        {/* Counting is not ranking, and the distinction is the reason
            this replaced a leaderboard rather than moving one. Behind a
            mark, because it explains the row of counts rather than
            reporting anything. */}
        <Hint text={t("decisions.tally.note")} label={t("decisions.tally.reviewed")} />
      </div>

      <div className="decision-filter-bar">
        <div className="decision-filter-fields">
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
          <label className="field">
            <span>{t("decisions.filter.humanState")}</span>
            {/* Filtered here rather than on the server: both states are
                already on every row, and an endpoint parameter for them
                would be a second way to ask one question. */}
            <select
              value={reviewFilter}
              onChange={(event) => setReviewFilter(event.target.value as ReviewFilter)}
            >
              <option value="all">{t("decisions.filter.all")}</option>
              <option value="unreviewed">{t("decisions.filter.unreviewed")}</option>
              <option value="reviewed">{t("decisions.filter.reviewed")}</option>
              <option value="approved">{t("decisions.filter.approved")}</option>
            </select>
          </label>
        </div>
        {/* Said out loud rather than left to be inferred from the row
            count: a reader who filters to "ranked" and sees one row
            should know the others still exist. */}
        <span className="decision-result-count">
          {shown.length} {t("decisions.filter.results")}{" "}
          <Hint text={t("decisions.filter.note")} label={t("decisions.filter.results")} />
        </span>
      </div>

      {loading ? (
        <p className="muted">{t("common.loading")}</p>
      ) : shown.length === 0 ? (
        <EmptyState
          icon="benchmark"
          title={t("decisions.empty.title")}
          body={t("decisions.empty.body")}
        />
      ) : (
        <div className="panel decision-table-panel">
          <div className="table-scroll">
            <table>
            <thead>
              <tr>
                <th>{t("decisions.column.deployment")}</th>
                <th>{t("decisions.column.scope")}</th>
                <th>{t("decisions.column.episodes")}</th>
                <th>{t("decisions.column.outcome")}</th>
                {oneDeployment ? <th>{t("decisions.column.utility")}</th> : null}
                <th>{t("decisions.column.review")}</th>
                <th>{t("decisions.column.created")}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((run) => (
                <DecisionRow key={run.id} run={run} withUtility={oneDeployment} />
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
  /* `null` means "whatever the candidates say", which is the state this
     panel is in until somebody disagrees with the derivation — not a
     scope value, so changing a candidate keeps moving the scope with
     it. Storing the derived value here instead would freeze the first
     derivation and quietly stop tracking the picker. */
  const [scopeOverride, setScopeOverride] = useState<ExperimentScope | null>(null);
  const [jobs, setJobs] = useState<DecisionJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [custom, setCustom] = useState<CustomMap>(NO_CUSTOM_MAP);
  const [stacks, setStacks] = useState<AlgorithmInfo[]>([]);
  const [configs, setConfigs] = useState<LocalControllerConfig[]>([]);

  const live = jobs.filter(jobIsLive);
  const base = profiles.find((profile) => profile.id === profileId);
  const candidates = [first, second];
  const derivedScope = inferExperimentScope(candidates);
  const scope = scopeOverride ?? derivedScope;
  const conflict = scopeConflict(scope, candidates);
  const customReady =
    custom.mapId !== "" &&
    custom.newProfileId.trim() !== "" &&
    custom.start !== null &&
    custom.goal !== null;

  // What there is to choose between. Fetched once; a failure here is
  // deliberately silent because `CandidateFields` falls back to free
  // text — a convenience list that did not arrive must not take the
  // ability to start a sweep with it.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [registry, named] = await Promise.all([
          authFetch<AlgorithmInfo[]>("/algorithms"),
          listLocalControllers(),
        ]);
        if (cancelled) return;
        setStacks(registry);
        setConfigs(named);
      } catch {
        // Free-text inputs remain; nothing to say.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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

  const [preflight, setPreflight] = useState<import("@/lib/decisions").PreflightResult | null>(
    null,
  );
  const [checking, setChecking] = useState(false);

  /* The same body the launch would send — never a paraphrase. The
     expensive mistakes live in the details (an episode count below what
     the declared risk needs, two entries hashing to one identity), and a
     summary would smooth over exactly those. Advisory only: the launch
     button works regardless of what this says. */
  const check = async () => {
    setChecking(true);
    setError(null);
    try {
      const parsed = Number.parseInt(episodes, 10);
      setPreflight(
        await preflightDecision({
          task_profile_id: profileId,
          candidates: [first, second],
          ...(Number.isFinite(parsed) && parsed > 0 ? { episodes: parsed } : {}),
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setChecking(false);
    }
  };

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
        candidates,
        // Sent, never left out. The client's default is
        // `global_planner_selection`, so an omitted scope silently
        // declared a global-planner conclusion over whatever pair was
        // on the form — and every local-controller comparison, the
        // commoner one, was refused for a scope nobody chose.
        scope,
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
    <div className="panel comparison-setup">
      <div className="panel-head">
        <h3><Icon name="play" size={18} />{t("decisions.launch.title")}</h3>
      </div>

      {error ? <LaunchError message={error} /> : null}

      <div className="comparison-setup-grid">
        <fieldset className="comparison-common">
          <legend>{t("decisions.launch.common")}</legend>
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
        <label className="field">
          <span>{t("decisions.launch.episodes")}</span>
          <input
            value={episodes}
            onChange={(event) => setEpisodes(event.target.value)}
            placeholder={t("decisions.launch.episodesDefault")}
            inputMode="numeric"
          />
        </label>
        </fieldset>
        <div className="candidate-card candidate-a">
          <div className="candidate-card-head"><span><Icon name="cpu" size={18} /></span><div><small>Candidate A</small><strong>{first.stack || "—"}</strong></div></div>
        <CandidatePicker
          label={t("decisions.launch.candidateA")}
          value={first}
          onChange={setFirst}
          stacks={stacks}
          configs={configs}
          detailed
        />
        </div>
        <span className="candidate-vs" aria-hidden="true">VS</span>
        <div className="candidate-card candidate-b">
          <div className="candidate-card-head"><span><Icon name="cpu" size={18} /></span><div><small>Candidate B</small><strong>{second.stack || "—"}</strong></div></div>
        <CandidatePicker
          label={t("decisions.launch.candidateB")}
          value={second}
          onChange={setSecond}
          stacks={stacks}
          configs={configs}
          detailed
        />
        </div>
      </div>

      <ScopeField
        scope={scope}
        derived={derivedScope}
        overridden={scopeOverride !== null}
        conflict={conflict}
        onChange={setScopeOverride}
      />

      <DecisionDeploymentPreview deployment={base} />

      <div className="comparison-launch-actions">
        <button
          type="button"
          disabled={checking || !profileId || customReady}
          title={customReady ? t("preflight.disabledDerived") : undefined}
          onClick={() => void check()}
        >
          {checking ? t("preflight.checking") : t("preflight.check")}
        </button>
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
          {busy ? <span className="decision-spinner" /> : <Icon name="play" size={18} />}
          {customReady ? t("decisions.launch.submitDerived") : t("decisions.launch.submit")}
        </button>
        {(busy || !profileId || live.length > 0 || (custom.mapId !== "" && !customReady)) ? (
          <span className="comparison-disabled-reason"><Icon name="info" size={15} />{busy ? t("decisions.launch.busy") : !profileId ? t("decisions.launch.needDeployment") : live.length > 0 ? t("decisions.launch.oneAtATime") : t("decisions.launch.needMap")}</span>
        ) : null}
      </div>

      {preflight ? (
        <div style={{ marginTop: 10 }}>
          <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            {t("preflight.plan", {
              episodes: String(preflight.plan.episodes_per_candidate),
              total: String(preflight.plan.episode_runs_total),
              nmin: String(preflight.plan.n_min_required),
            })}
          </p>
          <AdviceListView result={preflight} />
        </div>
      ) : null}

      <MapChoice
        base={base}
        value={custom}
        onChange={setCustom}
        disabled={busy || live.length > 0}
      />

      <details className="comparison-explainer">
        <summary><Icon name="info" size={16} /><strong>{t("decisions.launch.howTitle")}</strong><Icon name="chevronDown" size={15} /></summary>
        {/* The queue warning stays on the page; the standing
            explanation of what a launch costs goes behind the mark. One
            is a fact about right now, the other is background. */}
        <p>{live.length > 0 ? t("decisions.launch.oneAtATime") : <Hint text={t("decisions.launch.note")} label={t("decisions.launch.title")} />} {" "}<Link href="/candidates">{t("decisions.launch.whatAreThese")}</Link></p>
      </details>

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

/** What this comparison is allowed to conclude about.
 *
 * **Derived, shown, and still editable.** The derivation is right for
 * every controlled swap — see `lib/experimentScope` — so the field opens
 * on the answer the two candidates already imply and nobody has to learn
 * the rule to queue a valid run. It stays editable because a reader may
 * be asking a question the pair does not spell out, and because a page
 * that silently decides on their behalf is how the old one shipped a
 * default nobody could see.
 *
 * **The warning does not disable the button.** The server validates the
 * scope again and is the authority; a client that refused first would be
 * a second implementation of HĐ-1.4, free to drift from it. What this
 * buys is the interval — the sweep is queued and runs for hours, so a
 * refusal that arrives before the click costs a re-pick and one that
 * arrives after costs an afternoon.
 */
function ScopeField({
  scope,
  derived,
  overridden,
  conflict,
  onChange,
}: {
  scope: ExperimentScope;
  derived: ExperimentScope;
  overridden: boolean;
  conflict: ReturnType<typeof scopeConflict>;
  onChange: (next: ExperimentScope | null) => void;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="comparison-scope">
      <legend>{t("decisions.launch.scope")}</legend>
      <div className="comparison-scope-row">
        <label className="field">
          <span>{t("decisions.launch.scope")}</span>
          <select
            value={scope}
            onChange={(event) => onChange(event.target.value as ExperimentScope)}
          >
            {EXPERIMENT_SCOPES.map((one) => (
              <option key={one} value={one}>
                {t(SCOPE_LABEL_KEY[one])}
              </option>
            ))}
          </select>
        </label>
        {overridden ? (
          <button type="button" onClick={() => onChange(null)}>
            {t("decisions.launch.scopeReset")}
          </button>
        ) : null}
      </div>
      {/* What this scope licenses a conclusion about — the whole reason
          the choice matters, and a sentence nobody would go looking for
          in the contract. */}
      <p className="muted comparison-scope-note">{t(SCOPE_NOTE_KEY[scope])}</p>
      <p className="muted comparison-scope-note">
        {overridden
          ? t("decisions.launch.scopeOverridden", { derived: t(SCOPE_LABEL_KEY[derived]) })
          : t("decisions.launch.scopeDerived")}
      </p>
      {conflict ? (
        <p className="notice notice--warn comparison-scope-note">{t(CONFLICT_KEY[conflict])}</p>
      ) : null}
    </fieldset>
  );
}

/** A launch refusal, in a sentence that names the next move.
 *
 * The scope violations are the ones worth translating: they arrive as
 * *"scope global_planner_selection requires an identical local layer
 * (component, version and parameters) in every candidate, found 2
 * variants across ['e1251e…', 'e4d2c…']"* — accurate, and addressed to
 * whoever wrote the validator. The reader needs one of two moves out of
 * it, and neither is in the sentence.
 *
 * **The server's own words stay, one fold down.** They carry the
 * candidate ids and the variant count, which is what anybody reporting
 * the problem needs, and a translation that turned out to be wrong
 * would otherwise have destroyed the evidence. Anything unrecognised is
 * shown verbatim: an error mistranslated is worse than one untranslated.
 */
function LaunchError({ message }: { message: string }) {
  const { t } = useTranslation();
  const violation = readScopeViolation(message);
  if (!violation) return <div className="error-box">{message}</div>;
  return (
    <div className="error-box">
      <p className="launch-error-headline">{t(violationKey(violation))}</p>
      <details className="launch-error-detail">
        <summary>{t("decisions.scope.violation.detail")}</summary>
        <code>{message}</code>
      </details>
    </div>
  );
}

/** The map a sweep runs on, when it should not be the deployment's own.
 *
 * **Empty `mapId` means "leave the deployment alone", and that is the
 * default.** Every existing flow keeps working without a click.
 */
interface CustomMap {
  mapId: string;
  newProfileId: string;
  /** Full poses, not points. The start's heading is the direction the
   *  robot is actually facing when the episode begins — the simulator
   *  seeds `RobotState(pose=start_pose)` from it — so a robot pointed
   *  away from its goal spends the first second turning around. */
  start: Pose2D | null;
  goal: Pose2D | null;
}

const NO_CUSTOM_MAP: CustomMap = {
  mapId: "",
  newProfileId: "",
  start: null,
  goal: null,
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
              {/* Attached to the id field, which is the control the note
                  is about: choosing a map files a *new* deployment
                  rather than editing the chosen one, and this box is
                  where its name goes. */}
              <span>
                {t("decisions.map.newId")}{" "}
                <Hint text={t("decisions.map.note")} label={t("decisions.map.newId")} />
              </span>
              <input
                value={value.newProfileId}
                disabled={disabled}
                onChange={(event) => onChange({ ...value, newProfileId: event.target.value })}
                placeholder={base ? `${base.id}_custom` : "warehouse_b_v1"}
              />
            </label>
          </div>



          {mapData ? (
            <MissionPlacer
              map={mapData}
              start={value.start}
              goal={value.goal}
              onChange={(poses) => onChange({ ...value, ...poses })}
              robotRadius={robotRadius}
              goalTolerance={goalTolerance}
              disabled={disabled}
              startNote={t("decisions.map.startHeadingNote")}
              goalNote={t("decisions.map.goalHeadingNote")}
            />
          ) : (
            <p className="muted">{t("common.loading")}</p>
          )}
        </>
      ) : null}
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

function JobList({
  jobs,
  onCancel,
}: {
  jobs: DecisionJob[];
  onCancel: (jobId: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  return (
    <div className="decision-progress-panel" aria-live="polite">
      <div className="decision-progress-head"><span><span className="decision-spinner" />{t("decisions.job.progress")}</span><strong>{jobs.filter(jobIsLive).length > 0 ? t("decisions.job.running") : t("decisions.job.finished")}</strong></div>
      {jobs.find(jobIsLive)?.total ? <div className="decision-progress-track"><span style={{ width: `${Math.min(100, (jobs.find(jobIsLive)!.progress / jobs.find(jobIsLive)!.total) * 100)}%` }} /></div> : null}
    <div className="table-scroll">
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
    </div>
  );
}

function DecisionRow({ run, withUtility }: { run: DecisionRun; withUtility: boolean }) {
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
      {withUtility ? (
        <td>
          {/* Six significant figures, because ΔU between two candidates
              is routinely in the fourth. Rounding it for tidiness would
              show two different recommendations as the same number. */}
          {run.card ? run.card.decision_utility.toFixed(6) : "—"}
        </td>
      ) : null}
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

/** One number with a label, for the tally strip. */
function Tally({ label, value, icon, tone }: { label: string; value: number; icon: IconName; tone: string }) {
  return (
    <div className={`stat-card decision-tally decision-tally--${tone}${value === 0 ? " is-zero" : ""}`}>
      <span className="decision-tally-icon"><Icon name={icon} size={17} /></span>
      <span className="stat-card-head">{label}</span>
      <span className="stat-card-value">{value}</span>
    </div>
  );
}
