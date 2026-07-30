"use client";

/** Evidence-backed failure analysis for one episode.
 *
 * Every finding is shown with the evidence that produced it. Confidence
 * is displayed prominently because it is load-bearing: a `low` finding
 * is a hypothesis consistent with the data, not a conclusion, and a
 * reader who cannot see that will over-trust it.
 */

import type { Confidence, FailureReport, Finding } from "@/lib/platformTypes";

const CONFIDENCE_CLASS: Record<Confidence, string> = {
  high: "ok",
  medium: "warn",
  low: "muted-badge",
};

const CONFIDENCE_NOTE: Record<Confidence, string> = {
  high: "the engine recorded this cause directly",
  medium: "derived from trajectory statistics with one clear reading",
  low: "consistent with the data, but other readings exist",
};

export function FailureFindings({ report }: { report: FailureReport }) {
  const clean = report.primary.category === "none";
  return (
    <div className="findings">
      <FindingCard finding={report.primary} primary />
      {report.contributing.length > 0 ? (
        <>
          <h4 className="muted">Contributing factors</h4>
          {report.contributing.map((finding, index) => (
            <FindingCard key={`${finding.category}-${index}`} finding={finding} />
          ))}
        </>
      ) : null}
      {clean && report.contributing.length === 0 ? (
        <p className="muted">Nothing went wrong in this episode.</p>
      ) : null}
    </div>
  );
}

function FindingCard({ finding, primary = false }: { finding: Finding; primary?: boolean }) {
  return (
    <div className={`finding${primary ? " finding-primary" : ""}`}>
      <div className="finding-head">
        <code>{finding.category}</code>
        <span
          className={`badge ${CONFIDENCE_CLASS[finding.confidence]}`}
          title={CONFIDENCE_NOTE[finding.confidence]}
        >
          {finding.confidence} confidence
        </span>
      </div>
      <p>{finding.summary}</p>
      {finding.evidence.length > 0 ? (
        <table className="evidence-table">
          <thead>
            <tr>
              <th>Evidence</th>
              <th>Detail</th>
              <th>t (s)</th>
              <th>Value</th>
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
      ) : (
        <p className="muted">No evidence recorded for this finding.</p>
      )}
    </div>
  );
}
