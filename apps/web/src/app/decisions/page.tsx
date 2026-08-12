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
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  cancelDecisionJob,
  coverage,
  jobIsLive,
  listDecisionJobs,
  listDecisions,
  listTaskProfiles,
  noCardReason,
  queueDecision,
  type CandidateChoice,
  type DecisionJob,
  type DecisionRun,
  type NoCardReason,
  type TaskProfileSummary,
} from "@/lib/decisions";

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

  const live = jobs.filter(jobIsLive);

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
      await queueDecision({
        task_profile_id: profileId,
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
          disabled={busy || !profileId || live.length > 0}
          onClick={() => void launch()}
        >
          {t("decisions.launch.submit")}
        </button>
      </div>

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
        {run.ranked ? (
          <span className="badge ok" title={run.status ?? undefined}>
            {run.recommended_candidate_id}
          </span>
        ) : (
          <span className={`badge ${REASON_TONE[reason!]}`}>
            {t(`decisions.reason.${reason}`)}
          </span>
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
