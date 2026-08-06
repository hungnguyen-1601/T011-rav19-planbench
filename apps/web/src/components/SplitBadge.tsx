"use client";

/** Evaluation split of a scenario (P05): dev, held out, or unassigned.
 *
 * Held out is styled as a warning rather than a neutral label on
 * purpose. It is not a property of the scenario the reader can ignore —
 * it is a rule about what they are allowed to do with the number next to
 * it. Unassigned is muted and explicitly labelled, never rendered as an
 * empty cell, because "nobody classified this" and "this is dev" must
 * not look the same.
 */

import { useTranslation } from "@/lib/i18n";
import type { ScenarioSplit } from "@/lib/platformTypes";

const CLASS_BY_SPLIT: Record<ScenarioSplit, string> = {
  dev: "badge ok",
  holdout: "badge warn",
  unassigned: "badge muted-badge",
};

export function SplitBadge({
  split,
  notes,
}: {
  split: ScenarioSplit;
  notes?: string | null;
}) {
  const { t } = useTranslation();
  const label = t(`protocol.${split}`);
  const title = notes ?? (split === "unassigned" ? t("protocol.unassignedHint") : t("protocol.splitHint"));
  return (
    <span className={CLASS_BY_SPLIT[split]} title={title}>
      {label}
    </span>
  );
}
