"use client";

/** Success rate against measured scenario difficulty (F09, biểu đồ 1).
 *
 * The chart a single averaged success rate cannot be. "A* + DWA succeeds
 * 78% of the time" hides whether it sailed through the easy scenarios and
 * collapsed at the hard ones or degraded gently across the range — and
 * those are different algorithms. The x axis is P03's measurement, so the
 * line is read against a scale somebody actually ran, not against the
 * order the scenarios happen to be listed in.
 *
 * What is deliberately not drawn: scenarios with no measured difficulty.
 * They have no x coordinate, and placing them at the end of the axis
 * would invent one. The panel names them instead.
 */

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { seriesColor, type DifficultyCurve, type DifficultyPoint } from "@/lib/charts";
import { useTranslation } from "@/lib/i18n";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };

export function DifficultyCurveChart({ curve }: { curve: DifficultyCurve }) {
  const { t } = useTranslation();
  if (curve.series.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart margin={{ top: 8, right: 16, bottom: 28, left: 8 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="difficulty"
          domain={[0, 1]}
          ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
          tick={AXIS}
          stroke="var(--border-strong)"
          label={{
            value: t("charts.difficultyAxis"),
            position: "insideBottom",
            offset: -16,
            fill: "var(--muted)",
            fontSize: 12,
          }}
        />
        <YAxis
          type="number"
          dataKey="successRate"
          domain={[0, 1]}
          tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
          tick={AXIS}
          stroke="var(--border-strong)"
          label={{
            value: t("charts.successAxis"),
            angle: -90,
            position: "insideLeft",
            fill: "var(--muted)",
            fontSize: 12,
          }}
        />
        <Tooltip content={<PointTooltip />} />
        <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
        {curve.series.map((series, index) => (
          <Line
            key={series.algorithm}
            type="monotone"
            name={series.algorithm}
            data={series.points}
            dataKey="successRate"
            stroke={seriesColor(index)}
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** The scenario behind the point, and how much run it stands on.
 *
 * The scenario name matters more than the coordinates: a reader looking
 * at a dip wants to know *which* scenario dipped. The report count is
 * there because a point averaged over three runs and a point from one run
 * look identical on the line. */
function PointTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: DifficultyPoint }[];
}) {
  const { t } = useTranslation();
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <strong>{point.scenario}</strong>
      <div>
        {t("charts.difficultyAxis")}: {point.difficulty.toFixed(3)} (CI95{" "}
        {point.ci95[0].toFixed(2)}–{point.ci95[1].toFixed(2)})
      </div>
      <div>
        {t("charts.successAxis")}: {(point.successRate * 100).toFixed(1)}%
      </div>
      <div className="muted">
        {t("charts.fromReports", { reports: point.reportCount, episodes: point.episodes })}
      </div>
      {point.stale ? <div className="muted">{t("charts.staleDifficulty")}</div> : null}
    </div>
  );
}
