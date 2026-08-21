"use client";

/** Which stack to use — the last thing on the page, because it is the
 * thing the page is for.
 *
 * **Two groups, one line between them.** Above it, candidates that
 * cleared every gate: ranked, and eligible to be recommended. Below it,
 * candidates that did not: still marked out of 100, because in this
 * deployment nobody clears everything yet and a page with no numbers at
 * all leaves a reader with six pass/fail columns and no sense of how
 * close anything came.
 *
 * The line is not decoration. A gate failure may leave **no trace in the
 * mark**: collisions are excluded from `U_S` by contract (HĐ-6, so that
 * they cannot be traded against speed) and no objective reflects a
 * missing observation channel. So a stack that hit something can carry a
 * higher number than one that did not, and a single ranked list would
 * put it on top with a badge nobody reads. Inside a group the number
 * ranks; across the line it does not compare.
 *
 * **The headline comes from the card, never from the top of the list.**
 * `HĐ-10.1` refuses a Pareto-dominated candidate even when it leads on
 * utility.
 */

import {
  collisionGateReason,
  invisibleFailures,
  marginIsConclusive,
  outOf100,
  standings,
  verdictOf,
  type Standing,
} from "@/lib/conclusion";
import { Hint } from "@/components/Hint";
import { useTranslation } from "@/lib/i18n";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";

const OBJECTIVES = ["U_R", "U_S", "U_E", "U_C"] as const;

export function ConclusionPanel({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates: RunCandidate[] = run.report?.candidates ?? [];
  if (candidates.length === 0) return null;

  const { eligible, blocked } = standings(candidates);
  const verdict = verdictOf(run);
  const gatesById = new Map(candidates.map((entry) => [entry.candidate_id, entry.gates]));
  const best = eligible.find((entry) => entry.utility !== null);

  return (
    <section className="panel conclusion" aria-labelledby="conclusion-title">
      <div className="panel-head">
        <h3 id="conclusion-title">
          {t("conclusion.title")}{" "}
          <Hint text={t("conclusion.note")} label={t("conclusion.title")} />
        </h3>
      </div>

      <Headline verdict={verdict} best={best} candidates={candidates} />

      {eligible.length > 0 ? (
        <Group
          heading={t("conclusion.eligible")}
          hint={t("conclusion.eligible.hint")}
          rows={eligible}
          gatesById={gatesById}
        />
      ) : null}

      {blocked.length > 0 ? (
        <Group
          heading={t("conclusion.blocked")}
          hint={t("conclusion.blocked.hint")}
          rows={blocked}
          gatesById={gatesById}
          separated={eligible.length > 0}
        />
      ) : null}
    </section>
  );
}

function Headline({
  verdict,
  best,
  candidates,
}: {
  verdict: ReturnType<typeof verdictOf>;
  best: Standing | undefined;
  candidates: RunCandidate[];
}) {
  const { t } = useTranslation();

  if (verdict.kind === "no-card") {
    return (
      <p className="conclusion-headline conclusion-headline--muted">
        {/* Not a gap. Fewer than two candidates cleared the gates, so ΔU
            does not exist — and the marks below are what the run can
            still say. */}
        {t("conclusion.headline.noCard")}
        {best ? ` ${t("conclusion.headline.bestSoFar", { stack: best.label })}` : ""}
      </p>
    );
  }
  if (verdict.kind === "near-equivalent") {
    return (
      <p className="conclusion-headline conclusion-headline--muted">
        {t("conclusion.headline.nearEquivalent")}
      </p>
    );
  }

  const winner = candidates.find((entry) => entry.candidate_id === verdict.candidateId);
  const conclusive = marginIsConclusive(verdict.ci);
  /* The stack alone does not say which candidate won: both sides of a
     local-controller comparison run `astar+dwa`, and only the config
     tells them apart. Composed here rather than in `Standing.label`,
     which is rendered beside `<code>{standing.config}</code>` further
     down — folding it in there would print the config twice in one row
     and change the accessible name of the score bar with it. */
  const winnerLabel = winner
    ? `${winner.stack_label} · ${winner.local_controller_config}`
    : verdict.candidateId;
  return (
    <div className="conclusion-headline">
      <strong>{t("conclusion.headline.use", { stack: winnerLabel })}</strong>
      {verdict.deltaU !== null ? (
        <span className="muted">
          {" "}
          {t("conclusion.headline.margin", {
            delta: verdict.deltaU.toFixed(4),
            low: verdict.ci ? verdict.ci[0].toFixed(4) : "—",
            high: verdict.ci ? verdict.ci[1].toFixed(4) : "—",
          })}
        </span>
      ) : null}
      {/* An interval that straddles zero is consistent with the two
          being equal, and the mean alone would turn that into a
          result. */}
      {verdict.ci && !conclusive ? (
        <span className="badge warn">{t("conclusion.headline.inconclusive")}</span>
      ) : null}
    </div>
  );
}

function Group({
  heading,
  hint,
  rows,
  gatesById,
  separated = false,
}: {
  heading: string;
  hint: string;
  rows: Standing[];
  gatesById: Map<string, Record<string, unknown> | undefined>;
  separated?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className={`conclusion-group${separated ? " is-separated" : ""}`}>
      <h4>
        {heading} <Hint text={hint} label={heading} />
      </h4>
      {rows.map((standing) => {
        const mark = outOf100(standing.utility);
        const gates = gatesById.get(standing.candidateId);
        const hidden = invisibleFailures(standing, gates);
        const g2 = collisionGateReason(standing, gates);
        return (
          <article className="conclusion-row" key={standing.candidateId}>
            <div className="conclusion-row-head">
              <span className="conclusion-stack">
                {standing.label} <code>{standing.config}</code>
              </span>
              <span className="conclusion-mark">
                {/* No mark rather than 0/100: a candidate that could not
                    be scored has no result, and zero reads as the worst
                    possible one. */}
                {mark === null ? t("conclusion.unscored") : `${mark} / 100`}
              </span>
            </div>
            <div
              className="conclusion-bar"
              role="img"
              aria-label={
                mark === null
                  ? t("conclusion.unscored")
                  : t("conclusion.barLabel", { stack: standing.label, mark })
              }
            >
              <span style={{ width: `${(standing.utility ?? 0) * 100}%` }} />
            </div>
            {standing.objectives ? (
              <div className="conclusion-objectives">
                {OBJECTIVES.map((key) => (
                  <span key={key}>
                    <Hint
                      text={t(`conclusion.objective.${key}`)}
                      label={key}
                    />
                    <code>{key}</code> {standing.objectives![key].toFixed(2)}
                  </span>
                ))}
              </div>
            ) : null}
            {standing.blockingGates.length > 0 ? (
              <div className="conclusion-flags">
                <span className="badge err">
                  {t("conclusion.blockedAt", { gates: standing.blockingGates.join(", ") })}
                </span>
                {/* The two G2 failures read as opposite things — "it hit
                    something" versus "nobody looked long enough to know"
                    — and the label alone cannot tell them apart. */}
                {g2 === "sample-too-small" ? (
                  <span className="badge muted-badge">{t("conclusion.g2.sample")}</span>
                ) : null}
                {hidden.length > 0 ? (
                  <span className="badge warn">
                    {t("conclusion.markCannotSee", { gates: hidden.join(", ") })}{" "}
                    <Hint text={t("conclusion.markCannotSee.hint")} label={t("conclusion.title")} />
                  </span>
                ) : null}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
