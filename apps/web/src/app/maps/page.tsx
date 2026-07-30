"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { emptyBorderedMap, warehouseMap } from "@/lib/demoMap";
import type { MapSummary } from "@/lib/types";

export default function MapsPage() {
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setMaps(await api.listMaps());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = async (kind: "warehouse" | "empty") => {
    setBusy(true);
    try {
      const stamp = new Date().toISOString().slice(11, 19);
      const map =
        kind === "warehouse"
          ? warehouseMap(`warehouse-${stamp}`)
          : emptyBorderedMap(`empty-${stamp}`);
      await api.createMap(map);
      await refresh();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setBusy(true);
    try {
      await api.deleteMap(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>Maps</h2>
      {error ? <div className="error-box">{error}</div> : null}
      <div className="toolbar">
        <button className="primary" disabled={busy} onClick={() => void create("warehouse")}>
          New warehouse map
        </button>
        <button disabled={busy} onClick={() => void create("empty")}>
          New empty map
        </button>
        <button disabled={busy} onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="panel">
        {maps.length === 0 ? (
          <p className="muted">No maps stored. Create one to get started.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Cells</th>
                <th>Resolution</th>
                <th>Version</th>
                <th>Checksum</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {maps.map((map) => (
                <tr key={map.id}>
                  <td>
                    <Link href={`/maps/${map.id}`}>{map.name}</Link>
                  </td>
                  <td>
                    {map.width} × {map.height}
                  </td>
                  <td>{map.resolution} m</td>
                  <td>v{map.version}</td>
                  <td className="muted">
                    <code>{map.checksum.slice(0, 10)}</code>
                  </td>
                  <td>
                    <button disabled={busy} onClick={() => void remove(map.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
