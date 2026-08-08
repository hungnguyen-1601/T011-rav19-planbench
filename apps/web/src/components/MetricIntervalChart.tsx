"use client";

/** Median with IQR and CI95, one metric at a time (F09, biểu đồ 2).
 *
 * Two whiskers on purpose, and they are not the same thing. The wide one
 * is the interquartile range — how much the runs actually varied. The
 * narrow one is the bootstrap interval for the median itself — how well
 * this many seeds pin that median down. A chart showing only the second
 * invites the reader to mistake a tight estimate of a wildly varying
 * quantity for a consistent algorithm, which is the exact error P04
 * exists to prevent.
 *
 * A stack with no median gets no bar. It is named under the chart
 * instead: a zero-height bar reads as "it was fast", when what happened
 * is that it never arrived.
 */

import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { seriesColor, type IntervalRow, type IntervalSeries } from "@/lib/charts";
import { useTranslation } from "@/lib/i18n";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };

export function MetricIntervalChart({
  series,
  digits,
  unit,
}: {
  series: IntervalSeries;
  digits: number;
  unit: string;
}) {
  if (series.rows.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={64 + series.rows.length * 56}>
      <BarChart
        data={series.rows}
        layout="vertical"
        margin={{ top: 8, right: 32, bottom: 8, left: 8 }}
      >
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={AXIS} stroke="var(--border-strong)" />
        <YAxis
          type="category"
          dataKey="algorithm"
          width={150}
          tick={AXIS}
          stroke="var(--border-strong)"
        />
        <Tooltip
          cursor={{ fill: "var(--hover)" }}
          content={<IntervalTooltip digits={digits} unit={unit} />}
        />
        <Bar dataKey="median" fill={seriesColor(0)} barSize={18} isAnimationActive={false}>
          {/* Order matters visually: the IQR is drawn first and wider, so
              the narrower interval for the median sits on top of it
              rather than being hidden behind it. */}
          <ErrorBar dataKey="iqrError" width={6} strokeWidth={2} stroke="var(--border-strong)" direction="x" />
          <ErrorBar dataKey="ciError" width={10} strokeWidth={2} stroke="var(--text)" direction="x" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function IntervalTooltip({
  active,
  payload,
  digits,
  unit,
}: {
  active?: boolean;
  payload?: { payload: IntervalRow }[];
  digits: number;
  unit: string;
}) {
  const { t } = useTranslation();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const show = (value: number) => `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
  return (
    <div className="chart-tooltip">
      <strong>{row.algorithm}</strong>
      <div>
        {t("charts.median")}: {show(row.median)}
      </div>
      <div>
        IQR: {row.iqr ? `${show(row.iqr[0])} – ${show(row.iqr[1])}` : "—"}
      </div>
      <div>
        CI95: {row.ci ? `${show(row.ci[0])} – ${show(row.ci[1])}` : "—"}
      </div>
    </div>
  );
}
