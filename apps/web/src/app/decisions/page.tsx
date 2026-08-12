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
import { useTranslation } from "@/lib/i18n";
import {
  coverage,
  listDecisions,
  listTaskProfiles,
  noCardReason,
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
