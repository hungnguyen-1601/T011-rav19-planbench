"use client";

/** Built-in scenario library (M5), in curriculum order.
 *
 * Importing materialises the map and scenario server-side from
 * `build_scenario()`. The browser never authors geometry: two clients
 * importing the same entry must get byte-identical maps, or benchmarks
 * built from them would not be comparable.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Scene25D } from "@/components/Scene25D";
import { authFetch, useSession } from "@/lib/auth";
import type { ImportedScenario, LibraryEntry } from "@/lib/platformTypes";
import type { MapResource, ScenarioResource } from "@/lib/types";

interface Preview {
  name: string;
  map: MapResource;
  scenario: ScenarioResource;
}

export default function LibraryPage() {
  const session = useSession();
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<ImportedScenario[]>([]);

  useEffect(() => {
    (async () => {
      try {
        setEntries(await authFetch<LibraryEntry[]>("/scenario-library"));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  const importEntry = useCallback(async (name: string) => {
    setBusy(name);
    setError(null);
    try {
      const result = await authFetch<ImportedScenario>(`/scenario-library/${name}/import`, {
        method: "POST",
      });
      setImported((current) => [...current, result]);
      const [map, scenarios] = await Promise.all([
        authFetch<MapResource>(`/maps/${result.map_id}`),
        authFetch<ScenarioResource[]>("/scenarios"),
      ]);
      const scenario = scenarios.find((item) => item.id === result.scenario_id);
      if (scenario) setPreview({ name, map, scenario });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }, []);

  const canImport = session?.role === "operator" || session?.role === "admin";

  return (
    <>
      <h2>Scenario library</h2>
      <p className="muted">
        Ordered easiest to hardest — the same order the PPO curriculum uses. Importing creates a
        stored map and scenario you can benchmark against.
      </p>
      {!session ? (
        <div className="error-box">
          <Link href="/login">Sign in</Link> to browse and import the library.
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Scenario</th>
              <th>Description</th>
              <th>Size</th>
              <th>Dynamic</th>
              <th>Timeout</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.name}>
                <td className="muted">{entry.curriculum_index}</td>
                <td>
                  <code>{entry.name}</code>
                </td>
                <td>{entry.description}</td>
                <td className="muted">
                  {entry.map_size_m[0].toFixed(1)} × {entry.map_size_m[1].toFixed(1)} m
                </td>
                <td>
                  {entry.dynamic_obstacles > 0 ? (
                    <span className="badge warn">{entry.dynamic_obstacles} moving</span>
                  ) : (
                    <span className="muted">static</span>
                  )}
                </td>
                <td className="muted">{entry.timeout_seconds}s</td>
                <td>
                  <button
                    type="button"
                    disabled={!canImport || busy !== null}
                    onClick={() => importEntry(entry.name)}
                  >
                    {busy === entry.name ? "Importing…" : "Import"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {entries.length === 0 && !error ? <p className="muted">Loading…</p> : null}
        {session && !canImport ? (
          <p className="muted">Reviewers can browse the library; importing is an operator action.</p>
        ) : null}
      </div>

      {preview ? (
        <div className="panel">
          <h3>
            {preview.name} <span className="muted">2.5D preview</span>
          </h3>
          <Scene25D
            map={preview.map.map_data}
            width={720}
            height={460}
            startPose={preview.scenario.scenario.start_pose}
            goalPose={preview.scenario.scenario.goal_pose}
            robotPose={preview.scenario.scenario.start_pose}
            robotRadius={preview.scenario.scenario.robot.radius}
          />
          <p className="muted">
            Map <code>{preview.map.id}</code> · scenario <code>{preview.scenario.id}</code> — use
            them on the <Link href="/benchmarks">Benchmarks</Link> page.
          </p>
        </div>
      ) : null}

      {imported.length > 0 ? (
        <div className="panel">
          <h3>Imported this session</h3>
          <table>
            <thead>
              <tr>
                <th>Library entry</th>
                <th>Map</th>
                <th>Scenario</th>
              </tr>
            </thead>
            <tbody>
              {imported.map((item) => (
                <tr key={item.scenario_id}>
                  <td>
                    <code>{item.library_name}</code>
                  </td>
                  <td>
                    <Link href={`/maps/${item.map_id}`}>
                      <code>{item.map_id}</code>
                    </Link>
                  </td>
                  <td>
                    <code>{item.scenario_id}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
