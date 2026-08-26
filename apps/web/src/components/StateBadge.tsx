"use client";

/** A benchmark's state, in the reader's language.
 *
 * The state *value* stays English on the wire and in the API — it is a
 * protocol token, and translating it would break every comparison. Only
 * the label is localised, and the raw value is kept in `title` so anyone
 * debugging against the API can still see what the server actually said.
 *
 * The tone is never carried by colour alone: the word changes too.
 */

import { useTranslation } from "@/lib/i18n";

const TONE: Record<string, string> = {
  accepted: "ok",
  completed: "ok",
  approved: "ok",
  failed: "err",
  rejected: "err",
  cancelled: "err",
};

export function StateBadge({ state }: { state: string }) {
  const { t } = useTranslation();
  const tone = TONE[state] ?? "warn";
  return (
    <span className={`badge ${tone}`} title={state}>
      {t(`benchmarks.state.${state}`)}
    </span>
  );
}
