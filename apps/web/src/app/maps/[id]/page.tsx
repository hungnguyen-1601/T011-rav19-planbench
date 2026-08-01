"use client";

/** Map editor: paint occupied/free/unknown cells and save a new version. */

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { MapCanvas } from "@/components/MapCanvas";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { FREE, OCCUPIED, UNKNOWN } from "@/lib/demoMap";
import { worldToCell } from "@/lib/transform";
import type { MapData } from "@/lib/types";

type Brush = "occupied" | "free" | "unknown";

const BRUSH_VALUE: Record<Brush, number> = {
  occupied: OCCUPIED,
  free: FREE,
  unknown: UNKNOWN,
};

export default function MapEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation();
  const { id } = use(params);
  const [map, setMap] = useState<MapData | null>(null);
  const [version, setVersion] = useState<number>(0);
  const [brush, setBrush] = useState<Brush>("occupied");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resource = await api.getMap(id);
        if (cancelled) return;
        setMap(resource.map_data);
        setVersion(resource.version);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const paint = useCallback(
    (x: number, y: number) => {
      setMap((current) => {
        if (!current) return current;
        const cell = worldToCell(current, x, y);
        if (!cell) return current;
        const index = cell.row * current.width + cell.col;
        const value = BRUSH_VALUE[brush];
        if (current.cells[index] === value) return current;
        const cells = [...current.cells];
        cells[index] = value;
        setDirty(true);
        return { ...current, cells };
      });
    },
    [brush],
  );

  const save = async () => {
    if (!map) return;
    try {
      const updated = await api.updateMap(id, map);
      setVersion(updated.version);
      setDirty(false);
      setError(null);
      setStatus(t("maps.savedAs", { version: updated.version }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (error && !map) return <div className="error-box">{error}</div>;
  if (!map) return <p className="muted">{t("maps.loadingMap")}</p>;

  return (
    <>
      <h2>
        {/* The map name is user-supplied: shown verbatim. */}
        {t("maps.editorTitle", { name: map.name })} <span className="muted">v{version}</span>
      </h2>
      {error ? <div className="error-box">{error}</div> : null}
      {status ? <p className="muted">{status}</p> : null}

      <div className="toolbar">
        <span className="muted">{t("maps.brushLabel")}</span>
        {(["occupied", "free", "unknown"] as Brush[]).map((option) => (
          <button
            key={option}
            className={brush === option ? "primary" : ""}
            onClick={() => setBrush(option)}
          >
            {t(`maps.brush.${option}`)}
          </button>
        ))}
        <button className="primary" disabled={!dirty} onClick={() => void save()}>
          {dirty ? t("maps.saveNewVersion") : t("maps.saved")}
        </button>
        <Link href="/simulate">{t("maps.runSimulation")}</Link>
      </div>

      <div className="panel">
        <MapCanvas map={map} onWorldClick={paint} onWorldDrag={paint} />
        <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
          {t("maps.editorHint", {
            width: map.width,
            height: map.height,
            resolution: map.resolution,
            worldWidth: (map.width * map.resolution).toFixed(1),
            worldHeight: (map.height * map.resolution).toFixed(1),
          })}
        </p>
      </div>
    </>
  );
}
