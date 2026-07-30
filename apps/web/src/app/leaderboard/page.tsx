"use client";

/** Leaderboard (M5): stacks ranked within identical conditions.
 *
 * Groups are the whole point. Two rows only mean something next to each
 * other when they share a `conditions_checksum`; the UI therefore never
 * renders one flat table, because that would invite exactly the
 * cross-condition comparison the fairness record exists to prevent.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authFetch, useSession } from "@/lib/auth";
import type { Leaderboard, LeaderboardEntry, LeaderboardGroup } from "@/lib/platformTypes";

const DEFAULT_WEIGHTS = { success: 0.4, safety: 0.3, efficiency: 0.2, smoothness: 0.1 };

export default function LeaderboardPage() {
  const session = useSession();
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [acceptedOnly, setAcceptedOnly] = useState(true);
  const [scenario, setScenario] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        accepted_only: String(acceptedOnly),
        weight_success: String(weights.success),
        weight_safety: String(weights.safety),
        weight_efficiency: String(weights.efficiency),
        weight_smoothness: String(weights.smoothness),
      });
      if (scenario) query.set("scenario_name", scenario);
      setBoard(await authFetch<Leaderboard>(`/leaderboard?${query}`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [acceptedOnly, scenario, weights]);


  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <h2>Leaderboard</h2>
      {!session ? (
        <div className="error-box">
          <Link href="/login">Sign in</Link> to see ranked results.
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <h3>Scoring</h3>
        <div className="toolbar">
          {(Object.keys(DEFAULT_WEIGHTS) as (keyof typeof DEFAULT_WEIGHTS)[]).map((key) => (
            <label key={key} className="field">
              {key}
              <input
                type="number"
                min={0}
                step={0.05}
                value={weights[key]}
                onChange={(event) =>
                  setWeights({ ...weights, [key]: Math.max(0, Number(event.target.value)) })
                }
              />
            </label>
          ))}
          <label className="field">
            scenario filter
            <input
              value={scenario}
              placeholder="all scenarios"
              onChange={(event) => setScenario(event.target.value.trim())}
            />
          </label>
          <label className="inline">
            <input
              type="checkbox"
              checked={acceptedOnly}
              onChange={(event) => setAcceptedOnly(event.target.checked)}
            />
            accepted results only
          </label>
        </div>
        {!acceptedOnly ? (
          <div className="error-box">
            Showing results a reviewer has not accepted. These are provisional and must not be
            published as conclusions.
          </div>
        ) : null}
        {board ? <p className="muted formula">{board.score_formula}</p> : null}
      </div>

      {loading ? <p className="muted">Loading…</p> : null}

      {board && board.groups.length === 0 && !loading ? (
        <div className="panel">
          <p className="muted">
            Nothing to rank yet.{" "}
            {acceptedOnly
              ? "Only benchmarks a reviewer has accepted appear here — untick the box to inspect unreviewed runs."
              : "Run a benchmark first."}
          </p>
        </div>
      ) : null}

      {board?.groups.map((group) => <GroupTable key={group.conditions_checksum} group={group} />)}
    </>
  );
}

function GroupTable({ group }: { group: LeaderboardGroup }) {
  return (
    <div className="panel">
      <h3>
        {group.scenario_name} <span className="muted">on {group.map_name}</span>
      </h3>
      <p className="muted">
        seeds [{group.seeds.join(", ")}] · conditions <code>{group.conditions_checksum}</code>
      </p>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Stack</th>
            <th>Score</th>
            <th>Success</th>
            <th>Collision</th>
            <th>Travel (s)</th>
            <th>Efficiency</th>
            <th>Worst clearance</th>
            <th>Benchmark</th>
          </tr>
        </thead>
        <tbody>
          {group.entries.map((entry, index) => (
            <Row key={`${entry.benchmark_id}-${entry.algorithm}`} entry={entry} rank={index + 1} />
          ))}
        </tbody>
      </table>
      <p className="muted">
        Rows in different groups ran under different conditions and are not comparable.
      </p>
    </div>
  );
}

function Row({ entry, rank }: { entry: LeaderboardEntry; rank: number }) {
  return (
    <tr>
      <td className="muted">{rank}</td>
      <td>
        <code>{entry.algorithm}</code>
      </td>
      <td>
        {entry.overall_score === null ? (
          <span className="muted" title="no scorable component was recorded">
            —
          </span>
        ) : (
          <strong>{entry.overall_score.toFixed(3)}</strong>
        )}
      </td>
      <td>{(entry.success_rate * 100).toFixed(0)}%</td>
      <td>{(entry.collision_rate * 100).toFixed(0)}%</td>
      <td>{fmt(entry.mean_travel_time)}</td>
      <td>{fmt(entry.mean_path_efficiency, 3)}</td>
      <td>{fmt(entry.worst_min_clearance, 3)}</td>
      <td>
        <Link href={`/benchmarks/${entry.benchmark_id}`}>{entry.benchmark_name}</Link>
      </td>
    </tr>
  );
}

function fmt(value: number | null, digits = 2): string {
  return value === null ? "—" : value.toFixed(digits);
}
