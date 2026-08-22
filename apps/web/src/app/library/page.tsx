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
import { DifficultyBadge } from "@/components/DifficultyBadge";
import { EmptyState } from "@/components/EmptyState";
import { MapView } from "@/components/MapView";
import { SplitBadge } from "@/components/SplitBadge";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import type {
  DifficultyCalibrationSummary,
  ImportedScenario,
  LibraryEntry,
} from "@/lib/platformTypes";
import type { MapResource, ScenarioResource } from "@/lib/types";

interface Preview {
  name: string;
  map: MapResource;
  scenario: ScenarioResource;
}

export default function LibraryPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<ImportedScenario[]>([]);
  const [calibration, setCalibration] = useState<DifficultyCalibrationSummary | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setEntries(await authFetch<LibraryEntry[]>("/scenario-library"));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  // Separate request, and a failure here is deliberately not surfaced as
  // a page error: the difficulty scale is extra information about the
  // library, and losing it must not stop anyone from importing a
  // scenario.
  useEffect(() => {
    (async () => {
      try {
        setCalibration(
          await authFetch<DifficultyCalibrationSummary>("/difficulty-calibration"),
        );
      } catch {
        setCalibration(null);
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

  // Browsing is public; importing writes to the shared library and so
  // needs an account.
  const canImport = Boolean(session);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("library.title")}</h2>
          <p>{t("library.subtitle")}</p>
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
              <th title={t("library.curriculumHint")}>{t("library.curriculum")}</th>
              <th>{t("common.scenario")}</th>
              <th title={t("difficulty.hint")}>{t("library.difficulty")}</th>
              <th title={t("protocol.splitHint")}>{t("protocol.split")}</th>
              <th>{t("algorithms.description")}</th>
              <th>{t("maps.size")}</th>
              <th>{t("library.obstacles")}</th>
              <th>{t("library.timeout")}</th>
              <th>{t("common.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.name}>
                <td className="muted">{entry.curriculum_index}</td>
                <td>
                  <code>{entry.name}</code>
                </td>
                <td>
                  <DifficultyBadge difficulty={entry.difficulty} />
                </td>
                <td>
                  <SplitBadge split={entry.split} notes={entry.split_notes} />
                </td>
                <td>{entry.description}</td>
                <td className="muted">
                  {entry.map_size_m[0].toFixed(1)} × {entry.map_size_m[1].toFixed(1)} m
                </td>
                <td>
                  {entry.dynamic_obstacles > 0 ? (
                    <span className="badge warn">{entry.dynamic_obstacles}</span>
                  ) : (
                    <span className="muted">{t("common.none")}</span>
                  )}
                </td>
                <td className="muted">{entry.timeout_seconds}s</td>
                <td>
                  <button
                    type="button"
                    disabled={!canImport || busy !== null}
                    onClick={() => importEntry(entry.name)}
                  >
                    {busy === entry.name ? t("library.importing") : t("library.import")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        {entries.length === 0 && !error ? <p className="muted">{t("common.loading")}</p> : null}
        {entries.length === 0 && error ? (
          <EmptyState
            icon="library"
            title={t("library.empty.title")}
            body={t("library.empty.body")}
          />
        ) : null}
      </div>

      {calibration ? (
        <div className="panel">
          <h3>{t("difficulty.calibrationTitle")}</h3>
          {calibration.calibration_version && calibration.baseline ? (
            <p className="muted">
              {t("difficulty.calibrationMeta", {
                version: calibration.calibration_version,
                algorithm: calibration.baseline.algorithm,
                seeds: String(calibration.baseline.seeds.length),
                sha: calibration.baseline.git_sha.slice(0, 12),
                replanning: calibration.baseline.replanning_enabled
                  ? t("difficulty.replanningOn")
                  : t("difficulty.replanningOff"),
              })}
            </p>
          ) : (
            <p className="muted">{t("difficulty.uncalibratedHint")}</p>
          )}
          {calibration.coverage.spread !== null ? (
            <p className="muted">
              {t("difficulty.range", {
                min: (calibration.coverage.min_difficulty ?? 0).toFixed(2),
                max: (calibration.coverage.max_difficulty ?? 0).toFixed(2),
                spread: calibration.coverage.spread.toFixed(2),
                count: String(calibration.coverage.scenario_count),
              })}
            </p>
          ) : null}
          {/* Coverage warnings are the point of this panel, not a footnote:
              a difficulty scale everything sits at one end of cannot rank
              anything, and the fix is authoring scenarios, not editing the
              cache. */}
          {calibration.coverage.warnings.map((warning) => (
            <div className="notice notice--warn" key={warning}>
              {warning}
            </div>
          ))}
        </div>
      ) : null}

      {preview ? (
        <div className="panel">
          <h3>
            {preview.name} <span className="muted">{t("library.preview")}</span>
          </h3>
          {/* This preview was the one place in the app with a raised
              view and no flat one — the mirror image of the gap
              everywhere else. It opens raised because seeing the shape of
              a scenario is why somebody previews it, but the top-down
              view is now a click away, which is where its start and goal
              coordinates are legible. */}
          <MapView
            map={preview.map.map_data}
            width={720}
            height={460}
            startPose={preview.scenario.scenario.start_pose}
            goalPose={preview.scenario.scenario.goal_pose}
            robotPose={preview.scenario.scenario.start_pose}
            robotRadius={preview.scenario.scenario.robot.radius}
            goalTolerance={preview.scenario.scenario.goal_tolerance}
            initialMode="raised"
          />
          <p className="muted">
            {t("library.importedAs", { map: preview.map.id, scenario: preview.scenario.id })}{" "}
            <Link href="/decisions">{t("library.openDecisions")}</Link>
          </p>
        </div>
      ) : null}

      {imported.length > 0 ? (
        <div className="panel">
          <h3>{t("library.imported")}</h3>
          <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("library.entries")}</th>
                <th>{t("common.map")}</th>
                <th>{t("common.scenario")}</th>
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
        </div>
      ) : null}
    </>
  );
}
