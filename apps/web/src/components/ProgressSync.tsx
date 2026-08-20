"use client";

/** The arc-length alignment panel: slider, caveat, and where they parted.
 *
 * Its own file rather than a helper inside the page, for two reasons.
 * Next forbids a page module from exporting anything but the route's own
 * hooks, so a component defined there cannot be rendered by a test —
 * and this is precisely the component worth rendering in one, because
 * the thing it must never do is show arc-length-aligned panels without
 * the sentence explaining that the two runs were there at different
 * times.
 */

import { RunningComparison } from "@/components/RunningComparison";
import { useTranslation } from "@/lib/i18n";
import type { DivergencePoint, ReplaySyncView, RunCandidate } from "@/lib/decisions";
import type { PlaybackState } from "@/lib/playback";

export type SyncSlot =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ready"; view: ReplaySyncView }
  | { state: "error"; message: string };


export function ProgressSync({
  sync,
  scan,
  span,
  onScan,
  candidates,
}: {
  sync: SyncSlot;
  scan: PlaybackState;
  span: number;
  onScan: (next: PlaybackState) => void;
  candidates: RunCandidate[];
}) {
  const { t } = useTranslation();
  if (sync.state === "loading" || sync.state === "idle") {
    return <div className="episode-skeleton" role="status">{t("trace.sync.loading")}</div>;
  }
  if (sync.state === "error") {
    return <div className="episode-error" role="alert"><p>{t("trace.sync.error")}</p><p className="muted">{sync.message}</p></div>;
  }

  const view: ReplaySyncView = sync.view;
  const ruler = candidates.find((c) => c.candidate_id === view.reference_source_candidate_id);
  const jumps = [
    ...(view.divergence.sustained ? [view.divergence.sustained] : []),
    ...view.divergence.anchors,
  ];

  return (
    <div className="episode-progress-sync">
      {/* Served by the platform, rendered verbatim. A caveat the client
          can reword is a caveat the client can water down. */}
      <p className="episode-sync-warning" role="note">{view.plan.warning}</p>
      <p className="muted">
        <span className={`badge ${view.plan.reference.quality === "reference_plan" ? "ok" : "warn"}`}>
          {t(`trace.sync.quality.${view.plan.reference.quality}`)}
        </span>
        {ruler ? ` ${t("trace.sync.ruler")}: ${ruler.stack_label}` : ""}
      </p>
      <div className="episode-playback">
        <button type="button" onClick={() => onScan({ ...scan, playing: !scan.playing && span > 0 })}>
          {scan.playing ? t("trace.pause") : t("trace.play")}
        </button>
        <input
          type="range"
          min={0}
          max={span || 0}
          step="0.01"
          value={Math.min(scan.time, span)}
          aria-label={t("trace.sync.progressLabel")}
          aria-valuetext={`${scan.time.toFixed(1)} / ${span.toFixed(1)} m`}
          onChange={(event) => onScan({ ...scan, playing: false, time: Number(event.target.value) })}
        />
        <output>{scan.time.toFixed(1)} / {span.toFixed(1)} m</output>
      </div>
      {jumps.length > 0 ? (
        <div className="episode-divergence" aria-label={t("trace.sync.divergence")}>
          <span className="muted">{t("trace.sync.divergence")}:</span>
          {jumps.map((point, index) => (
            <button
              key={`${point.kind}-${point.event ?? index}-${point.progress_m}`}
              type="button"
              className="chip"
              onClick={() => onScan({ ...scan, playing: false, time: point.progress_m })}
            >
              {chipLabel(point, t)}
            </button>
          ))}
        </div>
      ) : null}
      {/* Under the slider, because it reads the slider. The scrub
          position on this panel is metres of progress, which is exactly
          the ladder's own axis — so the rung on screen is the rung the
          reader is standing on, with no second position to keep in
          sync. */}
      <RunningComparison
        running={view.running?.ladder ?? null}
        progress={scan.time}
        candidateA={view.candidate_a}
        candidateB={view.candidate_b}
        candidates={candidates}
        referenceSource={view.reference_source_candidate_id}
      />
    </div>
  );
}

function chipLabel(point: DivergencePoint, t: (key: string) => string): string {
  const where = `${point.progress_m.toFixed(1)} m`;
  if (point.kind === "event") return `${point.event} (${point.side?.toUpperCase()}) · ${where}`;
  return `${t("trace.sync.sustained")} · ${where}`;
}

