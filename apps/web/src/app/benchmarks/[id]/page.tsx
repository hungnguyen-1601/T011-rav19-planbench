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
import { authFetch, loadSession, type Session } from "@/lib/auth";
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
  const [session, setSession] = useState<Session | null>(null);
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
    const current = loadSession();
    setSession(current);
    if (current) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

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
          <Link href="/login">Sign in</Link> to view benchmarks.
        </p>
      </div>
    );
  }
  if (!results) {
    return error ? <div className="error-box">{error}</div> : <p className="muted">Loading…</p>;
  }

  const benchmark = results.benchmark;
  const isOperator = session.role === "operator" || session.role === "admin";
  const isReviewer = session.role === "reviewer" || session.role === "admin";
  const state = benchmark.state;

  return (
    <>
      <h2>
        {benchmark.spec.name} <span className={`badge ${state === "accepted" ? "ok" : "warn"}`}>{state}</span>
      </h2>
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <h3>Human-in-the-loop</h3>
        <div className="toolbar">
          <input
            placeholder="Comment (recorded with the decision)"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          />
          {isOperator ? (
            <>
              <button disabled={busy || state !== "draft" && state !== "rejected"} onClick={() => void act("submit")}>
                Submit for approval
              </button>
              <button
                className="primary"
                disabled={busy || state !== "approved"}
                onClick={() => void act("run")}
              >
                Run benchmark
              </button>
              <button
                disabled={busy || !["pending_approval", "approved", "running"].includes(state)}
                onClick={() => void act("cancel")}
              >
                Cancel
              </button>
            </>
          ) : null}
          {isReviewer ? (
            <>
              <button disabled={busy || state !== "pending_approval"} onClick={() => void act("approve")}>
                Approve spec
              </button>
              <button disabled={busy || state !== "pending_approval"} onClick={() => void act("reject")}>
                Reject spec
              </button>
              <button
                className="primary"
                disabled={busy || state !== "pending_review"}
                onClick={() => void act("accept-result")}
              >
                Accept results
              </button>
              <button disabled={busy || state !== "pending_review"} onClick={() => void act("reject-result")}>
                Reject results
              </button>
            </>
          ) : null}
        </div>
        {benchmark.approvals.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Action</th>
                <th>User</th>
                <th>Role</th>
                <th>Transition</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.approvals.map((entry, index) => (
                <tr key={index}>
                  <td>{entry.action}</td>
                  <td>{entry.user}</td>
                  <td>{entry.role}</td>
                  <td className="muted">
                    {entry.previous_state} → {entry.new_state}
                  </td>
                  <td className="muted">{entry.comment || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">No decisions recorded yet.</p>
        )}
      </div>

      <JobProgress benchmarkId={id} onFinished={() => void refresh()} canCancel={isOperator} />

      {results.report ? (
        <>
          <div className="panel">
            <h3>Fairness evidence</h3>
            <p className="muted" style={{ fontSize: 12 }}>
              Every stack ran under these identical conditions. Two reports sharing a conditions
              checksum are directly comparable.
            </p>
            <table>
              <tbody>
                <tr>
                  <td className="muted">Conditions checksum</td>
                  <td>
                    <code>{results.report.fairness.conditions_checksum.slice(0, 24)}</code>
                  </td>
                </tr>
                <tr>
                  <td className="muted">Map / scenario</td>
                  <td>
                    {results.report.fairness.map_name} / {results.report.fairness.scenario_name}
                  </td>
                </tr>
                <tr>
                  <td className="muted">Seeds</td>
                  <td>{results.report.fairness.seeds.join(", ")}</td>
                </tr>
                <tr>
                  <td className="muted">Timeout / dt</td>
                  <td>
                    {results.report.fairness.timeout_seconds} s / {results.report.fairness.simulation_dt} s
                  </td>
                </tr>
                <tr>
                  <td className="muted">Robot radius / v_max</td>
                  <td>
                    {results.report.fairness.robot_radius} m / {results.report.fairness.max_linear_velocity} m/s
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="panel">
            <h3>Comparison</h3>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Stack</th>
                    <th>Episodes</th>
                    <th>Success</th>
                    <th>Collision</th>
                    <th>Timeout</th>
                    <th>Travel (ok)</th>
                    <th>Efficiency</th>
                    <th>Smoothness</th>
                    <th>Worst clearance</th>
                    <th>Latency</th>
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
              No single metric decides a winner: weigh safety (clearance, collision), success,
              efficiency, smoothness and computation together.
            </p>
          </div>

          <div className="panel">
            <h3>Episodes ({episodes.length})</h3>
            <table>
              <thead>
                <tr>
                  <th>Stack</th>
                  <th>Seed</th>
                  <th>Status</th>
                  <th>Travel</th>
                  <th>Length</th>
                  <th>Min clearance</th>
                  <th />
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
                      <button onClick={() => void openReplay(episode.id)}>Replay</button>
                      <button
                        className="secondary"
                        onClick={() => void openDiagnosis(episode.id)}
                      >
                        Diagnose
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="panel">
          <p className="muted">No results yet — the benchmark has not been run.</p>
        </div>
      )}

      {replay && map ? (
        <div className="panel">
          <div className="toolbar">
            <h3 style={{ margin: 0 }}>
              Replay — {replay.algorithm} (seed {replay.seed})
            </h3>
            <div className="view-toggle">
              <button
                type="button"
                aria-pressed={view === "top"}
                onClick={() => setView("top")}
              >
                Top-down
              </button>
              <button
                type="button"
                aria-pressed={view === "25d"}
                onClick={() => setView("25d")}
              >
                2.5D
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
            {replay.trajectory.length} trajectory points · status {replay.metrics.status}
            {replay.events.length > 0 ? ` · ${replay.events[replay.events.length - 1].message}` : ""}
          </p>
        </div>
      ) : null}

      {failure ? (
        <div className="panel">
          <h3>
            Failure analysis — episode <code>{failure.episodeId}</code>
          </h3>
          <p className="muted">
            Derived from recorded episode data only. Confidence is part of the finding: a{" "}
            <em>low</em> finding is a hypothesis consistent with the data, not a conclusion.
          </p>
          <FailureFindings report={failure.report} />
        </div>
      ) : null}
    </>
  );
}
