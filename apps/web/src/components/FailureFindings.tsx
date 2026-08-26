"use client";

/** Evidence-backed failure analysis for one episode.
 *
 * Every finding is shown with the evidence that produced it. Confidence
 * is displayed prominently because it is load-bearing: a `low` finding
 * is a hypothesis consistent with the data, not a conclusion, and a
 * reader who cannot see that will over-trust it.
 */

import { useTranslation } from "@/lib/i18n";
import type { Confidence, FailureReport, Finding } from "@/lib/platformTypes";

const CONFIDENCE_CLASS: Record<Confidence, string> = {
  high: "ok",
  medium: "warn",
  low: "muted-badge",
};

export function FailureFindings({ report }: { report: FailureReport }) {
  const { t } = useTranslation();
  const clean = report.primary.category === "none";
  return (
    <div className="findings">
      <FindingCard finding={report.primary} primary />
      {report.contributing.length > 0 ? (
        <>
          <h4 className="muted">{t("findings.contributing")}</h4>
          {report.contributing.map((finding, index) => (
            <FindingCard key={`${finding.category}-${index}`} finding={finding} />
          ))}
        </>
      ) : null}
      {clean && report.contributing.length === 0 ? (
        <p className="muted">{t("findings.nothingWrong")}</p>
      ) : null}
    </div>
  );
}

function FindingCard({ finding, primary = false }: { finding: Finding; primary?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className={`finding${primary ? " finding-primary" : ""}`}>
      <div className="finding-head">
        <code>{finding.category}</code>
        <span
          className={`badge ${CONFIDENCE_CLASS[finding.confidence]}`}
          title={t(`findings.note.${finding.confidence}`)}
        >
          {t("findings.confidenceLabel", {
            level: t(`findings.confidence.${finding.confidence}`),
          })}
        </span>
      </div>
      <p>{finding.summary}</p>
      {finding.evidence.length > 0 ? (
        <div className="table-scroll">
        <table className="evidence-table">
          <thead>
            <tr>
              <th>{t("findings.evidence")}</th>
              <th>{t("findings.detail")}</th>
              <th>t (s)</th>
              <th>{t("findings.value")}</th>
            </tr>
          </thead>
          <tbody>
            {finding.evidence.map((evidence, index) => (
              <tr key={`${evidence.kind}-${index}`}>
                <td>
                  <code>{evidence.kind}</code>
                </td>
                <td>{evidence.detail}</td>
                <td className="muted">{evidence.time === null ? "—" : evidence.time.toFixed(2)}</td>
                <td className="muted">
                  {evidence.value === null ? "—" : evidence.value.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      ) : (
        <p className="muted">{t("findings.noEvidence")}</p>
      )}
    </div>
  );
}
