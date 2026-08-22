"use client";

/** Stored scenarios: the entry point of the scenario editor (plan 2.3).
 *
 * Two things this page is careful about:
 *
 * - Every row shows its evaluation split, and everything authored here
 *   is `unassigned`. There is no control to change that: promoting a
 *   scenario to dev or held-out is a reviewed protocol change (P05), not
 *   a choice its author makes about their own scenario.
 * - Difficulty is not shown per row. A scenario nobody has calibrated
 *   has no difficulty (P03), and inventing a placeholder for a brand-new
 *   scenario is exactly the guess the calibration exists to replace.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { SplitBadge } from "@/components/SplitBadge";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import type { MapSummary, ScenarioResource } from "@/lib/types";

export default function ScenariosPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [scenarios, setScenarios] = useState<ScenarioResource[]>([]);
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [items, mapList] = await Promise.all([
        authFetch<ScenarioResource[]>("/scenarios"),
        authFetch<MapSummary[]>("/maps"),
      ]);
      setScenarios(items);
      setMaps(mapList);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const remove = useCallback(
    async (id: string) => {
      setBusy(id);
      setError(null);
      try {
        await authFetch<void>(`/scenarios/${id}`, { method: "DELETE" });
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(null);
      }
    },
    [reload],
  );

  const mapName = (id: string) => maps.find((item) => item.id === id)?.name ?? id;
  const canEdit = Boolean(session);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("scenarios.title")}</h2>
          <p>{t("scenarios.subtitle")}</p>
        </div>
        <div>
          {canEdit ? <Link href="/scenarios/new">{t("scenarios.create")}</Link> : null}
        </div>
      </div>

      {!session ? (
        <div className="notice">
          <Link href="/login">{t("topbar.signIn")}</Link> — {t("common.signInRequired")}
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <div className="table-scroll wide">
          <table>
            <thead>
              <tr>
                <th>{t("common.scenario")}</th>
                <th>{t("common.map")}</th>
                <th title={t("protocol.splitHint")}>{t("protocol.split")}</th>
                <th>{t("scenarios.obstacles")}</th>
                <th>{t("common.created")}</th>
                <th>{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((item) => (
                <tr key={item.id}>
                  <td>
                    <code>{item.scenario.name}</code>
                  </td>
                  <td className="muted">{mapName(item.map_id)}</td>
                  <td>
                    <SplitBadge split={item.split} />
                  </td>
                  <td className="muted">
                    {t("scenarios.obstacleCount", {
                      static: String(item.scenario.static_obstacles?.length ?? 0),
                      dynamic: String(item.scenario.dynamic_obstacles?.length ?? 0),
                    })}
                  </td>
                  <td className="muted">{item.created_at}</td>
                  <td>
                    <Link href={`/scenarios/${item.id}`}>{t("scenarios.edit")}</Link>{" "}
                    <button
                      type="button"
                      disabled={!canEdit || busy !== null}
                      onClick={() => remove(item.id)}
                    >
                      {t("scenarios.delete")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loaded ? <p className="muted">{t("common.loading")}</p> : null}
        {loaded && scenarios.length === 0 ? (
          <EmptyState
            icon="library"
            title={t("scenarios.empty.title")}
            body={t("scenarios.empty.body")}
          />
        ) : null}
      </div>
    </>
  );
}
