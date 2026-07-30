"use client";

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
  if (!metrics) {
    return (
      <div className="panel">
        <h3>Metrics</h3>
        <p className="muted">Run a simulation to see metrics computed by the backend.</p>
      </div>
    );
  }
  const badge = metrics.success ? "ok" : metrics.collision ? "err" : "warn";
  return (
    <div className="panel">
      <h3>Metrics</h3>
      <div style={{ marginBottom: 12 }}>
        <span className={`badge ${badge}`}>{metrics.status}</span>
      </div>
      <div className="metrics">
        <Metric label="Travel time" value={format(metrics.travel_time, 2, " s")} />
        <Metric label="Trajectory length" value={format(metrics.trajectory_length, 2, " m")} />
        <Metric label="Path efficiency" value={format(metrics.path_efficiency, 3)} />
        <Metric label="Average speed" value={format(metrics.average_speed, 2, " m/s")} />
        <Metric label="Max speed" value={format(metrics.max_speed, 2, " m/s")} />
        <Metric label="Smoothness" value={format(metrics.smoothness, 3, " rad/m")} />
        <Metric label="Min clearance" value={format(metrics.min_clearance, 3, " m")} />
        <Metric label="Mean clearance" value={format(metrics.mean_clearance, 3, " m")} />
        <Metric label="Steps" value={String(metrics.steps)} />
        {plan ? (
          <>
            <Metric label="Planned length" value={format(plan.path_length, 2, " m")} />
            <Metric
              label="Global planning"
              value={format(plan.planning_time_seconds * 1000, 1, " ms")}
            />
            <Metric label="Expanded nodes" value={String(plan.expanded_nodes)} />
          </>
        ) : null}
      </div>
      <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        All values are computed by the backend from the recorded trajectory; the UI never
        derives metrics itself.
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
