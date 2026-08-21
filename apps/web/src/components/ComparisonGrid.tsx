"use client";

/** The end-of-run comparison, as a table.
 *
 * **A table, not a flat CSS grid, and that is a correctness choice.**
 * The grid this replaced laid every cell out in one stream, so it had no
 * notion of a row: a row that emitted one cell fewer than the others —
 * the flags row, which only appears when a candidate carries a finding —
 * pulled every cell after it one column left, and the page silently
 * mis-columned itself precisely when it had something to report. A
 * `<tr>` cannot do that. It also gives `<th scope="col">` to a screen
 * reader, which a stream of `<div>`s can only imitate with ARIA.
 *
 * Exported, and taking everything through props, so a test can render it
 * with `renderToStaticMarkup`. That is not architecture for its own
 * sake: this repo has no jsdom, so a component the tests cannot import
 * is a component nothing checks (`docs/KNOWN_LIMITATIONS.md`).
 */

import { Hint } from "@/components/Hint";
import { Icon } from "@/components/Icon";
import { type MetricRow, comparisonRows, leaders } from "@/lib/candidateMetrics";
import { candidateNames, headingField } from "@/lib/candidateHeading";
import { gateVerdictBadge } from "@/lib/gateSummary";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

const SIDES = ["a", "b"] as const;
const sideLabel = (index: number) => String.fromCharCode(65 + index);
const sideOf = (index: number) => SIDES[index] ?? "n";

export function ComparisonGrid({
  run,
  candidates,
  hostWarning,
}: {
  run: DecisionRun;
  candidates: RunCandidate[];
  /** Rendered inside the p99 row's label cell. G4 reads wall-clock
   *  latency, so an unpinned host qualifies that row and no other —
   *  above the table it would read as a caveat on every number. */
  hostWarning?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const rows = comparisonRows(candidates);
  const heading = headingField(candidates);

  // `Δ (B−A)` is a statement about two things. With one candidate there
  // is no difference; with three there is no "the" difference. The
  // column is not rendered at all rather than rendered and hidden.
  const hasDelta = candidates.length === 2;

  // A row of empty cells is not a finding. This one carries two — an
  // undeclared observation class, and a candidate retired early — and
  // appears only when a candidate has one.
  const hasFlags = candidates.some(
    (candidate) => !candidate.local_observation_class || candidate.stopped_early,
  );

  return (
    // The table keeps a minimum width and scrolls inside this wrapper.
    // Letting it shrink instead pushes the whole page into a horizontal
    // scroll, which moves the navigation as well as the numbers.
    <div className="comparison-scroll">
      <table className="comparison-table">
        <thead>
          <tr>
            <th scope="col" className="comparison-gutter comparison-grid-head" />
            {candidates.map((candidate, index) => {
              const names = candidateNames(candidate, heading);
              const verdict = gateVerdictBadge(candidate);
              return (
                <th
                  scope="col"
                  key={candidate.candidate_id}
                  className={`comparison-cell comparison-grid-head candidate-${sideOf(index)}`}
                >
                  <div>
                    <span className="candidate-letter">Candidate {sideLabel(index)}</span>
                    {/* Whichever of stack or config actually differs on
                        this run. Hard-coding either prints identical
                        words at the top of both columns on half the
                        runs — see `lib/candidateHeading`. */}
                    <h4>{names.heading}</h4>
                    <span className="candidate-secondary">{names.secondary}</span>
                  </div>
                  <span className="candidate-marks">
                    {run.recommended_candidate_id === candidate.candidate_id ? (
                      <span className="badge ok">
                        <Icon name="check" size={12} />
                        {t("decisions.card.recommended")}
                      </span>
                    ) : null}
                    {/* Six gates run *before* anything is scored (HĐ-7),
                        so a candidate that failed one was never ranked
                        at all. That belongs beside its name. */}
                    <span className={`badge ${verdict.tone}`}>
                      {t(verdict.key, { gates: verdict.gates })}
                    </span>
                  </span>
                </th>
              );
            })}
            {hasDelta ? (
              <th scope="col" className="comparison-cell comparison-delta">
                <span className="candidate-letter">Δ (B−A)</span>
              </th>
            ) : null}
          </tr>
        </thead>

        <tbody>
          {hasFlags ? (
            <tr>
              <th scope="row" className="comparison-gutter" />
              {candidates.map((candidate, index) => (
                <td
                  key={candidate.candidate_id}
                  className={`comparison-cell comparison-flags candidate-${sideOf(index)}`}
                >
                  {/* The class itself sits under the heading now. What
                      stays here is the *finding*: a stack whose inputs
                      nobody wrote down cannot be shown to have matched
                      the others, and an empty cell reads as "same as the
                      rest". */}
                  {candidate.local_observation_class ? null : (
                    <span className="badge warn" title={t("decisions.gates.observationUnknownNote")}>
                      {t("decisions.gates.observationUnknown")}
                    </span>
                  )}
                  {/* A retired candidate covered fewer episodes, so every
                      number in its column rests on a smaller sample. In
                      the column, because that is where it is read. */}
                  {candidate.stopped_early ? (
                    <span
                      className="badge warn"
                      title={`${candidate.stopped_early.gate}: ${candidate.stopped_early.rule}`}
                    >
                      {t("decisions.gates.stoppedEarly", {
                        run: String(candidate.stopped_early.episodes_run),
                        planned: String(candidate.stopped_early.episodes_planned),
                        gate: candidate.stopped_early.gate,
                      })}
                    </span>
                  ) : null}
                </td>
              ))}
              {/* No Δ cell, and nothing has to stand in for one. In the
                  grid this row used to shift every cell after it. */}
              {hasDelta ? <td className="comparison-delta" /> : null}
            </tr>
          ) : null}

          {rows.map((metric) => (
            <MetricLine
              key={metric.key}
              metric={metric}
              candidates={candidates}
              hasDelta={hasDelta}
              extra={metric.key === "p99" ? hostWarning : null}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricLine({
  metric,
  candidates,
  hasDelta,
  extra,
}: {
  metric: MetricRow;
  candidates: RunCandidate[];
  hasDelta: boolean;
  extra?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const best = leaders(metric);

  return (
    <tr>
      <th scope="row" className="comparison-gutter comparison-label">
        {t(`decisions.compare.${metric.key}`)}{" "}
        <Hint
          text={t(`decisions.compare.why.${metric.key}`)}
          label={t(`decisions.compare.${metric.key}`)}
        />
        {/* The deployment's own limit, under the metric it judges rather
            than beside a value — it belongs to the row, not to any one
            candidate. */}
        {metric.threshold ? (
          <span className="comparison-limit">
            {t("decisions.compare.limit", { limit: metric.threshold })}
          </span>
        ) : null}
        {extra}
      </th>

      {metric.numberText.map((digits, index) => (
        <td
          key={candidates[index].candidate_id}
          className={`comparison-cell comparison-value candidate-${sideOf(index)}${
            best.includes(index) ? " is-best" : ""
          }`}
        >
          {digits === null ? (
            // Not an em dash. "Zero" and "not recorded" are opposite
            // readings, and one glyph for both loses the difference.
            <span className="not-measured">{t("common.notMeasured")}</span>
          ) : (
            <>
              <span className="num">{digits}</span>
              {/* The slot renders even when the quantity has no unit:
                  dropping it lets a unitless row's number slide right
                  and breaks the decimal column the rest of the table
                  keeps. */}
              <span className="unit">{metric.unit ?? ""}</span>
            </>
          )}
          {best.includes(index) ? (
            <span className="sr-only"> ({t("running.leads")})</span>
          ) : null}
        </td>
      ))}

      {hasDelta ? <td className="comparison-delta">{metric.deltaText ?? ""}</td> : null}
    </tr>
  );
}
