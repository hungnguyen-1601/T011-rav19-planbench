"use client";

/** The replanning switch, shared by the simulate page and the benchmark form.
 *
 *  One component because the rule is one rule. The two pages set it for
 *  different things — a single run, or a whole sweep — but the semantics
 *  and the caveats are identical, and two copies would drift.
 *
 *  Two things it deliberately does:
 *
 *  - **Defaults to off.** Replanning changes what the global planner is
 *    allowed to see (P02), so nobody should end up with it on because a
 *    form remembered a checkbox.
 *  - **Warns while it is on, not after.** A blocked robot has to stand
 *    still for the whole stuck window before it is granted a new path.
 *    That wait is real simulated time and it lands in `travel_time`.
 *    Unexplained, it reads as the app having frozen.
 */

import { useTranslation } from "@/lib/i18n";
import type { ReplanningConfig } from "@/lib/benchmarkTypes";

export const NO_REPLANNING: ReplanningConfig = { enabled: false, max_replans: 0 };

export function ReplanningControls({
  value,
  onChange,
  scope,
}: {
  value: ReplanningConfig;
  onChange: (next: ReplanningConfig) => void;
  /** Which caveat to show. A benchmark also needs to be told the rule
   *  applies to every stack in the sweep, not to one algorithm. */
  scope: "simulation" | "benchmark";
}) {
  const { t } = useTranslation();
  return (
    <div style={{ marginTop: 12 }}>
      <label className="inline" title={t("replanning.hint")}>
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(event) =>
            onChange(
              event.target.checked
                ? // Turning it on with a budget of zero is rejected by the
                  // server, so the switch carries a usable budget with it.
                  { enabled: true, max_replans: Math.max(1, value.max_replans) }
                : NO_REPLANNING,
            )
          }
        />
        {t("replanning.enable")}
      </label>
      {value.enabled ? (
        <>
          <label className="inline" style={{ marginLeft: 16 }}>
            {t("replanning.maxReplans")}
            <input
              type="number"
              min={1}
              max={20}
              value={value.max_replans}
              style={{ width: 72, marginLeft: 6 }}
              onChange={(event) => {
                const parsed = Number(event.target.value);
                onChange({
                  enabled: true,
                  max_replans: Number.isFinite(parsed) ? Math.max(1, Math.trunc(parsed)) : 1,
                });
              }}
            />
          </label>
          <div className="notice" style={{ marginTop: 8 }}>
            {t("replanning.slowWarning")}
            {scope === "benchmark" ? ` ${t("replanning.benchmarkScope")}` : ""}
          </div>
        </>
      ) : null}
    </div>
  );
}
