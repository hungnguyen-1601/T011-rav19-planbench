"use client";

/** Planner latency over the episode, under that candidate's metrics.
 *
 * **A number cannot show a spike.** The tile reads the latency at one
 * instant and the result panel reads the p99; between them sits the
 * shape that explains both — whether the planner is steady, whether it
 * blew up once at a replan, whether it degraded as the map filled up.
 * Candidate B on a timeout episode read 7.63 ms at the scrubber against
 * a p99 of 2101 ms, and no arrangement of two numbers says why.
 *
 * Drawn as plain SVG. The decisions that could be wrong — where the
 * scale tops out, and what a tick with no planning means — are in
 * `lib/latencyChart.ts`, where they can be tested; this file is the
 * geometry.
 */

import { useTranslation } from "@/lib/i18n";
import {
  CHART,
  PLOT_HEIGHT,
  PLOT_WIDTH,
  latencyPlot,
  playheadFraction,
  timeAtFraction,
} from "@/lib/latencyChart";

const { width: WIDTH, height: HEIGHT, padLeft: PAD_LEFT, padRight: PAD_RIGHT } = CHART;
const PAD_TOP = CHART.padTop;

/** How far one arrow key moves the playhead, as a share of the episode.
 *  Coarse enough to cross a long run in a reasonable number of presses,
 *  fine enough to land on a spike. */
const KEY_STEP = 0.02;

export function LatencyChart({
  times,
  latencies,
  controlPeriodS,
  step,
  atTime,
  p99Ms,
  onSeek,
}: {
  times: readonly number[];
  latencies: readonly number[];
  controlPeriodS: number;
  /** The trace row the replay has reached. The chart draws up to here
   *  and no further, so it fills in as the episode plays instead of
   *  presenting a finished shape from the first frame. */
  step: number;
  /** Where the replay is, in seconds. Drawn as a playhead so the chart
   *  and the canvas above it are the same moment. */
  atTime: number;
  /** The p99 **so far**, not the episode's. Drawn because a single
   *  spike owns the vertical scale and the bulk of the run then has no
   *  readable summary left on the chart — and taken from the running
   *  series so it cannot disagree with the compute tile beside it. The
   *  episode's own p99 would be a number from the future. */
  p99Ms?: number | null;
  /** Seek the replay to a moment on this candidate's own clock.
   *
   * **The chart is the timeline.** It already draws where the run is
   * and what it was doing; making it clickable removes the trip back up
   * to the scrubber. The caller applies the seek to *both* panels —
   * converting units where the alignment needs it — so the pair stays
   * comparable rather than one canvas jumping alone. */
  onSeek?: (seconds: number) => void;
}) {
  const { t } = useTranslation();
  const plot = latencyPlot(times, latencies, controlPeriodS, step);
  if (!plot) {
    return (
      <p className="muted latency-chart-empty">{t("trace.latencyChart.noPlanning")}</p>
    );
  }

  const innerWidth = PLOT_WIDTH;
  const innerHeight = PLOT_HEIGHT;
  const toX = (seconds: number) => PAD_LEFT + (seconds / plot.tMax) * innerWidth;
  const toY = (ms: number) => PAD_TOP + innerHeight - (ms / plot.msMax) * innerHeight;

  const head = playheadFraction(plot, atTime);
  const budgetY = toY(plot.budgetMs);
  const p99Y = p99Ms && p99Ms > 0 && p99Ms <= plot.msMax ? toY(p99Ms) : null;

  return (
    <figure className="latency-chart">
      <figcaption>
        <span>{t("trace.latencyChart.title")}</span>
        {/* Live, like everything else here: a badge that lit up for a
            spike ten seconds ahead would be reporting the future. */}
        <span className={plot.breached ? "badge err" : "badge ok"}>
          {t(plot.breached ? "trace.latencyChart.over" : "trace.latencyChart.under")}
        </span>
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        // A slider rather than an image once it can be seeked: it holds
        // a value in a range and setting it is the point. Without the
        // role and the key handling this would be a control only a
        // mouse can reach.
        role={onSeek ? "slider" : "img"}
        className={onSeek ? "latency-seekable" : undefined}
        tabIndex={onSeek ? 0 : undefined}
        aria-label={t("trace.latencyChart.alt")}
        aria-valuemin={onSeek ? 0 : undefined}
        aria-valuemax={onSeek ? Number(plot.tMax.toFixed(2)) : undefined}
        aria-valuenow={onSeek ? Number(atTime.toFixed(2)) : undefined}
        aria-valuetext={onSeek ? `${atTime.toFixed(1)} / ${plot.tMax.toFixed(1)} s` : undefined}
        preserveAspectRatio="xMidYMid meet"
        onClick={
          onSeek
            ? (event) => {
                const box = event.currentTarget.getBoundingClientRect();
                if (box.width <= 0) return;
                onSeek(timeAtFraction(plot, (event.clientX - box.left) / box.width));
              }
            : undefined
        }
        onKeyDown={
          onSeek
            ? (event) => {
                const direction =
                  event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                if (direction === 0) {
                  if (event.key === "Home") onSeek(0);
                  else if (event.key === "End") onSeek(plot.tMax);
                  else return;
                } else {
                  onSeek(
                    Math.max(0, Math.min(plot.tMax, atTime + direction * KEY_STEP * plot.tMax)),
                  );
                }
                event.preventDefault();
              }
            : undefined
        }
      >
        <line
          x1={PAD_LEFT}
          y1={PAD_TOP + innerHeight}
          x2={WIDTH - PAD_RIGHT}
          y2={PAD_TOP + innerHeight}
          className="latency-axis"
        />
        {/* G4's threshold. Always on the chart — see `latencyPlot`. */}
        <line
          x1={PAD_LEFT}
          y1={budgetY}
          x2={WIDTH - PAD_RIGHT}
          y2={budgetY}
          className="latency-budget"
        />
        <text x={PAD_LEFT - 6} y={budgetY + 4} className="latency-tick" textAnchor="end">
          {plot.budgetMs.toFixed(0)}
        </text>
        {p99Y === null ? null : (
          <>
            <line
              x1={PAD_LEFT}
              y1={p99Y}
              x2={WIDTH - PAD_RIGHT}
              y2={p99Y}
              className="latency-p99"
            />
            <text x={PAD_LEFT - 6} y={p99Y + 4} className="latency-tick" textAnchor="end">
              p99
            </text>
          </>
        )}
        {/* One polyline per unbroken run: a tick where the planner did
            not run is a gap, not a zero. */}
        {plot.segments.map((segment, index) => (
          <polyline
            key={index}
            className="latency-line"
            points={segment.points.map((point) => `${toX(point.t)},${toY(point.ms)}`).join(" ")}
          />
        ))}
        {head === null ? null : (
          <line
            x1={PAD_LEFT + head * innerWidth}
            y1={PAD_TOP}
            x2={PAD_LEFT + head * innerWidth}
            y2={PAD_TOP + innerHeight}
            className="latency-playhead"
          />
        )}
        <text x={PAD_LEFT - 6} y={PAD_TOP + 4} className="latency-tick" textAnchor="end">
          {plot.msMax.toFixed(0)}
        </text>
        <text x={PAD_LEFT} y={HEIGHT - 4} className="latency-tick">
          0 s
        </text>
        <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 4} className="latency-tick" textAnchor="end">
          {plot.tMax.toFixed(1)} s
        </text>
      </svg>
    </figure>
  );
}
