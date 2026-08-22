"use client";

/** What this run concluded, at the top of the page that concluded it.
 *
 * **The answer used to be on the sixth screen.** The scores, the margin
 * and the card were all below the episode replay — which is a
 * drill-down, opened by a reader who already doubts something — so a
 * reader arriving for the result met an evidence table, a thirty-episode
 * pager and two trajectory canvases before anything told them what the
 * run decided. The comment above the render order in the page has said
 * "the answer, then how it was reached" for a while; this is the first
 * arrangement where that is true of the screen as well as of the source.
 *
 * **And it says the missing recommendation once.** Four panels each
 * stated it in different words, and one of them stated it wrongly — the
 * copy for "nobody cleared" printed under a table showing a candidate
 * that had. Fixing that sentence was necessary and not sufficient: four
 * copies of one fact force a reader to check them against each other.
 * The reason lives here now, and the explanation of it lives once more
 * further down, beside the evidence it draws on.
 */

import { Icon } from "@/components/Icon";
import { Hint } from "@/components/Hint";
import { marginIsConclusive, outOf100, standings, verdictOf } from "@/lib/conclusion";
import { type NoCardReason, noCardReason } from "@/lib/decisions";
import type { DecisionRun } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

export function DecisionSummary({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates = run.report?.candidates ?? [];
  if (candidates.length === 0) return null;

  const { eligible, blocked } = standings(candidates);
  // Highest first among those that cleared, then those that did not.
  // Both are shown: a blocked candidate's mark is why a reader can see
  // that the gates, not the score, are what removed it.
  const rows = [...eligible, ...blocked];
  const verdict = verdictOf(run);

  return (
    <section className="panel decision-summary-panel" aria-labelledby="decision-summary-title">
      <div className="panel-head">
        <h3 id="decision-summary-title">
          {t("summary.title")} <Hint text={t("summary.note")} label={t("summary.title")} />
        </h3>
      </div>

      <div className="decision-summary-body">
        <div className="decision-summary-scores">
          {rows.map((standing) => {
            const mark = outOf100(standing.utility);
            return (
              <div
                key={standing.candidateId}
                className={`decision-summary-row${standing.eligible ? "" : " is-blocked"}`}
              >
                <div className="decision-summary-row-head">
                  <span className="decision-summary-stack">
                    {standing.label} <code>{standing.config}</code>
                  </span>
                  <span className="decision-summary-mark">
                    {/* Never `0 / 100` for an unscored candidate: that
                        reads as the worst possible result rather than as
                        an absent one. */}
                    {mark === null ? t("summary.unscored") : `${mark} / 100`}
                  </span>
                </div>
                <div
                  className="decision-summary-bar"
                  role="img"
                  aria-label={`${standing.label}: ${mark === null ? t("summary.unscored") : `${mark} / 100`}`}
                >
                  <span style={{ width: `${mark === null ? 0 : Number(mark)}%` }} />
                </div>
                {standing.eligible ? null : (
                  <span className="badge err decision-summary-blocked">
                    {standing.blockingGates.length > 0
                      ? t("summary.blockedAt", { gates: standing.blockingGates.join(", ") })
                      : t("summary.blocked")}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <Recommendation run={run} verdict={verdict} />
      </div>
    </section>
  );
}

/** The card on the right: what to do, and how sure the run is of it. */
function Recommendation({
  run,
  verdict,
}: {
  run: DecisionRun;
  verdict: ReturnType<typeof verdictOf>;
}) {
  const { t } = useTranslation();

  if (verdict.kind === "no-card") {
    // The single place the page states why no recommendation came back.
    // `noCardReason` tells one survivor from none, which is the
    // difference between "register a second candidate" and "register a
    // better one" — opposite next actions from the same empty card.
    const reason: NoCardReason = noCardReason(run);
    return (
      <aside className="decision-recommendation is-none">
        <span className="decision-recommendation-label">{t("summary.recommendation")}</span>
        <strong>{reason ? t(`decisions.reason.${reason}`) : t("decisions.noCard.title")}</strong>
        <p className="muted">{reason ? t(`decisions.noCard.whatNext.${reason}`) : ""}</p>
        {run.report?.gate_only_deployment ? (
          <div className="notice">{run.report.gate_only_deployment}</div>
        ) : null}
        {/* **The report's own words, kept.** The summary above is this
            client's reading of a reason code; a reader who disagrees
            with the reading needs the platform's sentence, not a
            paraphrase of it. It travelled here with the message rather
            than being dropped when the panel that held it went. */}
        {run.report?.why_no_card ? (
          <details className="decision-recommendation-verbatim">
            <summary className="muted">{t("decisions.noCard.verbatim")}</summary>
            <p>{run.report.why_no_card}</p>
          </details>
        ) : null}
      </aside>
    );
  }

  if (verdict.kind === "near-equivalent") {
    return (
      <aside className="decision-recommendation is-tie">
        <span className="decision-recommendation-label">{t("summary.recommendation")}</span>
        <strong>{t("conclusion.headline.nearEquivalent")}</strong>
        <p className="muted">{t("summary.tieNext")}</p>
      </aside>
    );
  }

  const card = run.card;
  const winner = (run.report?.candidates ?? []).find(
    (entry) => entry.candidate_id === verdict.candidateId,
  );
  const label = winner
    ? `${winner.stack_label} · ${winner.local_controller_config}`
    : verdict.candidateId;
  const conclusive = marginIsConclusive(verdict.ci);

  return (
    <aside className="decision-recommendation is-card">
      <span className="decision-recommendation-label">
        <Icon name="trophy" size={13} />
        {t("summary.recommendation")}
      </span>
      <strong>{label}</strong>
      {/* Margin and interval together, never the margin alone. A ΔU
          whose interval straddles zero is a difference the run cannot
          demonstrate, and printing it unqualified is how a coin toss
          reads as a finding. */}
      <dl className="decision-recommendation-evidence">
        {verdict.deltaU !== null ? (
          <div>
            <dt>{t("decisions.card.deltaU")}</dt>
            <dd>{`${verdict.deltaU >= 0 ? "+" : ""}${verdict.deltaU.toFixed(4)}`}</dd>
          </div>
        ) : null}
        {verdict.ci ? (
          <div>
            <dt>{t("decisions.card.ci95")}</dt>
            <dd>{`[${verdict.ci[0].toFixed(4)}, ${verdict.ci[1].toFixed(4)}]`}</dd>
          </div>
        ) : null}
        {card?.evidence?.n_episodes ? (
          <div>
            <dt>{t("decisions.card.nEpisodes")}</dt>
            <dd>{String(card.evidence.n_episodes)}</dd>
          </div>
        ) : null}
      </dl>
      <p className={conclusive ? "muted" : "decision-recommendation-caveat"}>
        {t(conclusive ? "summary.marginClear" : "summary.marginInsideNoise")}
      </p>
    </aside>
  );
}
