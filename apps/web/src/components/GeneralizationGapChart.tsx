"use client";

/** Dev against held-out, per metric (F09, biểu đồ 3).
 *
 * One chart per metric rather than one chart with everything: success
 * rate, travel time and path efficiency do not share a unit, and a single
 * axis carrying all three would put a number of seconds beside a fraction
 * and imply they can be compared by height.
 *
 * A stack missing one side is absent from the pair rather than drawn
 * against zero. "We never ran it on a held-out scenario" and "it scored
 * nothing there" are opposite statements, and a bar of height zero says
 * the second one.
 */

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { seriesColor, type GapRow, type GapSeries } from "@/lib/charts";
import { useTranslation } from "@/lib/i18n";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };

export function GeneralizationGapChart({ series }: { series: GapSeries }) {
  const { t } = useTranslation();
  if (series.rows.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={80 + series.rows.length * 52}>
      <BarChart data={series.rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="algorithm" tick={AXIS} stroke="var(--border-strong)" />
        <YAxis tick={AXIS} stroke="var(--border-strong)" />
        <Tooltip cursor={{ fill: "var(--hover)" }} content={<GapTooltip metric={series.metric} />} />
        <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
        <Bar
          dataKey="dev"
          name={t("generalization.dev")}
          fill={seriesColor(0)}
          isAnimationActive={false}
        />
        <Bar
          dataKey="holdout"
          name={t("generalization.holdout")}
          fill={seriesColor(1)}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

function GapTooltip({
  active,
  payload,
  metric,
}: {
  active?: boolean;
  payload?: { payload: GapRow }[];
  metric: string;
}) {
  const { t } = useTranslation();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const show = (value: number | null) => (value === null ? "—" : value.toFixed(3));
  return (
    <div className="chart-tooltip">
      <strong>{row.algorithm}</strong>
      <div className="muted">{metric}</div>
      <div>
        {t("generalization.dev")}: {show(row.dev)}
      </div>
      <div>
        {t("generalization.holdout")}: {show(row.holdout)}
      </div>
      <div>
        {t("generalization.gap")}:{" "}
        {row.gap === null ? t("generalization.noGap") : `${row.gap > 0 ? "+" : ""}${row.gap.toFixed(3)}`}
        {row.worse === null ? null : (
          <span className="muted">
            {" "}
            —{" "}
            {row.worse
              ? t("generalization.worseOnHoldout")
              : t("generalization.betterOnHoldout")}
          </span>
        )}
      </div>
    </div>
  );
}
