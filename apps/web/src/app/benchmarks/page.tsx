"use client";

/** Benchmark list + creation. Approval actions live on the detail page. */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authFetch, loadSession, type Session } from "@/lib/auth";
import type { AlgorithmInfo, BenchmarkResource } from "@/lib/benchmarkTypes";
import type { MapSummary, ScenarioResource } from "@/lib/types";

const STATE_BADGE: Record<string, string> = {
  draft: "warn",
  pending_approval: "warn",
  approved: "ok",
  running: "warn",
  pending_review: "warn",
  accepted: "ok",
  rejected: "err",
  failed: "err",
  cancelled: "err",
};

export default function BenchmarksPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [benchmarks, setBenchmarks] = useState<BenchmarkResource[]>([]);
  const [algorithms, setAlgorithms] = useState<AlgorithmInfo[]>([]);
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioResource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("dwa-baseline");
  const [mapId, setMapId] = useState("");
  const [scenarioId, setScenarioId] = useState("");
  const [selected, setSelected] = useState<string[]>(["astar+dwa"]);
  const [seedText, setSeedText] = useState("1,2,3");

  const refresh = useCallback(async () => {
    try {
      const [list, algorithmList, mapList, scenarioList] = await Promise.all([
        authFetch<BenchmarkResource[]>("/benchmarks"),
        authFetch<AlgorithmInfo[]>("/algorithms"),
        authFetch<MapSummary[]>("/maps"),
        authFetch<ScenarioResource[]>("/scenarios"),
      ]);
      setBenchmarks(list);
      setAlgorithms(algorithmList);
      setMaps(mapList);
      setScenarios(scenarioList);
      if (!mapId && mapList.length > 0) setMapId(mapList[0].id);
      if (!scenarioId && scenarioList.length > 0) setScenarioId(scenarioList[0].id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [mapId, scenarioId]);

  useEffect(() => {
    const current = loadSession();
    setSession(current);
    if (current) void refresh();
    // refresh identity changes each render; run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const seeds = seedText
        .split(",")
        .map((value) => Number(value.trim()))
        .filter((value) => Number.isInteger(value));
      await authFetch<BenchmarkResource>("/benchmarks", {
        method: "POST",
        body: JSON.stringify({
          name,
          map_id: mapId,
          scenario_id: scenarioId,
          algorithms: selected.map((id) => ({ id, config: {} })),
          seeds,
        }),
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!session) {
    return (
      <>
        <h2>Benchmarks</h2>
        <div className="panel">
          <p className="muted">
            Benchmarks require a signed-in Operator or Reviewer.{" "}
            <Link href="/login">Sign in</Link>.
          </p>
        </div>
      </>
    );
  }

  const isOperator = session.role === "operator" || session.role === "admin";

  return (
    <>
      <h2>Benchmarks</h2>
      {error ? <div className="error-box">{error}</div> : null}

      {isOperator ? (
        <div className="panel">
          <h3>New benchmark</h3>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <label className="field">
              Name
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="field">
              Map
              <select value={mapId} onChange={(event) => setMapId(event.target.value)}>
                {maps.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Scenario
              <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
                {scenarios.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.scenario.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Seeds (comma separated)
              <input value={seedText} onChange={(event) => setSeedText(event.target.value)} />
            </label>
            <button
              className="primary"
              disabled={busy || !mapId || !scenarioId || selected.length === 0}
              onClick={() => void create()}
            >
              Create draft
            </button>
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
              Stacks under test (same map, scenario and seeds for every one):
            </div>
            {algorithms.map((algorithm) => (
              <label key={algorithm.id} className="inline" style={{ marginRight: 16 }}>
                <input
                  type="checkbox"
                  checked={selected.includes(algorithm.id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, algorithm.id]
                        : current.filter((id) => id !== algorithm.id),
                    )
                  }
                />
                {algorithm.id}
                {algorithm.benchmarkable ? null : (
                  <span className="badge warn" title={algorithm.description}>
                    reference only
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>
      ) : null}

      <div className="panel">
        <h3>All benchmarks</h3>
        {benchmarks.length === 0 ? (
          <p className="muted">None yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Stacks</th>
                <th>Seeds</th>
                <th>State</th>
                <th>Created by</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((benchmark) => (
                <tr key={benchmark.id}>
                  <td>
                    <Link href={`/benchmarks/${benchmark.id}`}>{benchmark.spec.name}</Link>
                  </td>
                  <td>{benchmark.spec.algorithms.map((a) => a.id).join(", ")}</td>
                  <td>{benchmark.spec.seeds.join(", ")}</td>
                  <td>
                    <span className={`badge ${STATE_BADGE[benchmark.state] ?? "warn"}`}>
                      {benchmark.state}
                    </span>
                  </td>
                  <td className="muted">{benchmark.created_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
