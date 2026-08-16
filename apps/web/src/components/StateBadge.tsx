"use client";

/** Standardized state badge component for PlanBench.
 *
 * Each state is rendered with:
 *  1. Distinct color tone class (`ok`, `err`, `warn`, `info`, `muted-badge`).
 *  2. Secondary visual symbol / icon (so status is never conveyed by color alone).
 *  3. Localized label via `useTranslation()`.
 *  4. Technical domain tooltip (`title`).
 *  5. Accessibility `aria-label`.
 *
 * The raw protocol state value is preserved for API interactions.
 */

import { useTranslation } from "@/lib/i18n";

interface StateConfig {
  tone: "ok" | "err" | "warn" | "info" | "muted-badge";
  icon: string;
}

const CONFIG: Record<string, StateConfig> = {
  draft: { tone: "info", icon: "📝" },
  running: { tone: "info", icon: "⚡" },
  success: { tone: "ok", icon: "✓" },
  succeeded: { tone: "ok", icon: "✓" },
  collision: { tone: "err", icon: "💥" },
  stuck: { tone: "err", icon: "🛑" },
  timeout: { tone: "warn", icon: "⏱" },
  accepted: { tone: "ok", icon: "✓" },
  approved: { tone: "ok", icon: "✓" },
  rejected: { tone: "err", icon: "✖" },
  failed: { tone: "err", icon: "✖" },
  cancelled: { tone: "muted-badge", icon: "⏸" },
  pending_approval: { tone: "warn", icon: "⏳" },
  pending_review: { tone: "warn", icon: "⏳" },
  pending: { tone: "warn", icon: "⏳" },
  queued: { tone: "warn", icon: "⏳" },
  completed: { tone: "ok", icon: "✓" },
  paused: { tone: "warn", icon: "⏸" },
  idle: { tone: "muted-badge", icon: "ℹ" },
};

export function StateBadge({ state }: { state: string }) {
  const { t } = useTranslation();
  const normalizedState = state ? state.toLowerCase() : "idle";
  const config = CONFIG[normalizedState] ?? { tone: "warn", icon: "ℹ" };

  // Try status.label.state first, then benchmarks.state.state, job.state.state, or fallback to raw state
  let label = t(`status.label.${normalizedState}`);
  if (label === `status.label.${normalizedState}`) {
    const bLabel = t(`benchmarks.state.${normalizedState}`);
    if (bLabel !== `benchmarks.state.${normalizedState}`) {
      label = bLabel;
    } else {
      const jLabel = t(`job.state.${normalizedState}`);
      label = jLabel !== `job.state.${normalizedState}` ? jLabel : state;
    }
  }

  let tooltip = t(`status.tooltip.${normalizedState}`);
  if (tooltip === `status.tooltip.${normalizedState}`) {
    tooltip = state;
  }

  const ariaLabel = t("status.aria.label", { status: label });

  return (
    <span
      className={`badge ${config.tone}`}
      title={tooltip}
      aria-label={ariaLabel}
      data-testid={`state-badge-${normalizedState}`}
    >
      <span className="badge-icon" aria-hidden="true" style={{ marginRight: "4px" }}>
        {config.icon}
      </span>
      <span>{label}</span>
    </span>
  );
}
