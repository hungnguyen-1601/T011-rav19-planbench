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
import { type MetricRow, comparisonRows, standings } from "@/lib/candidateMetrics";
import { type HeadingField, candidateNames, headingField } from "@/lib/candidateHeading";
import { collisionBoundCell } from "@/lib/collisionBound";
import { comparisonSummary } from "@/lib/comparisonSummary";
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

  // **The word, beside the colour that already said it.** Ahead was
  // green and behind was red, and for a sighted colourblind reader that
  // was the whole signal — the `sr-only` span beside each value reaches
  // a screen reader and nobody else. One comparison needs two
  // candidates; past two the cell names every leader it finds.
  const hasWinner = candidates.length >= 2;

  // A row of empty cells is not a finding. This one carries two — an
  // undeclared observation class, and a candidate retired early — and
  // appears only when a candidate has one.
  const hasFlags = candidates.some(
    (candidate) => !candidate.local_observation_class || candidate.stopped_early,
  );

  // A count of what the tinting already says. Ten rows carry a pattern
  // nobody reads off ten rows; every number comes from the same
  // `leaders()` the cells do, so the sentence cannot disagree with them.
  const summary = comparisonSummary(rows, candidates.length);

  return (
    <>
      {summary ? (
        <p className="comparison-summary">
          <Icon name="info" size={14} />
          <span>
            {t("decisions.compare.summary", {
              // Letters when the two name to the same thing. That
              // happens when neither the stack nor the config differs —
              // a run comparing a configuration against itself, which is
              // a real thing to measure (run-to-run variance) and would
              // otherwise produce "X leads on 2, X on 0".
              ...namesFor(candidates, heading),
              aWins: String(summary.wins[0]),
              bWins: String(summary.wins[1]),
              total: String(summary.total),
            })}
            {/* Dropped when nothing tied, so neither language has to
                make "0 are ties" read. */}
            {summary.ties > 0
              ? ` · ${t("decisions.compare.summaryTies", { ties: String(summary.ties) })}`
              : ""}
          </span>
        </p>
      ) : null}

    {/* The table keeps a minimum width and scrolls inside this wrapper.
        Letting it shrink instead pushes the whole page into a horizontal
        scroll, which moves the navigation as well as the numbers. */}
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
                  {/* The layout lives on this wrapper, not on the `<th>`.
                      A table cell given `display: grid` stops being a
                      table cell, and the browser then wraps every
                      consecutive non-cell child of the row into one
                      anonymous cell — which puts both candidates in a
                      single column, stacked. */}
                  <div className="head-inner">
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
                  </div>
                </th>
              );
            })}
            {hasDelta ? (
              <th scope="col" className="comparison-cell comparison-delta">
                <span className="candidate-letter">Δ (B−A)</span>
              </th>
            ) : null}
            {hasWinner ? (
              <th scope="col" className="comparison-cell comparison-winner">
                <span className="candidate-letter">{t("decisions.compare.winner")}</span>
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
                  className={`comparison-cell candidate-${sideOf(index)}`}
                >
                  <span className="comparison-flags">
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
                  </span>
                </td>
              ))}
              {/* No Δ cell, and nothing has to stand in for one. In the
                  grid this row used to shift every cell after it. */}
              {hasDelta ? <td className="comparison-delta" /> : null}
              {hasWinner ? <td className="comparison-winner" /> : null}
            </tr>
          ) : null}

          {rows.map((metric) => (
            <MetricLine
              key={metric.key}
              metric={metric}
              candidates={candidates}
              hasDelta={hasDelta}
              hasWinner={hasWinner}
              extra={metric.key === "p99" ? hostWarning : null}
              /* The bound is `3/N` under the simulated scenario
                 distribution, so the sample it rests on is not context —
                 it is what the number means. It was in a tooltip. */
              sub={metric.key === "collisionBound" ? t("decisions.compare.sub.collisionBound") : null}
            />
          ))}
        </tbody>
      </table>
    </div>
    {/* **Why there is no weight column, said out loud.** A reader
        arriving from a comparison template looks for one and finds
        nothing, and silence there reads as an omission rather than as
        the decision it is: weights attach to the four objectives, not to
        the metrics a reader compares on, so a weight beside `median
        episode duration` would be a number invented for the column. The
        real ones are under the scores, where they belong. */}
    <p className="comparison-footnote">{t("decisions.compare.weightNote")}</p>
    </>
  );
}

/** The two names the summary sentence uses.
 *
 * Normally the field that differs — the same words the column heads
 * carry, so the sentence and the table agree. When both candidates name
 * to the same string the sentence would read "X leads on 2, X on 0", so
 * it falls back to the letters, which are the only thing that still
 * tells them apart.
 */
function namesFor(candidates: RunCandidate[], heading: HeadingField): { a: string; b: string } {
  const a = candidateNames(candidates[0], heading).heading;
  const b = candidateNames(candidates[1], heading).heading;
  return a === b
    ? { a: `Candidate ${sideLabel(0)}`, b: `Candidate ${sideLabel(1)}` }
    : { a, b };
}

function MetricLine({
  metric,
  candidates,
  hasDelta,
  hasWinner,
  extra,
  sub,
}: {
  metric: MetricRow;
  candidates: RunCandidate[];
  hasDelta: boolean;
  hasWinner: boolean;
  extra?: React.ReactNode;
  /** A clause under the metric name that is true of every column. */
  sub?: React.ReactNode;
}) {
  const { t } = useTranslation();
  // Ahead, behind, or neither — from the same `leaders()` the summary
  // sentence counts, so a green cell and the sentence above it cannot
  // disagree. "Neither" is a real third answer: a tie, an unrecorded
  // value and a row with no direction all mark nobody.
  const mark = standings(metric);

  return (
    <tr>
      <th scope="row" className="comparison-gutter comparison-label">
        {t(`decisions.compare.${metric.key}`)}{" "}
        {/* **Which way is better, on the row itself.** Six of these ten
            rows are won by the smaller number, and `+9.35 ms` in the Δ
            column reads as an improvement to anyone who has not yet
            worked out that latency is one of them. The arrow is the
            cheapest place to say so: beside the name, where the reader
            already is when they meet the row. */}
        {metric.direction === "none" ? null : (
          <span
            className={`comparison-direction comparison-direction--${metric.direction}`}
            title={t(
              metric.direction === "lower"
                ? "decisions.compare.lowerIsBetter"
                : "decisions.compare.higherIsBetter",
            )}
          >
            <span aria-hidden="true">{metric.direction === "lower" ? "↓" : "↑"}</span>
            <span className="sr-only">
              {t(
                metric.direction === "lower"
                  ? "decisions.compare.lowerIsBetter"
                  : "decisions.compare.higherIsBetter",
              )}
            </span>
          </span>
        )}{" "}
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
        {sub ? <span className="comparison-sub">{sub}</span> : null}
        {extra}
      </th>

      {metric.key === "collisionBound"
        ? candidates.map((candidate, index) => (
            <CollisionBoundCell
              key={candidate.candidate_id}
              candidate={candidate}
              side={sideOf(index)}
            />
          ))
        : metric.numberText.map((digits, index) => (
        <td
          key={candidates[index].candidate_id}
          className={`comparison-cell comparison-value candidate-${sideOf(index)}${
            mark[index] === "lead" ? " is-best" : mark[index] === "trail" ? " is-worst" : ""
          }`}
        >
          {/* Two slots on an inner wrapper, never on the `<td>`: a table
              cell that is a grid is no longer a table cell. */}
          <span className="value-figure">
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
          </span>
          {/* In words as well as in colour. Red and green alone reach
              neither a colourblind reader nor a screen reader, and the
              losing side would then carry no signal at all. */}
          {mark[index] ? (
            <span className="sr-only">
              {" "}
              ({t(mark[index] === "lead" ? "running.leads" : "running.trails")})
            </span>
          ) : null}
        </td>
      ))}

      {hasDelta ? <td className="comparison-delta">{metric.deltaText ?? ""}</td> : null}
      {hasWinner ? <WinnerCell metric={metric} mark={mark} /> : null}
    </tr>
  );
}

/** Who led this row, in words.
 *
 * **Three answers, and the third is not a blank.** A row can be won, or
 * come out level, or never have been a comparison at all — a row with no
 * direction (`replans` is evidence, not a score) and a row where some
 * side recorded nothing are both the third. Printing an em dash for
 * "level" and an em dash for "never compared" would fold two different
 * facts into one glyph, which is the mistake the value cells already
 * refuse to make with `not measured` against `0`.
 *
 * The test of "was this a comparison" is deliberately the same pair of
 * conditions `comparisonSummary` uses to decide what to count. If they
 * drift, the sentence above the table says one candidate leads on five
 * rows while a different five rows carry its letter.
 */
function WinnerCell({ metric, mark }: { metric: MetricRow; mark: (string | null)[] }) {
  const { t } = useTranslation();
  const comparable =
    metric.direction !== "none" && metric.values.every((value) => value !== null);

  if (!comparable) {
    return (
      <td className="comparison-winner is-uncompared" title={t("decisions.compare.notCompared")}>
        <span aria-hidden="true">—</span>
        <span className="sr-only">{t("decisions.compare.notCompared")}</span>
      </td>
    );
  }

  const leaders = mark
    .map((entry, index) => (entry === "lead" ? sideLabel(index) : null))
    .filter((letter): letter is string => letter !== null);

  if (leaders.length === 0) {
    return <td className="comparison-winner is-tie">{t("decisions.compare.tie")}</td>;
  }
  return <td className="comparison-winner is-lead">{leaders.join(" · ")}</td>;
}

/** The collision-probability cell, with the sample it rests on.
 *
 * Two branches, and the second is the reason this cell is not an
 * ordinary value:
 *
 * - **A bound exists.** `≤ 10.0 %`, and under it the denominator. The
 *   number is `3/N`, so a lower one means a larger evidence base rather
 *   than a safer stack — without the sample beside it the cell says the
 *   opposite of what it means.
 * - **A collision was seen.** The platform publishes no bound at all
 *   (`gates.py:199`), so the cell prints neither `≤` — there is nothing
 *   to quote — nor "not measured", which would be false: the
 *   measurement exists and its result is unambiguous.
 */
function CollisionBoundCell({
  candidate,
  side,
}: {
  candidate: RunCandidate;
  side: string;
}) {
  const { t } = useTranslation();
  const cell = collisionBoundCell(candidate);

  if (cell.kind === "unknown") {
    return (
      <td className={`comparison-cell comparison-value candidate-${side}`}>
        <span className="value-figure">
          <span className="not-measured">{t("common.notMeasured")}</span>
        </span>
      </td>
    );
  }

  const sample =
    cell.kind === "bound"
      ? t("decisions.compare.cell.distinctEpisodes", {
          observed: String(cell.observed),
          distinct: String(cell.distinct),
        })
      : t("decisions.compare.cell.collisions", {
          observed: String(cell.observed),
          distinct: String(cell.distinct),
        });

  return (
    <td className={`comparison-cell comparison-value candidate-${side}`}>
      <span className="value-figure">
        {cell.kind === "bound" ? (
          <>
            <span className="num">≤ {(cell.bound * 100).toFixed(1)}</span>
            <span className="unit">%</span>
          </>
        ) : (
          <span className="not-applicable">{t("decisions.compare.cell.notApplicable")}</span>
        )}
        <span className="comparison-cell-sub">{sample}</span>
      </span>
    </td>
  );
}
