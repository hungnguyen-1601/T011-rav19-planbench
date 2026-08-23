"use client";

/** Built-in scenario library (M5), in curriculum order.
 *
 * **Two columns went, and a button arrived.** Measured difficulty and
 * the evaluation split were the widest things on this table and neither
 * answered the question a reader opens it with, which is what a scenario
 * *does*. The difficulty number is a property of one baseline stack on
 * one calibration run, and the split governs which scenarios a
 * generalization report may quote — real facts, and both about the
 * benchmark protocol rather than about the world being described.
 *
 * What replaced them is the answer: a preview, per row. Until now the
 * only way to see a scenario move was to import it, build a deployment
 * on it and open the test bench — three steps and two stored rows to
 * look at a picture.
 *
 * **Preview stores nothing, and that is load-bearing.** The obvious
 * implementation is to import and draw what comes back, which is exactly
 * how one database reached 198 maps carrying 41 distinct checksums. The
 * endpoint behind this builds the scenario and throws it away.
 *
 * Importing still materialises the map and scenario server-side from
 * `build_scenario()`. The browser never authors geometry: two clients
 * importing the same entry must get byte-identical maps, or benchmarks
 * built from them would not be comparable.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { MapView } from "@/components/MapView";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { advance, playableSeconds, trafficAt } from "@/lib/previewPlayback";
import { snapshotsOf } from "@/lib/traffic";
import type { ImportedScenario, LibraryEntry } from "@/lib/platformTypes";
import type { LibraryPreview } from "@/lib/types";

export default function LibraryPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [preview, setPreview] = useState<LibraryPreview | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<ImportedScenario[]>([]);
  /** Where the preview's playhead is, and whether it is running. Reset
   *  by every new preview: leaving it at 30 s would open a scenario in
   *  the middle of a route nobody has watched the start of. */
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setEntries(await authFetch<LibraryEntry[]>("/scenario-library"));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  /* Real elapsed seconds rather than a fixed step per frame: a
     backgrounded tab is throttled to one frame a second, and a constant
     increment would crawl there and race on a 144 Hz screen. What is
     being played back is seconds of a simulated episode. */
  useEffect(() => {
    if (!playing) return;
    const span = playableSeconds(preview);
    if (span <= 0) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const elapsed = (now - last) / 1000;
      last = now;
      setPlayhead((current) => {
        const next = advance(current, elapsed, span);
        if (!next.running) setPlaying(false);
        return next.seconds;
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, preview]);

  const previewEntry = useCallback(async (name: string) => {
    setPreviewing(name);
    setError(null);
    try {
      const answer = await authFetch<LibraryPreview>(`/scenario-library/${name}/preview`);
      setPreview(answer);
      setPlayhead(0);
      setPlaying(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPreview(null);
    } finally {
      setPreviewing(null);
    }
  }, []);

  const importEntry = useCallback(async (name: string) => {
    setBusy(name);
    setError(null);
    try {
      const result = await authFetch<ImportedScenario>(`/scenario-library/${name}/import`, {
        method: "POST",
      });
      setImported((current) => [...current, result]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }, []);

  // Browsing is public; importing writes to the shared library and so
  // needs an account. Previewing writes nothing, so it needs neither.
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
              <th>{t("algorithms.description")}</th>
              <th>{t("maps.size")}</th>
              <th>{t("library.obstacles")}</th>
              <th>{t("library.timeout")}</th>
              <th>{t("common.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.name} className={preview?.library_name === entry.name ? "is-previewing" : undefined}>
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
                    <span className="badge warn">{entry.dynamic_obstacles}</span>
                  ) : (
                    <span className="muted">{t("common.none")}</span>
                  )}
                </td>
                <td className="muted">{entry.timeout_seconds}s</td>
                <td className="library-actions">
                  {/* Preview first, and available signed out: looking at
                      a scenario writes nothing, and making somebody sign
                      in to look at a picture is a gate on the wrong
                      side of the decision. */}
                  <button
                    type="button"
                    disabled={previewing !== null}
                    onClick={() => void previewEntry(entry.name)}
                  >
                    {previewing === entry.name ? t("common.loading") : t("library.preview")}
                  </button>
                  <button
                    type="button"
                    disabled={!canImport || busy !== null}
                    onClick={() => void importEntry(entry.name)}
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

      {preview ? (
        <div className="panel library-preview">
          <div className="panel-head">
            <h3>
              <code>{preview.library_name}</code>{" "}
              <span className="muted">{t("library.preview")}</span>
            </h3>
            <span className="badge muted-badge">{t("library.previewStoresNothing")}</span>
          </div>

          {/* Opens raised because the shape of the space is why somebody
              previews a scenario, and the top-down view — where start and
              goal coordinates are legible — is one click away. */}
          <MapView
            map={preview.map}
            width={720}
            height={460}
            startPose={preview.scenario.start_pose}
            goalPose={preview.scenario.goal_pose}
            robotPose={preview.scenario.start_pose}
            robotRadius={preview.scenario.robot.radius}
            goalTolerance={preview.scenario.goal_tolerance}
            /* Both views read one playhead. Two canvases showing one
               scenario at two instants would be two scenarios. */
            dynamicObstacles={trafficAt(preview, playhead)}
            obstacleSnapshots={snapshotsOf(preview, playhead)}
            initialMode="raised"
          />

          {playableSeconds(preview) > 0 ? (
            <div className="deployment-preview-transport">
              <button
                type="button"
                onClick={() => {
                  // Pressing play at the end replays rather than doing
                  // nothing, which is what a live-looking button has to do.
                  if (!playing && playhead >= playableSeconds(preview)) setPlayhead(0);
                  setPlaying((current) => !current);
                }}
              >
                {t(playing ? "deployments.form.previewPause" : "deployments.form.previewPlay")}
              </button>
              <input
                type="range"
                className="deployment-preview-scrub"
                min={0}
                max={playableSeconds(preview)}
                step={preview.step || 0.2}
                value={playhead}
                aria-label={t("deployments.form.previewScrub")}
                onChange={(event) => {
                  // Dragging takes over from the timer, which would
                  // otherwise spring the handle out from under the
                  // pointer.
                  setPlaying(false);
                  setPlayhead(Number(event.target.value));
                }}
              />
              <span className="deployment-preview-clock">
                {playhead.toFixed(1)} / {playableSeconds(preview).toFixed(1)} s
              </span>
            </div>
          ) : (
            /* A scenario with no traffic is a thing to look at, not a
               reason to show a scrubber that cannot move. */
            <p className="muted library-preview-static">{t("library.previewNoTraffic")}</p>
          )}
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
