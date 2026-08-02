"use client";

import { useTranslation } from "@/lib/i18n";
import type { EpisodeMetrics, PlanResult } from "@/lib/types";

function format(value: number | null | undefined, digits = 2, suffix = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

export function MetricsPanel({
  metrics,
  plan,
}: {
  metrics: EpisodeMetrics | null;
  plan?: PlanResult | null;
}) {
  const { t } = useTranslation();
  if (!metrics) {
    return (
      <div className="panel">
        <h3>{t("metrics.title")}</h3>
        <p className="muted">{t("metrics.runFirst")}</p>
      </div>
    );
  }
  const badge = metrics.success ? "ok" : metrics.collision ? "err" : "warn";
  return (
    <div className="panel">
      <h3>{t("metrics.title")}</h3>
      <div style={{ marginBottom: 12 }}>
        <span className={`badge ${badge}`}>{metrics.status}</span>
      </div>
      <div className="metrics">
        <Metric label={t("metrics.travelTime")} value={format(metrics.travel_time, 2, " s")} />
        <Metric label={t("metrics.trajectoryLength")} value={format(metrics.trajectory_length, 2, " m")} />
        <Metric label={t("metrics.pathEfficiency")} value={format(metrics.path_efficiency, 3)} />
        <Metric label={t("metrics.averageSpeed")} value={format(metrics.average_speed, 2, " m/s")} />
        <Metric label={t("metrics.maxSpeed")} value={format(metrics.max_speed, 2, " m/s")} />
        <Metric
          label={t("metrics.smoothness")}
          value={format(metrics.smoothness_per_metre, 3, " rad/m")}
        />
        <Metric label={t("metrics.minClearance")} value={format(metrics.min_clearance, 3, " m")} />
        <Metric label={t("metrics.meanClearance")} value={format(metrics.mean_clearance, 3, " m")} />
        <Metric label={t("metrics.steps")} value={String(metrics.steps)} />
        {plan ? (
          <>
            <Metric label={t("metrics.plannedLength")} value={format(plan.path_length, 2, " m")} />
            <Metric
              label={t("metrics.globalPlanning")}
              value={format(plan.planning_time_seconds * 1000, 1, " ms")}
            />
            <Metric label={t("metrics.expandedNodes")} value={String(plan.expanded_nodes)} />
          </>
        ) : null}
      </div>
      <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        {t("metrics.computedByBackend")}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}
