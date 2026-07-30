"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, API_BASE } from "@/lib/api";
import type { MapSummary, SimulationResource } from "@/lib/types";

export default function DashboardPage() {
  const [health, setHealth] = useState<{ status: string; version: string } | null>(null);
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [simulations, setSimulations] = useState<SimulationResource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [healthResult, mapList, simulationList] = await Promise.all([
          api.health(),
          api.listMaps(),
          api.listSimulations(),
        ]);
        if (cancelled) return;
        setHealth(healthResult);
        setMaps(mapList);
        setSimulations(simulationList);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <h2>Dashboard</h2>
      {error ? (
        <div className="error-box">
          Backend unreachable at <code>{API_BASE}</code>: {error}
          <br />
          Start it with{" "}
          <code>
            PYTHONPATH=&quot;packages/schemas:packages/planning:packages/metrics:services/simulator:apps/api&quot;
            .venv/bin/uvicorn planbench_api.main:app --port 8000
          </code>
        </div>
      ) : null}
      {loading ? <p className="muted">Loading…</p> : null}

      <div className="panel">
        <h3>Backend</h3>
        {health ? (
          <p>
            <span className="badge ok">{health.status}</span> version {health.version} at{" "}
            <code>{API_BASE}</code>
          </p>
        ) : (
          <p className="muted">No response yet.</p>
        )}
      </div>

      <div className="panel">
        <h3>Maps ({maps.length})</h3>
        {maps.length === 0 ? (
          <p className="muted">
            No maps yet — <Link href="/maps">create one</Link>.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Resolution</th>
                <th>Version</th>
              </tr>
            </thead>
            <tbody>
              {maps.map((map) => (
                <tr key={map.id}>
                  <td>
                    <Link href={`/maps/${map.id}`}>{map.name}</Link>
                  </td>
                  <td>
                    {map.width} × {map.height} cells
                  </td>
                  <td>{map.resolution} m</td>
                  <td>v{map.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Recent simulations ({simulations.length})</h3>
        {simulations.length === 0 ? (
          <p className="muted">
            None yet — go to <Link href="/simulate">Live Simulation</Link>.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Algorithm</th>
                <th>State</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {simulations.slice(-10).reverse().map((simulation) => (
                <tr key={simulation.id}>
                  <td>
                    <code>{simulation.id}</code>
                  </td>
                  <td>{simulation.algorithm}</td>
                  <td>
                    <span className={`badge ${simulation.state === "finished" ? "ok" : "warn"}`}>
                      {simulation.state}
                    </span>
                  </td>
                  <td className="muted">{simulation.created_at.slice(0, 19).replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
