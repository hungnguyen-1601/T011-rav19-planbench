"use client";

/** Map editor: paint occupied/free/unknown cells and save a new version. */

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { MapPainter } from "@/components/MapPainter";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { MapData } from "@/lib/types";

export default function MapEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation();
  const { id } = use(params);
  const [map, setMap] = useState<MapData | null>(null);
  const [version, setVersion] = useState<number>(0);
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

      <div className="panel">
        {/* Saving is the page's business, not the painter's: this page
            PUTs a new version by id, while the deployment form holds an
            unsaved grid until the profile is filed. The painter takes
            the button as a slot so both keep one toolbar row. */}
        <MapPainter
          map={map}
          onChange={(next) => {
            setMap(next);
            setDirty(true);
          }}
          actions={
            <>
              <button type="button" className="primary" disabled={!dirty} onClick={() => void save()}>
                {dirty ? t("maps.saveNewVersion") : t("maps.saved")}
              </button>
              <Link href="/simulate">{t("maps.runSimulation")}</Link>
            </>
          }
        />
        {/* Where the start and the goal are, since this is where people
            look for them. They are not on a map and cannot be: `MapData`
            is walls, and the same warehouse serves many missions. The
            pair belongs to the deployment that runs on this map, so it
            is chosen where that deployment is filed. */}
        <p className="muted" style={{ marginTop: 6, fontSize: 12 }}>
          {t("maps.whereArePoses")} <Link href="/decisions">{t("maps.posesLink")}</Link>
        </p>
      </div>
    </>
  );
}
