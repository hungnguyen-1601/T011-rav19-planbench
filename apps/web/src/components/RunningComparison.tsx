"use client";

/** Two candidates at one rung of the progress ladder — E4.3.
 *
 * The panel above this one aligns the two replays and shows *where* they
 * parted. This one answers the question a reader has while scrubbing:
 * right now, who is doing better, and at what?
 *
 * **The two clocks are drawn as two tables, never one.** At a single
 * instant the robots are in different parts of the map, so "worst
 * clearance" read at equal time compares two different stretches of it.
 * The server declares which metric belongs to which clock and
 * `lib/running.ts` carries that split here; a single eight-row table
 * would be a smaller component and a wrong one.
 */

import { useTranslation } from "@/lib/i18n";
import type { RunCandidate, RunningPoint, RunningSample } from "@/lib/decisions";
import type { MetricRow } from "@/lib/running";
import {
  PROGRESS_CLOCK,
  TIME_CLOCK,
  compositeCaveat,
  leader,
  rowAt,
} from "@/lib/running";

export function RunningComparison({
  running,
  progress,
  candidateA,
  candidateB,
  candidates,
}: {
  running: RunningPoint[] | null;
  progress: number;
  candidateA: string;
  candidateB: string;
  candidates: RunCandidate[];
}) {
  const { t } = useTranslation();
  const label = (id: string) =>
    candidates.find((entry) => entry.candidate_id === id)?.stack_label ?? id;

  // `null` and `[]` mean different things and the server sends only the
  // former. Distinguished anyway: an empty table reads as "no
  // difference between them", which is not what "could not be computed"
  // says.
  if (running === null) {
    return (
      <section className="episode-running" aria-label={t("running.title")}>
        <h4>{t("running.title")}</h4>
        <p className="muted">{t("running.none")}</p>
      </section>
    );
  }

  const point = rowAt(running, progress);
  if (!point) {
    return (
      <section className="episode-running" aria-label={t("running.title")}>
        <h4>{t("running.title")}</h4>
        <p className="muted">{t("running.before")}</p>
      </section>
    );
  }

  return (
    <section className="episode-running" aria-label={t("running.title")}>
      <h4>
        {t("running.title")}{" "}
        <span className="muted">
          — {t("running.rung")} {point.progress_m.toFixed(1)} m
        </span>
      </h4>

      <ClockTable
        heading={t("running.clock.progress")}
        hint={t("running.clock.progress.hint")}
        rows={PROGRESS_CLOCK}
        point={point}
        labelA={label(candidateA)}
        labelB={label(candidateB)}
      />
      <ClockTable
        heading={t("running.clock.time")}
        hint={t("running.clock.time.hint")}
        rows={TIME_CLOCK}
        point={point}
        labelA={label(candidateA)}
        labelB={label(candidateB)}
      />

      <div className="episode-running-composite">
        <span>{t("running.composite.title")}</span>
        <strong className={point.partial_advantage >= 0 ? "ok" : "warn"}>
          {point.partial_advantage >= 0 ? "+" : ""}
          {point.partial_advantage.toFixed(3)}
        </strong>
        <span className="muted">
          {point.partial_objectives.join(" · ")}
        </span>
        {/* Rendered beside the number, not behind a tooltip: a composite
            whose caveat can be missed is a composite that will be read
            as ΔU. */}
        <p className="muted">{t(compositeCaveat(point))}</p>
      </div>
    </section>
  );
}

function ClockTable({
  heading,
  hint,
  rows,
  point,
  labelA,
  labelB,
}: {
  heading: string;
  hint: string;
  rows: MetricRow[];
  point: RunningPoint;
  labelA: string;
  labelB: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="episode-running-clock">
      <h5>{heading}</h5>
      <p className="muted">{hint}</p>
      <table>
        <thead>
          <tr>
            <th scope="col">{heading}</th>
            <th scope="col">{labelA}</th>
            <th scope="col">{labelB}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const winner = leader(row, point.a, point.b);
            return (
              <tr key={String(row.key)}>
                <th scope="row">{t(`running.metric.${String(row.key)}`)}</th>
                <Cell row={row} sample={point.a} lead={winner === "a"} lead_label={t("running.leads")} />
                <Cell row={row} sample={point.b} lead={winner === "b"} lead_label={t("running.leads")} />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Cell({
  row,
  sample,
  lead,
  lead_label,
}: {
  row: MetricRow;
  sample: RunningSample;
  lead: boolean;
  lead_label: string;
}) {
  const value = Number(sample[row.key]);
  return (
    <td className={lead ? "ok" : undefined}>
      {value.toFixed(row.digits)}
      {row.unit ? ` ${row.unit}` : ""}
      {/* The colour carries the claim for a sighted reader; this carries
          it for everyone else. */}
      {lead ? <span className="sr-only"> ({lead_label})</span> : null}
    </td>
  );
}
