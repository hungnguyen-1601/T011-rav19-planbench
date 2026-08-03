"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { emptyBorderedMap, warehouseMap } from "@/lib/demoMap";
import { useTranslation } from "@/lib/i18n";
import type { MapSummary } from "@/lib/types";

export default function MapsPage() {
  const { t } = useTranslation();
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMaps(await api.listMaps());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
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
      <div className="page-head">
        <div>
          <h2>{t("maps.title")}</h2>
          <p>{t("maps.subtitle")}</p>
        </div>
      </div>

      {error ? (
        <div className="error-box">
          {error}{" "}
          <button onClick={() => void refresh()} style={{ marginLeft: 8 }}>
            {t("common.retry")}
          </button>
        </div>
      ) : null}

      <div className="toolbar">
        <button className="primary" disabled={busy} onClick={() => void create("warehouse")}>
          <Icon name="plus" size={14} /> {t("maps.newWarehouse")}
        </button>
        <button disabled={busy} onClick={() => void create("empty")}>
          {t("maps.newEmpty")}
        </button>
        <button disabled={busy} onClick={() => void refresh()} aria-label={t("common.refresh")}>
          <Icon name="refresh" size={14} /> {t("common.refresh")}
        </button>
        {busy ? <span className="spinner" aria-label={t("common.loading")} /> : null}
      </div>

      <div className="panel">
        {loading ? (
          <p className="muted">{t("common.loading")}</p>
        ) : maps.length === 0 ? (
          <EmptyState
            icon="map"
            title={t("maps.empty.title")}
            body={t("maps.empty.body")}
            actionHref="/library"
            actionLabel={t("nav.library")}
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("common.name")}</th>
                  <th>{t("maps.cells")}</th>
                  <th>{t("maps.resolution")}</th>
                  <th>{t("maps.version")}</th>
                  <th>{t("maps.checksum")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {maps.map((map) => (
                  <tr key={map.id}>
                    <td>
                      {/* Map names are user-supplied: shown verbatim. */}
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
                      <button
                        disabled={busy}
                        onClick={() => void remove(map.id)}
                        aria-label={`${t("maps.delete")} ${map.name}`}
                      >
                        {t("maps.delete")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
