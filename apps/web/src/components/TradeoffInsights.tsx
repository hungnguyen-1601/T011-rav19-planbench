"use client";

/** The reading of the table, and the picture of it.
 *
 * Two blocks under one panel because they answer the same question at
 * two speeds: the insights say what the ten rows amount to, the bars
 * show the shape a reader would have had to build in their head.
 *
 * **The bars are drawn only where a scale exists.** A normalised bar is
 * a claim that two numbers share a ruler, and for most of these metrics
 * that ruler is the deployment's own declared limit. Where no limit was
 * declared the pair's own larger value is the ruler, which compares the
 * two candidates honestly and says nothing about whether either is good
 * — so the caption says which ruler each group used. A row with no
 * direction is not drawn at all: there is no better end of the bar.
 */

import { type MetricRow, comparisonRows, leaders } from "@/lib/candidateMetrics";
import { candidateNames, headingField } from "@/lib/candidateHeading";
import { type Tradeoff, tradeoffs } from "@/lib/tradeoffs";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

const SIDES = ["a", "b"] as const;
const sideOf = (index: number) => SIDES[index] ?? "n";

export function TradeoffInsights({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates: RunCandidate[] = run.report?.candidates ?? [];
  const rows = comparisonRows(candidates);
  const found = tradeoffs(rows, candidates.length);
  /* **Two candidates or nothing drawn.** A normalised bar is a claim
     that two numbers share a ruler; with one candidate every bar is that
     candidate against itself, which fills each track to whatever the
     scale happens to be and compares nothing. A one-sided bar chart is a
     ruler with one mark on it, and it reads as a result. */
  const drawable =
    candidates.length < 2
      ? []
      : rows.filter(
          (row) => row.direction !== "none" && row.values.every((value) => value !== null),
        );
  if (found.length === 0 && drawable.length === 0) return null;

  const heading = headingField(candidates);
  const names = candidates.map((candidate) => candidateNames(candidate, heading).heading);

  return (
    <section className="panel tradeoff-panel" aria-labelledby="tradeoff-title">
      <div className="panel-head">
        <h3 id="tradeoff-title">{t("tradeoff.title")}</h3>
      </div>

      {found.length > 0 ? (
        <ul className="tradeoff-list">
          {found.map((insight) => (
            <li key={`${insight.kind}:${insight.side ?? "run"}`} className={`tradeoff-${insight.kind}`}>
              {sentence(insight, names, t)}{" "}
              <span className="tradeoff-metrics">
                {insight.metrics.map((key) => t(`decisions.compare.${key}`)).join(" · ")}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {drawable.length > 0 ? (
        <div className="tradeoff-bars">
          {drawable.map((row) => (
            <NormalisedRow key={row.key} row={row} names={names} />
          ))}
          {/* Which ruler each bar used, on the panel rather than in a
              tooltip: a normalised bar with no scale beside it is the
              chart equivalent of a percentage with no denominator. */}
          <p className="tradeoff-scale-note">{t("tradeoff.scaleNote")}</p>
        </div>
      ) : null}
    </section>
  );
}

function sentence(
  insight: Tradeoff,
  names: string[],
  t: (key: string, vars?: Record<string, string>) => string,
): string {
  const vars = { ...insight.vars };
  if (insight.side !== null) {
    vars.side = names[insight.side] ?? `Candidate ${String.fromCharCode(65 + insight.side)}`;
    vars.other = names[insight.side === 0 ? 1 : 0] ?? "";
  }
  return t(`tradeoff.insight.${insight.kind}`, vars);
}

/** One metric, both candidates, on a shared 0–1 scale.
 *
 * The fill is *goodness*, not magnitude: on a `lower` row the smaller
 * number draws the longer bar. Drawing raw magnitude would put the worst
 * latency at full width beside the best success rate at full width, and
 * a reader scanning down the column would take both for wins. */
function NormalisedRow({ row, names }: { row: MetricRow; names: string[] }) {
  const { t } = useTranslation();
  const ahead = leaders(row);
  const values = row.values as number[];
  const ceiling = scaleOf(row, values);

  return (
    <div className="tradeoff-bar-row">
      <span className="tradeoff-bar-label">{t(`decisions.compare.${row.key}`)}</span>
      <div className="tradeoff-bar-pair">
        {values.map((value, index) => {
          const share = ceiling === 0 ? 0 : Math.min(1, Math.abs(value) / ceiling);
          const good = row.direction === "lower" ? 1 - share : share;
          return (
            <div key={index} className="tradeoff-bar-line">
              <span className="tradeoff-bar-name">{names[index] ?? sideOf(index)}</span>
              <span className={`tradeoff-bar-track candidate-${sideOf(index)}`}>
                <span
                  className={`tradeoff-bar-fill${ahead.includes(index) ? " is-lead" : ""}`}
                  style={{ width: `${Math.max(0, Math.min(100, good * 100))}%` }}
                />
              </span>
              <span className="tradeoff-bar-value">
                {row.numberText[index]}
                {row.unit ? ` ${row.unit}` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** The ruler: the deployment's declared limit where it declared one, the
 *  pair's own larger value otherwise. Never zero — a zero ceiling would
 *  divide by nothing and paint every bar full. */
function scaleOf(row: MetricRow, values: number[]): number {
  const declared = row.threshold === undefined ? NaN : Number.parseFloat(row.threshold);
  const largest = Math.max(...values.map((value) => Math.abs(value)));
  if (Number.isFinite(declared) && declared > 0) return Math.max(declared, largest);
  return largest;
}
