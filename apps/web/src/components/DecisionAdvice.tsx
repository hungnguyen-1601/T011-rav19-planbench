"use client";

/** Three use cases, three answers, on every run.
 *
 * **Including the runs that recommended nothing**, which is the whole
 * point: "no recommendation" is a fact about this comparison, and the
 * reader still has to decide what runs on the robot tomorrow. On a
 * blocked run the honest answer to two of these three is *nothing here*,
 * and saying it — with the gate that produced it — is more use than an
 * absent panel.
 *
 * **The hybrid card is not a slogan.** It appears only when one stack
 * genuinely leads on what the robot achieved and another on what it
 * spent, and when it appears it carries a routing rule somebody could
 * implement and check. "Consider a hybrid approach" with nothing under
 * it is the sentence this card exists instead of.
 */

import { Icon } from "@/components/Icon";
import { type DecisionAdvice as Advice, decisionAdvice } from "@/lib/decisionAdvice";
import { standings } from "@/lib/conclusion";
import type { DecisionRun } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

export function DecisionAdvice({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates = run.report?.candidates ?? [];
  if (candidates.length === 0) return null;

  const advice = decisionAdvice(run);
  // Named, with the gate that stopped them. "No candidate" is a weaker
  // sentence than "rrtstar+dwa, blocked at G3" and costs the same room.
  const blocked = standings(candidates)
    .blocked.map((entry) =>
      entry.blockingGates.length > 0
        ? `${entry.label} · ${entry.config} (${entry.blockingGates.join(", ")})`
        : `${entry.label} · ${entry.config}`,
    )
    .join(" · ");

  const cards = adviceCards(advice, blocked, t);

  return (
    <section className="panel decision-advice" aria-labelledby="decision-advice-title">
      <div className="panel-head">
        <h3 id="decision-advice-title">{t("advice.title")}</h3>
      </div>
      <div className="decision-advice-grid">
        {cards.map((card) => (
          <article
            key={card.useCase}
            className={`decision-advice-card${card.answer === null ? " is-empty" : ""}`}
          >
            <span className="decision-advice-case">
              <Icon name={card.icon} size={14} />
              {t(card.useCase)}
            </span>
            {card.answer === null ? (
              <strong className="decision-advice-none">{t("advice.answer.nothing")}</strong>
            ) : (
              <strong className="decision-advice-answer">{card.answer}</strong>
            )}
            <p className="decision-advice-why">{card.why}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

interface AdviceCard {
  useCase: string;
  icon: "trophy" | "cpu" | "benchmark";
  /** `null` renders "nothing here", which is an answer. An empty string
   *  would render as a card that forgot to say anything. */
  answer: string | null;
  why: string;
}

/** The three cards, for one advice. Split out so a test can assert the
 *  copy of a branch without rendering React. */
export function adviceCards(
  advice: Advice,
  blocked: string,
  t: (key: string, vars?: Record<string, string>) => string,
): AdviceCard[] {
  const quality = "advice.case.quality";
  const realtime = "advice.case.realtime";
  const both = "advice.case.both";

  switch (advice.kind) {
    case "none":
      return [
        { useCase: quality, icon: "trophy", answer: null, why: t("advice.why.noneQuality", { blocked }) },
        { useCase: realtime, icon: "cpu", answer: null, why: t("advice.why.noneRealtime", { blocked }) },
        { useCase: both, icon: "benchmark", answer: null, why: t("advice.why.noneBoth") },
      ];
    case "sole":
      return [
        {
          useCase: quality,
          icon: "trophy",
          answer: advice.sole.label,
          why: t("advice.why.soleQuality"),
        },
        { useCase: realtime, icon: "cpu", answer: null, why: t("advice.why.soleRealtime", { blocked }) },
        { useCase: both, icon: "benchmark", answer: null, why: t("advice.why.soleBoth") },
      ];
    case "tie":
      return [
        {
          useCase: quality,
          icon: "trophy",
          answer: advice.parties[0].label,
          why: t("advice.why.tieQuality"),
        },
        {
          useCase: realtime,
          icon: "cpu",
          answer: advice.parties[0].label,
          why: t("advice.why.tieRealtime"),
        },
        { useCase: both, icon: "benchmark", answer: null, why: t("advice.why.tieBoth") },
      ];
    case "single":
      return [
        {
          useCase: quality,
          icon: "trophy",
          answer: advice.winner.label,
          why: t("advice.why.singleQuality"),
        },
        {
          useCase: realtime,
          icon: "cpu",
          answer: advice.winner.label,
          why: t("advice.why.singleRealtime"),
        },
        { useCase: both, icon: "benchmark", answer: advice.winner.label, why: t("advice.why.singleBoth") },
      ];
    case "hybrid":
      return [
        {
          useCase: quality,
          icon: "trophy",
          answer: advice.quality.label,
          why: t("advice.why.hybridQuality"),
        },
        {
          useCase: realtime,
          icon: "cpu",
          answer: advice.realtime.label,
          why: t("advice.why.hybridRealtime"),
        },
        {
          useCase: both,
          icon: "benchmark",
          answer: t("advice.answer.route"),
          // The rule and its cost in one breath. Routing means both
          // stacks are built, tested and shipped, and a reader deciding
          // on the strength of the first half should meet the second.
          why: t("advice.why.hybridBoth", {
            quality: advice.quality.label,
            realtime: advice.realtime.label,
          }),
        },
      ];
  }
}
