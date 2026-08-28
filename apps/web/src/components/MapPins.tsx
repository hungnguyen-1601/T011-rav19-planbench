"use client";

/** Which deployments run this map, and which of them are behind.
 *
 * **The question this answers is "why did my edit not change what the
 * bench ran?"** A deployment names its map by a path that carries the
 * version — `maps/custom/<id>__v2.pgm` — so editing a map writes a new
 * version and leaves every deployment filed before the edit pointing at
 * the walls its episodes were driven on.
 *
 * That is deliberate and load-bearing, not an oversight:
 * `episode_context_id` does not hash the map (HĐ-3.1), so moving a
 * deployment onto new walls under the same id would make every stored
 * run describe a world that no longer exists, with nothing to warn
 * anybody. What was missing was somebody being *told* — the editor said
 * "Saving creates a new map version" beside a "Run a simulation" link
 * and left the reader to conclude the new version was what would run.
 *
 * So the pinned version is stated, and the way forward is offered as
 * what it actually is: a **new deployment** on the current map, never an
 * edit of the old one. The refusal in `TaskProfileService.derive` says
 * the same thing in the same words; this is that rule made visible
 * before somebody hits it.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, type MapPins as MapPinsData } from "@/lib/api";
import { deriveTaskProfile } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

export function MapPins({ mapId, version }: { mapId: string; version: number }) {
  const { t } = useTranslation();
  const [pins, setPins] = useState<MapPinsData | null>(null);
  const [deriving, setDeriving] = useState<string | null>(null);
  const [newId, setNewId] = useState("");
  const [failed, setFailed] = useState<string | null>(null);
  const [made, setMade] = useState<string | null>(null);

  const reload = useCallback(() => {
    api
      .mapPins(mapId)
      .then(setPins)
      // Silent: this panel is context. A map editor that refuses to draw
      // because it could not list deployments would be worse than one
      // that simply does not mention them.
      .catch(() => setPins(null));
  }, [mapId]);

  // `version` is a dependency so that saving a new version re-asks —
  // every pin that was current a moment ago has just gone stale, and
  // that is precisely the moment the reader needs to be told.
  useEffect(reload, [reload, version]);

  const derive = async (from: string) => {
    setDeriving(from);
    setFailed(null);
    setMade(null);
    try {
      const created = await deriveTaskProfile({
        base_task_profile_id: from,
        new_id: newId.trim(),
        map_id: mapId,
      });
      setMade(created.id);
      setNewId("");
      reload();
    } catch (caught) {
      // Shown verbatim. The server refuses an id already in use, and a
      // mission whose goal now sits inside a wall somebody just painted
      // — the second is the one worth reading, and a rewritten sentence
      // would lose which mission it was.
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setDeriving(null);
    }
  };

  if (!pins || pins.pins.length === 0) return null;

  const stale = pins.pins.filter((pin) => pin.stale);

  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <div className="panel-head">
        <h3>{t("maps.pins.title")}</h3>
      </div>
      <p className="muted small">{t("maps.pins.why")}</p>

      {failed ? <div className="error-box">{failed}</div> : null}
      {made ? (
        <p className="muted">
          {t("maps.pins.made")} <Link href="/decisions">{made}</Link>
        </p>
      ) : null}

      <table>
        <thead>
          <tr>
            <th>{t("maps.pins.deployment")}</th>
            <th>{t("maps.pins.runsOn")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {pins.pins.map((pin) => (
            <tr key={pin.task_profile_id}>
              <td>
                <code>{pin.task_profile_id}</code>
              </td>
              <td>
                <span className={`badge ${pin.stale ? "warn" : "ok"}`}>
                  {t("maps.pins.version", { version: String(pin.pinned_version) })}
                </span>
                {pin.stale ? (
                  <div className="muted small">
                    {t("maps.pins.behind", { current: String(pins.current_version) })}
                  </div>
                ) : null}
              </td>
              <td>
                {/* Offered only where it is the answer. A deployment
                    already on the current version has nothing to move
                    to, and a button saying so would invite a second
                    identical deployment for no reason. */}
                {pin.stale ? (
                  <button
                    type="button"
                    disabled={deriving !== null || !newId.trim()}
                    onClick={() => void derive(pin.task_profile_id)}
                  >
                    {t("maps.pins.derive")}
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {stale.length > 0 ? (
        <div className="row" style={{ marginTop: 10, alignItems: "flex-end", gap: 12 }}>
          <label className="field" style={{ flex: "0 1 28ch" }}>
            <span>{t("maps.pins.newId")}</span>
            <input
              value={newId}
              onChange={(event) => setNewId(event.target.value)}
              placeholder={t("maps.pins.newIdHint")}
            />
          </label>
          <p className="muted small" style={{ flex: 1 }}>
            {t("maps.pins.newIdWhy")}
          </p>
        </div>
      ) : null}
    </div>
  );
}
