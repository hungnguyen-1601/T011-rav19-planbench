"use client";

/** Benchmark detail: approval workflow, comparison, replay, diagnosis.
 *
 * The replay offers a top-down and a 2.5D view of the same recorded
 * episode. Both read the same trajectory — the view is presentation, and
 * switching it never changes a number.
 */

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FailureFindings } from "@/components/FailureFindings";
import { JobProgress } from "@/components/JobProgress";
import { MapCanvas } from "@/components/MapCanvas";
import { MetricIntervalChart } from "@/components/MetricIntervalChart";
import { Scene25D } from "@/components/Scene25D";
import { SendForReview } from "@/components/SendForReview";
import { SplitBadge } from "@/components/SplitBadge";
import { StateBadge } from "@/components/StateBadge";
import { authFetch, useSession } from "@/lib/auth";
import { buildIntervalSeries, INTERVAL_METRICS } from "@/lib/charts";
import { useTranslation } from "@/lib/i18n";
import { downloadReportMarkdown } from "@/lib/reports";
import { cancelReview, canAcceptResult, canRun, pendingFor, type ReviewStage } from "@/lib/reviews";
import type {
  BenchmarkReport,
  BenchmarkResults,
  EpisodeReplay,
  EpisodeSummary,
} from "@/lib/benchmarkTypes";
import type { FailureReport } from "@/lib/platformTypes";
import type { MapResource, ScenarioResource } from "@/lib/types";

function fmt(value: number | null | undefined, digits = 2, suffix = ""): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

/** Tooltip text for a cell whose headline number is a median.
 *
 *  The spread lives in the title rather than the cell because a table
 *  with three numbers per cell stops being readable — but it has to be
 *  reachable, or the median alone implies a precision the runs do not
 *  have. */
function spreadTitle(
  iqr: [number, number] | null,
  ci: [number, number] | null,
  digits: number,
): string {
  const parts: string[] = [];
  if (iqr) parts.push(`IQR ${iqr[0].toFixed(digits)}–${iqr[1].toFixed(digits)}`);
  if (ci) parts.push(`CI95 ${ci[0].toFixed(digits)}–${ci[1].toFixed(digits)}`);
  return parts.join(" · ");
}

function ciTitle(ci: [number, number] | null, digits: number): string {
  return ci ? `CI95 ${ci[0].toFixed(digits)}–${ci[1].toFixed(digits)}` : "";
}

export default function BenchmarkDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useTranslation();
  const session = useSession();
  const [results, setResults] = useState<BenchmarkResults | null>(null);
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>([]);
  const [replay, setReplay] = useState<EpisodeReplay | null>(null);
  const [map, setMap] = useState<MapResource | null>(null);
  const [scenario, setScenario] = useState<ScenarioResource | null>(null);
  const [failure, setFailure] = useState<{ episodeId: string; report: FailureReport } | null>(null);
  const [view, setView] = useState<"top" | "25d">("top");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  // Which stage the "send for review" modal opens on, or null when closed.
  const [sending, setSending] = useState<ReviewStage | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await authFetch<BenchmarkResults>(`/benchmarks/${id}/results`);
      setResults(data);
      if (data.report) {
        setEpisodes(await authFetch<EpisodeSummary[]>(`/benchmarks/${id}/episodes`));
      }
      if (!map) {
        setMap(await authFetch<MapResource>(`/maps/${data.benchmark.map_id}`));
        const scenarios = await authFetch<ScenarioResource[]>("/scenarios");
        setScenario(scenarios.find((item) => item.id === data.benchmark.scenario_id) ?? null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [id, map]);

  useEffect(() => {
    if (!session) return;
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, session]);

  const act = async (action: string) => {
    setBusy(true);
    setError(null);
    try {
      const path = action === "run" ? `/benchmarks/${id}/run` : `/benchmarks/${id}/${action}`;
      await authFetch(path, {
        method: "POST",
        body: action === "run" ? undefined : JSON.stringify({ comment }),
      });
      setComment("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async (requestId: string) => {
    setBusy(true);
    setError(null);
    try {
      await cancelReview(requestId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const openReplay = async (episodeId: string) => {
    try {
      setReplay(await authFetch<EpisodeReplay>(`/episodes/${episodeId}/replay`));
      setFailure(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const openDiagnosis = async (episodeId: string) => {
    try {
      const report = await authFetch<FailureReport>(`/episodes/${episodeId}/failures`);
      setFailure({ episodeId, report });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!session) {
    return (
      <div className="panel">
        <p className="muted">
          <Link href="/login">{t("topbar.signIn")}</Link> — {t("common.signInTo")}
        </p>
      </div>
    );
  }
  if (!results) {
    return error ? (
      <div className="error-box">{error}</div>
    ) : (
      <p className="muted">{t("common.loading")}</p>
    );
  }

  const benchmark = results.benchmark;
  const state = benchmark.state;
  const isOwner = benchmark.is_owner;
  const requests = benchmark.review_requests ?? [];
  const pendingSpec = pendingFor(requests, "spec");
  const pendingResult = pendingFor(requests, "result");
  // Whether *this* member is the one being waited on. Shown so a
  // reviewer arriving from a link knows why the buttons are there.
  const iAmSpecReviewer = pendingSpec?.request.reviewer_user_id === session.user.id;
  const iAmResultReviewer = pendingResult?.request.reviewer_user_id === session.user.id;
  const blocking = pendingSpec ?? pendingResult;

  return (
    <>
      <div className="page-head">
        <h2>
          {/* The benchmark name is user-supplied: shown verbatim. */}
          {benchmark.spec.name} <StateBadge state={state} />
        </h2>
      </div>
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <h3>{t("detail.workflow")}</h3>
        <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
          {isOwner
            ? t("detail.ownerHint")
            : t("detail.readerHint", { name: benchmark.created_by })}
        </p>

        {blocking ? (
          <div className="notice">
            {t("detail.waitingOn", {
              name: blocking.reviewer?.nickname ?? "—",
              stage: t(`detail.stage.${blocking.request.stage}`),
            })}
            {blocking.request.request_comment ? ` — “${blocking.request.request_comment}”` : ""}.{" "}
            {iAmSpecReviewer || iAmResultReviewer
              ? t("detail.waitingOnYou")
              : isOwner
                ? t("detail.waitingBlocked")
                : ""}
          </div>
        ) : null}

        <div className="toolbar">
          <input
            placeholder={t("detail.commentPlaceholder")}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          />

          {isOwner ? (
            <>
              <button
                className="primary"
                disabled={busy || !canRun(isOwner, state, requests)}
                title={pendingSpec ? t("detail.blockedBySpec") : undefined}
                onClick={() => void act("run")}
              >
                {t("detail.run")}
              </button>
              <button
                className="primary"
                disabled={busy || !canAcceptResult(isOwner, state, requests)}
                title={pendingResult ? t("detail.blockedByResult") : undefined}
                onClick={() => void act("accept-result")}
              >
                {t("detail.acceptResults")}
              </button>
              <button
                disabled={busy || state !== "pending_review" || Boolean(pendingResult)}
                onClick={() => void act("reject-result")}
              >
                {t("detail.rejectResults")}
              </button>
              <button
                disabled={busy || !["pending_approval", "approved", "running"].includes(state)}
                onClick={() => void act("cancel")}
              >
                {t("detail.cancelRun")}
              </button>
              {blocking ? (
                <button disabled={busy} onClick={() => void withdraw(blocking.request.id)}>
                  {t("detail.cancelReview")}
                </button>
              ) : (
                <button
                  disabled={busy}
                  onClick={() => setSending(state === "pending_review" ? "result" : "spec")}
                >
                  {t("detail.sendForReview")}
                </button>
              )}
            </>
          ) : null}

          {iAmSpecReviewer ? (
            <>
              <button className="primary" disabled={busy} onClick={() => void act("approve")}>
                {t("detail.approveSpec")}
              </button>
              <button disabled={busy} onClick={() => void act("reject")}>
                {t("detail.rejectSpec")}
              </button>
            </>
          ) : null}
          {iAmResultReviewer ? (
            <>
              <button className="primary" disabled={busy} onClick={() => void act("accept-result")}>
                Accept results
              </button>
              <button disabled={busy} onClick={() => void act("reject-result")}>
                {t("detail.rejectResults")}
              </button>
            </>
          ) : null}
        </div>

        {requests.length > 0 ? (
          <>
            <h4>{t("detail.reviewRequests")}</h4>
            <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("detail.stageCol")}</th>
                  <th>{t("detail.reviewer")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("detail.asked")}</th>
                  <th>{t("detail.comments")}</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((view) => (
                  <tr key={view.request.id}>
                    <td>{view.request.stage}</td>
                    <td>{view.reviewer?.nickname ?? "—"}</td>
                    <td>
                      <span
                        className={`badge ${
                          view.request.status === "approved"
                            ? "ok"
                            : view.request.status === "pending"
                              ? ""
                              : "warn"
                        }`}
                      >
                        {t(`reviews.status.${view.request.status}`)}
                      </span>
                    </td>
                    <td className="muted">{view.request.request_comment || "—"}</td>
                    <td className="muted" style={{ whiteSpace: "pre-wrap" }}>
                      {view.request.review_comment || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        ) : null}

        <h4>{t("detail.auditTrail")}</h4>
        {benchmark.approvals.length > 0 ? (
          <div className="table-scroll wide">
          <table>
            <thead>
              <tr>
                <th>{t("detail.action")}</th>
                <th>{t("detail.user")}</th>
                <th>{t("detail.transition")}</th>
                <th>{t("common.comment")}</th>
                <th>{t("detail.when")}</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.approvals.map((entry, index) => (
                <tr key={index}>
                  <td>
                    {entry.action}
                    {entry.review_request_id ? (
                      <span className="muted" title="Answering a review request">
                        {" "}
                        ↩
                      </span>
                    ) : null}
                  </td>
                  <td>
                    {entry.user}
                    {entry.role === "admin" ? <span className="badge warn">admin</span> : null}
                  </td>
                  <td className="muted">
                    {entry.previous_state} → {entry.new_state}
                  </td>
                  <td className="muted">{entry.comment || "—"}</td>
                  <td className="muted">{new Date(entry.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        ) : (
          <p className="muted">{t("detail.noDecisions")}</p>
        )}
      </div>

      {sending ? (
        <SendForReview
          benchmarkId={id}
          defaultStage={sending}
          onSent={() => void refresh()}
          onClose={() => setSending(null)}
        />
      ) : null}

      <JobProgress benchmarkId={id} onFinished={() => void refresh()} canCancel={isOwner} />

      {results.report ? (
        <>
          <div className="panel">
            <h3>{t("detail.fairness")}</h3>
            <p className="muted" style={{ fontSize: 12 }}>
              {t("detail.fairnessHint")}
            </p>
            {results.report.scenario_split === "holdout" ? (
              <div className="notice">{t("protocol.holdoutBenchmarkNotice")}</div>
            ) : null}
            {results.report.scenario_split === "unassigned" ? (
              <div className="notice">{t("protocol.unassignedBenchmarkNotice")}</div>
            ) : null}
            <table>
              <tbody>
                <tr>
                  <td className="muted">{t("detail.conditionsChecksum")}</td>
                  <td>
                    <code>{results.report.fairness.conditions_checksum.slice(0, 24)}</code>
                  </td>
                </tr>
                <tr>
                  <td className="muted">{t("detail.mapScenario")}</td>
                  <td>
                    {results.report.fairness.map_name} / {results.report.fairness.scenario_name}
                  </td>
                </tr>
                <tr>
                  <td className="muted">{t("common.seeds")}</td>
                  <td>{results.report.fairness.seeds.join(", ")}</td>
                </tr>
                <tr>
                  {/* P05 snapshot: the split as it was when this ran, not
                      as it is today. Shown beside the checksum because it
                      is the same kind of fact — what this result is
                      allowed to be compared with. */}
                  <td className="muted">{t("protocol.split")}</td>
                  <td>
                    <SplitBadge split={results.report.scenario_split} />
                    {results.report.protocol_version ? (
                      <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                        {t("protocol.version")} {results.report.protocol_version}
                      </span>
                    ) : null}
                  </td>
                </tr>
                <tr>
                  <td className="muted">{t("detail.timeoutDt")}</td>
                  <td>
                    {results.report.fairness.timeout_seconds} s / {results.report.fairness.simulation_dt} s
                  </td>
                </tr>
                <tr>
                  <td className="muted">{t("detail.robot")}</td>
                  <td>
                    {results.report.fairness.robot_radius} m / {results.report.fairness.max_linear_velocity} m/s
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="panel">
            <h3>{t("detail.comparison")}</h3>
            <div className="table-scroll wide">
              <table>
                <thead>
                  <tr>
                    <th>{t("algorithms.stack")}</th>
                    <th>{t("detail.episodesCol")}</th>
                    <th>{t("detail.success")}</th>
                    <th>{t("detail.collision")}</th>
                    <th>{t("detail.timeout")}</th>
                    <th title={t("detail.medianHint")}>{t("detail.travelOk")}</th>
                    <th title={t("detail.medianHint")}>{t("detail.efficiency")}</th>
                    <th title={t("detail.medianHint")}>{t("detail.smoothness")}</th>
                    <th>{t("detail.clearance")}</th>
                    <th>{t("detail.latency")}</th>
                  </tr>
                </thead>
                <tbody>
                  {results.report.aggregates.map((aggregate) => (
                    <tr key={aggregate.algorithm}>
                      <td>{aggregate.algorithm}</td>
                      <td>{aggregate.episodes}</td>
                      <td title={ciTitle(aggregate.ci95_success_rate, 3)}>
                        {(aggregate.success_rate * 100).toFixed(0)}%
                      </td>
                      <td>{(aggregate.collision_rate * 100).toFixed(0)}%</td>
                      <td>{(aggregate.timeout_rate * 100).toFixed(0)}%</td>
                      {/* Median, not mean: one episode that dithered until
                       *  the timeout would drag a mean past anything that
                       *  actually happened. Spread and interval are in the
                       *  cell title so the table stays readable. */}
                      <td
                        title={spreadTitle(
                          aggregate.iqr_travel_time_successful,
                          aggregate.ci95_travel_time_successful,
                          2,
                        )}
                      >
                        {fmt(aggregate.median_travel_time_successful, 2, " s")}
                      </td>
                      <td
                        title={spreadTitle(
                          aggregate.iqr_path_efficiency_successful,
                          aggregate.ci95_path_efficiency_successful,
                          3,
                        )}
                      >
                        {fmt(aggregate.median_path_efficiency_successful, 3)}
                      </td>
                      <td
                        title={spreadTitle(
                          aggregate.iqr_smoothness_successful,
                          aggregate.ci95_smoothness_successful,
                          3,
                        )}
                      >
                        {fmt(aggregate.median_smoothness_successful, 3)}
                      </td>
                      <td>{fmt(aggregate.worst_min_clearance, 3, " m")}</td>
                      <td>{fmt((aggregate.mean_local_planning_latency ?? 0) * 1000, 1, " ms")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
              {t("detail.comparisonHint")}
            </p>
            <p className="muted" style={{ fontSize: 12 }}>
              {t("detail.medianHint")}
            </p>
          </div>

          <DistributionPanel report={results.report} />

          <StatisticsPanel report={results.report} />

          <ExportPanel benchmarkId={id} />

          <div className="panel">
            <h3>
              {t("detail.episodes")} ({episodes.length})
            </h3>
            <div className="table-scroll wide">
            <table>
              <thead>
                <tr>
                  <th>{t("algorithms.stack")}</th>
                  <th>{t("detail.seed")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("detail.travel")}</th>
                  <th>{t("detail.length")}</th>
                  <th>{t("detail.minClearance")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {episodes.map((episode) => (
                  <tr key={episode.id}>
                    <td>{episode.algorithm}</td>
                    <td>{episode.seed}</td>
                    <td>
                      <span
                        className={`badge ${episode.record.status === "success" ? "ok" : "err"}`}
                      >
                        {episode.record.status}
                      </span>
                    </td>
                    <td>{fmt(episode.record.metrics.travel_time, 2, " s")}</td>
                    <td>{fmt(episode.record.metrics.trajectory_length, 2, " m")}</td>
                    <td>{fmt(episode.record.metrics.min_clearance, 3, " m")}</td>
                    <td>
                      <button onClick={() => void openReplay(episode.id)}>
                        {t("detail.replay")}
                      </button>
                      <button
                        className="secondary"
                        onClick={() => void openDiagnosis(episode.id)}
                      >
                        {t("detail.diagnose")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        </>
      ) : (
        <div className="panel">
          <p className="muted">{t("detail.noResults")}</p>
        </div>
      )}

      {replay && map ? (
        <div className="panel">
          <div className="toolbar">
            <h3 style={{ margin: 0 }}>
              {t("detail.replayOf", { algorithm: replay.algorithm, seed: replay.seed })}
            </h3>
            <div className="view-toggle">
              <button
                type="button"
                aria-pressed={view === "top"}
                onClick={() => setView("top")}
              >
                {t("detail.topDown")}
              </button>
              <button
                type="button"
                aria-pressed={view === "25d"}
                onClick={() => setView("25d")}
              >
                {t("detail.view25d")}
              </button>
            </div>
          </div>
          {view === "top" ? (
            <MapCanvas
              map={map.map_data}
              plannedPath={replay.plan_path}
              trajectory={replay.trajectory}
              startPose={scenario?.scenario.start_pose}
              goalPose={scenario?.scenario.goal_pose}
              robotPose={
                replay.trajectory.length > 0
                  ? replay.trajectory[replay.trajectory.length - 1]
                  : null
              }
              collisionPoint={
                replay.metrics.collision && replay.trajectory.length > 0
                  ? replay.trajectory[replay.trajectory.length - 1]
                  : null
              }
            />
          ) : (
            <Scene25D
              map={map.map_data}
              plannedPath={replay.plan_path}
              trajectory={replay.trajectory}
              startPose={scenario?.scenario.start_pose}
              goalPose={scenario?.scenario.goal_pose}
              robotRadius={scenario?.scenario.robot.radius ?? 0.3}
              robotPose={
                replay.trajectory.length > 0
                  ? replay.trajectory[replay.trajectory.length - 1]
                  : null
              }
            />
          )}
          <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            {t("detail.replayFooter", {
              points: replay.trajectory.length,
              status: replay.metrics.status,
            })}
            {replay.events.length > 0 ? ` · ${replay.events[replay.events.length - 1].message}` : ""}
          </p>
        </div>
      ) : null}

      {failure ? (
        <div className="panel">
          <h3>
            {t("detail.failureAnalysis")} — <code>{failure.episodeId}</code>
          </h3>
          <p className="muted">{t("detail.failureHint")}</p>
          <FailureFindings report={failure.report} />
        </div>
      ) : null}
    </>
  );
}

/** Median, IQR and CI95 as bars with two whiskers (F09).
 *
 * The table above already carries these numbers, with the spread in a
 * tooltip. That was a compromise — three numbers per cell stops being
 * readable — and it has a cost: a spread nobody hovers over is a spread
 * nobody sees. The chart is where the comparison happens, and it puts the
 * variation on screen without being asked.
 *
 * Two whiskers, and they mean different things: the wide one is the
 * interquartile range (how much the runs varied), the narrow one is the
 * bootstrap interval for the median (how well this many seeds pin it
 * down). The panel says so, because a chart with an unexplained error bar
 * gets read as whichever of the two the reader already had in mind.
 */
function DistributionPanel({ report }: { report: BenchmarkReport }) {
  const { t } = useTranslation();
  const drawn = INTERVAL_METRICS.map((metric) => ({
    metric,
    series: buildIntervalSeries(report.aggregates, metric),
  })).filter((one) => one.series.rows.length > 0);
  if (drawn.length === 0) return null;
  return (
    <div className="panel">
      <h3>{t("charts.distributions")}</h3>
      <p className="muted" style={{ fontSize: 12 }}>
        {t("charts.distributionsHint")}
      </p>
      {!report.statistically_adequate ? (
        <div className="error-box">
          {t("detail.fewSeedsWarning", { seeds: report.seed_count })}
        </div>
      ) : null}
      {drawn.map(({ metric, series }) => (
        <div key={metric.key} style={{ marginTop: 12 }}>
          <h4 style={{ marginBottom: 4 }}>
            {t(metric.labelKey)}
          </h4>
          <MetricIntervalChart series={series} digits={metric.digits} unit={metric.unit} />
          {series.missing.length > 0 ? (
            <p className="muted" style={{ fontSize: 12 }}>
              {t("charts.noDistribution", { algorithms: series.missing.join(", ") })}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

/** Take the whole report out of the platform (F09).
 *
 * The export is the deliverable this milestone is judged on: everything
 * P02 to P05 computed is worth nothing to a reviewer who cannot open it
 * without an account. The button reports the filename it saved rather
 * than a generic success — on a browser that silently drops downloads,
 * "saved X" is the difference between a working feature and a click that
 * appears to do nothing.
 */
function ExportPanel({ benchmarkId }: { benchmarkId: string }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      setSaved(await downloadReportMarkdown(benchmarkId));
    } catch (err) {
      setSaved(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h3>{t("charts.export")}</h3>
      <p className="muted" style={{ fontSize: 12 }}>
        {t("charts.exportHint")}
      </p>
      {error ? <div className="error-box">{error}</div> : null}
      <div className="toolbar">
        <button className="primary" disabled={busy} onClick={() => void download()}>
          {busy ? t("charts.exporting") : t("charts.downloadMarkdown")}
        </button>
        {saved ? (
          <span className="muted">{t("charts.exportSaved", { filename: saved })}</span>
        ) : null}
      </div>
    </div>
  );
}

/** Head-to-head tests (P04), with the caveats attached to each row.
 *
 *  Deliberately not a verdict. Every row shows the paired seed count and
 *  its own warning, and the panel refuses to call a result significant
 *  when the benchmark did not run enough seeds to say so — the p-value
 *  is still printed, because hiding it would be its own distortion, but
 *  it is printed next to the reason not to lean on it. */
function StatisticsPanel({ report }: { report: BenchmarkReport }) {
  const { t } = useTranslation();
  if (report.comparisons.length === 0) return null;
  return (
    <div className="panel">
      <h3>{t("detail.statistics")}</h3>
      <p className="muted" style={{ fontSize: 12 }}>
        {t("detail.statisticsHint")}
      </p>
      {!report.statistically_adequate ? (
        <div className="error-box">
          {t("detail.fewSeedsWarning", { seeds: report.seed_count })}
        </div>
      ) : null}
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("detail.pair")}</th>
              <th>{t("detail.metric")}</th>
              <th>{t("detail.pairedSeeds")}</th>
              <th>{t("detail.pValue")}</th>
              <th title={t("detail.effectSizeHint")}>{t("detail.effectSize")}</th>
              <th>{t("detail.verdict")}</th>
            </tr>
          </thead>
          <tbody>
            {report.comparisons.map((comparison) => (
              <tr key={`${comparison.algorithm_a}-${comparison.algorithm_b}-${comparison.metric}`}>
                <td>
                  <code>{comparison.algorithm_a}</code> vs{" "}
                  <code>{comparison.algorithm_b}</code>
                </td>
                <td>{comparison.metric}</td>
                <td>{comparison.paired_seed_count}</td>
                <td>{comparison.p_value === null ? "—" : comparison.p_value.toFixed(4)}</td>
                <td>{fmt(comparison.effect_size, 3)}</td>
                <td>
                  {comparison.p_value === null
                    ? t("detail.noTest")
                    : comparison.significant && report.statistically_adequate
                      ? t("detail.differenceFound")
                      : t("detail.noConclusion")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.comparisons
        .filter((comparison) => comparison.warning)
        .map((comparison) => (
          <p
            key={`${comparison.algorithm_a}-${comparison.algorithm_b}-warning`}
            className="muted"
            style={{ fontSize: 12 }}
          >
            <code>{comparison.algorithm_b}</code>: {comparison.warning}
          </p>
        ))}
      <p className="muted" style={{ fontSize: 12 }}>
        {t("detail.noStrongClaim")}
      </p>
    </div>
  );
}
