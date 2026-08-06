"use client";

/** Measured scenario difficulty (P03): `1 - success_rate(baseline)`.
 *
 * Three things this component refuses to do, all for the same reason —
 * a difficulty is a measurement, and a measurement presented without its
 * conditions is an opinion with a decimal point:
 *
 * - It never renders a bare number. The interval is always beside it, so
 *   0.00 from 30 seeds does not read as "impossible to fail".
 * - It says which baseline and which calibration version produced the
 *   value, in the tooltip.
 * - When there is no calibration it prints "not measured", never a dash
 *   and never the curriculum position standing in for one.
 */

import { useTranslation } from "@/lib/i18n";
import type { DifficultyLabel } from "@/lib/platformTypes";

const CLASS_BY_BAND: Record<string, string> = {
  easy: "badge ok",
  moderate: "badge",
  hard: "badge warn",
  unsolved: "badge err",
};

export function DifficultyBadge({ difficulty }: { difficulty: DifficultyLabel | null }) {
  const { t } = useTranslation();
  if (!difficulty) {
    return (
      <span className="muted" title={t("difficulty.uncalibratedHint")}>
        {t("difficulty.uncalibrated")}
      </span>
    );
  }
  const [low, high] = difficulty.ci95;
  const title = [
    t("difficulty.baselineHint", {
      algorithm: difficulty.baseline_algorithm,
      seeds: String(difficulty.seed_count),
      version: difficulty.calibration_version,
    }),
    difficulty.adequate ? null : t("difficulty.provisional"),
    difficulty.stale ? t("difficulty.staleHint") : null,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className="difficulty-cell" title={title}>
      <span className={CLASS_BY_BAND[difficulty.band] ?? "badge"}>
        {t(`difficulty.band.${difficulty.band}`)}
      </span>{" "}
      <strong>{difficulty.value.toFixed(2)}</strong>{" "}
      <span className="muted">
        {t("difficulty.ci", { low: low.toFixed(2), high: high.toFixed(2) })}
      </span>
      {difficulty.stale ? <span className="badge warn">{t("difficulty.stale")}</span> : null}
      {difficulty.adequate ? null : (
        <span className="badge warn">{t("difficulty.provisionalBadge")}</span>
      )}
    </span>
  );
}
