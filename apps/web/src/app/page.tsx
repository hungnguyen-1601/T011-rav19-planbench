"use client";

/** Dashboard.
 *
 * What it used to be: a "BACKEND — version 0.1.0 at http://localhost:8000"
 * card, a table of maps, and a table of simulations. The version and the
 * URL told an ordinary user nothing they could act on, and told a
 * stranger where the API lives. Both moved to /system; what replaced
 * them is a small "System online" line and figures somebody might
 * actually decide something from.
 *
 * Every number comes from an endpoint that already existed — see
 * `lib/dashboard.ts` for why no `/dashboard/summary` was added — and a
 * figure that failed to load renders as "—", never as zero.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { QuickActions } from "@/components/QuickActions";
import { StatCard } from "@/components/StatCard";
import { StateBadge } from "@/components/StateBadge";
import { SystemStatus } from "@/components/SystemStatus";
import { useSession } from "@/lib/auth";
import {
  loadDashboard,
  pendingForMe,
  recentBenchmarks,
  recentSimulations,
  summarise,
  type DashboardData,
} from "@/lib/dashboard";
import { useTranslation } from "@/lib/i18n";

function shortTime(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

const NO_STATS = {
  benchmarks: null,
  accepted: null,
  pendingReviews: null,
  scenarios: null,
  algorithms: null,
  simulations: null,
};

export default function DashboardPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    loadDashboard()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  // Re-runs on sign-in and sign-out: which sections are fetchable at all
  // depends on having a session.
  const userId = session?.user.id ?? "";
  useEffect(() => {
    refresh();
  }, [refresh, userId]);

  const stats = data ? summarise(data) : NO_STATS;
  const benchmarks = data ? recentBenchmarks(data) : [];
  const simulations = data ? recentSimulations(data) : [];
  const reviews = data ? pendingForMe(data) : [];
  const signedIn = session !== null;
  const first = loading && !data;

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("dashboard.title")}</h2>
          <p>{t("dashboard.subtitle")}</p>
        </div>
        <SystemStatus
          status={first ? "checking" : data?.online ? "online" : "offline"}
          onRetry={refresh}
        />
      </div>

      {data?.partial && data.online ? <div className="notice">{t("dashboard.stale")}</div> : null}

      <div className="stat-grid">
        <StatCard
          icon="benchmark"
          label={t("dashboard.stats.benchmarks")}
          hint={t("dashboard.stats.benchmarksHint")}
          value={stats.benchmarks}
          loading={first}
          href="/benchmarks"
        />
        <StatCard
          icon="check"
          label={t("dashboard.stats.accepted")}
          hint={t("dashboard.stats.acceptedHint")}
          value={stats.accepted}
          loading={first}
          href="/leaderboard"
        />
        <StatCard
          icon="inbox"
          label={t("dashboard.stats.pendingReviews")}
          hint={t("dashboard.stats.pendingReviewsHint")}
          value={stats.pendingReviews}
          loading={first}
          href="/reviews"
        />
        <StatCard
          icon="library"
          label={t("dashboard.stats.scenarios")}
          hint={t("dashboard.stats.scenariosHint")}
          value={stats.scenarios}
          loading={first}
          href="/library"
        />
        <StatCard
          icon="cpu"
          label={t("dashboard.stats.algorithms")}
          hint={t("dashboard.stats.algorithmsHint")}
          value={stats.algorithms}
          loading={first}
          href="/algorithms"
        />
        <StatCard
          icon="play"
          label={t("dashboard.stats.simulations")}
          hint={t("dashboard.stats.simulationsHint")}
          value={stats.simulations}
          loading={first}
          href="/simulate"
        />
      </div>

      <QuickActions signedIn={signedIn} />

      <div className="dashboard-columns">
        <section className="panel">
          <div className="panel-head">
            <h3>{t("dashboard.recentBenchmarks")}</h3>
            <Link href="/benchmarks">{t("dashboard.viewAll")}</Link>
          </div>
          {!signedIn ? (
            <EmptyState
              icon="user"
              title={t("dashboard.empty.signedOut.title")}
              body={t("dashboard.empty.signedOut.body")}
              actionHref="/login"
              actionLabel={t("topbar.signIn")}
            />
          ) : benchmarks.length === 0 ? (
            <EmptyState
              icon="benchmark"
              title={t("dashboard.empty.benchmarks.title")}
              body={t("dashboard.empty.benchmarks.body")}
              actionHref="/benchmarks"
              actionLabel={t("dashboard.action.createBenchmark")}
            />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("common.name")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("common.created")}</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmarks.map((benchmark) => (
                    <tr key={benchmark.id}>
                      <td>
                        <Link href={`/benchmarks/${benchmark.id}`}>{benchmark.spec.name}</Link>
                      </td>
                      <td>
                        <StateBadge state={benchmark.state} />
                      </td>
                      <td className="muted">{shortTime(benchmark.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3>{t("dashboard.pendingRequests")}</h3>
            <Link href="/reviews">{t("dashboard.viewAll")}</Link>
          </div>
          {!signedIn ? (
            <EmptyState
              icon="user"
              title={t("dashboard.empty.signedOut.title")}
              body={t("dashboard.empty.signedOut.body")}
              actionHref="/login"
              actionLabel={t("topbar.signIn")}
            />
          ) : reviews.length === 0 ? (
            <EmptyState
              icon="inbox"
              title={t("dashboard.empty.reviews.title")}
              body={t("dashboard.empty.reviews.body")}
            />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("common.name")}</th>
                    <th>{t("reviews.from")}</th>
                    <th>{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {reviews.map((view) => (
                    <tr key={view.request.id}>
                      <td>
                        <Link href={`/benchmarks/${view.request.benchmark_id}`}>
                          {view.benchmark_name || view.request.benchmark_id}
                        </Link>
                      </td>
                      <td>{view.requested_by?.nickname ?? "—"}</td>
                      <td>
                        <span className="badge warn">
                          {view.request.stage === "spec"
                            ? t("reviews.specReview")
                            : t("reviews.resultReview")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3>{t("dashboard.recentSimulations")}</h3>
            <Link href="/simulate">{t("dashboard.viewAll")}</Link>
          </div>
          {simulations.length === 0 ? (
            <EmptyState
              icon="play"
              title={t("dashboard.empty.simulations.title")}
              body={t("dashboard.empty.simulations.body")}
              actionHref="/simulate"
              actionLabel={t("dashboard.action.startSimulation")}
            />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("common.algorithm")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("common.created")}</th>
                  </tr>
                </thead>
                <tbody>
                  {simulations.map((simulation) => (
                    <tr key={simulation.id}>
                      {/* Algorithm ids are protocol tokens: never translated. */}
                      <td>{simulation.algorithm}</td>
                      <td>
                        <span className={`badge ${simulation.state === "finished" ? "ok" : "warn"}`}>
                          {simulation.state}
                        </span>
                      </td>
                      <td className="muted">{shortTime(simulation.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
