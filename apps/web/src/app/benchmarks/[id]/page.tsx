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
import { Scene25D } from "@/components/Scene25D";
import { SendForReview } from "@/components/SendForReview";
import { StateBadge } from "@/components/StateBadge";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { cancelReview, canAcceptResult, canRun, pendingFor, type ReviewStage } from "@/lib/reviews";
import type {
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
                    <th>{t("detail.travelOk")}</th>
                    <th>{t("detail.efficiency")}</th>
                    <th>{t("detail.smoothness")}</th>
                    <th>{t("detail.clearance")}</th>
                    <th>{t("detail.latency")}</th>
                  </tr>
                </thead>
                <tbody>
                  {results.report.aggregates.map((aggregate) => (
                    <tr key={aggregate.algorithm}>
                      <td>{aggregate.algorithm}</td>
                      <td>{aggregate.episodes}</td>
                      <td>{(aggregate.success_rate * 100).toFixed(0)}%</td>
                      <td>{(aggregate.collision_rate * 100).toFixed(0)}%</td>
                      <td>{(aggregate.timeout_rate * 100).toFixed(0)}%</td>
                      <td>{fmt(aggregate.mean_travel_time_successful, 2, " s")}</td>
                      <td>{fmt(aggregate.mean_path_efficiency_successful, 3)}</td>
                      <td>{fmt(aggregate.mean_smoothness_successful, 3)}</td>
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
          </div>

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
