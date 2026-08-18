"use client";

/* One rendering for every advisory surface — pre-flight, gate diagnosis,
 * reporting guardrails — because the shape is one shape. Each item shows
 * both halves: the legitimate next step, and the move that is barred.
 * The second one gets the visual weight; it is the half that stops a
 * reader from "fixing" a benchmark by editing its thresholds.
 */

import type { AdviceList } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

const BADGE: Record<string, string> = {
  blocking: "badge err",
  material: "badge warn",
  disclosure: "badge",
};

export function AdviceListView({ result }: { result: AdviceList }) {
  const { t } = useTranslation();

  return (
    <div>
      {/* "N rules ran, nothing to say" is a result; an unadorned empty
          list would be indistinguishable from a feature that never ran. */}
      <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        {t("advice.rulesRan", { count: String(result.rules_applied) })}
        {" · "}
        {t("advice.counts", {
          blocking: String(result.blocking),
          material: String(result.material),
          disclosure: String(result.disclosure),
        })}
      </p>

      {result.summary ? <p style={{ marginBottom: 8 }}>{result.summary}</p> : null}
      {result.fabricated > 0 ? (
        <div className="notice">{t("advice.fabricated", { count: String(result.fabricated) })}</div>
      ) : null}
      {result.refused ? (
        <p className="muted" style={{ fontSize: 12 }}>
          {t("advice.refused")}: {result.refused}
        </p>
      ) : null}

      {result.advice.length === 0 ? (
        <p className="muted">{t("advice.clean")}</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
          {result.advice.map((item, index) => (
            <li key={`${item.code}-${index}`} className="panel" style={{ padding: 12 }}>
              <p style={{ margin: 0 }}>
                <span className={BADGE[item.severity] ?? "badge"}>{t(`advice.${item.severity}`)}</span>{" "}
                {item.source === "model" ? (
                  <span className="badge">{t("advice.fromModel")}</span>
                ) : null}{" "}
                <strong>{item.claim}</strong>
                {item.subject ? (
                  <>
                    {" "}
                    <code style={{ fontSize: 11 }}>{item.subject}</code>
                  </>
                ) : null}
              </p>
              <p className="muted" style={{ margin: "6px 0", fontSize: 13 }}>
                {item.ground}
              </p>
              <p style={{ margin: "4px 0", fontSize: 13 }}>
                <strong>{t("advice.do")}:</strong> {item.do}
              </p>
              {item.do_not ? (
                <p style={{ margin: "4px 0", fontSize: 13 }}>
                  <strong>{t("advice.doNot")}:</strong> {item.do_not}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
