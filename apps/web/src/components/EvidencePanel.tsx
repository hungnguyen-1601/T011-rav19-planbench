"use client";

/** The evidence behind a decision, under the gate table (E4.1/E4.2).
 *
 * **Under the gates, and that placement is the argument.** The gate
 * table says who was eliminated where; this says what was seen while
 * they ran. A reader who has just been told "G3: fail" should find the
 * sightings next, not three sections later behind a recommendation.
 *
 * **A run with no ranking still has one of these.** Three of the five
 * outcomes produce no pair, so no ΔU decomposition — and those are the
 * runs somebody most asks "why did it fail" about. The waterfall block
 * disappears; the sightings, the lattice and the declared gaps stay.
 *
 * **Nothing here is a conclusion.** Claims come from the promotion
 * matrix run over a checker result, and no analyst has passed the gate
 * yet. What this panel shows is evidence with nothing drawn on it, and
 * it says so rather than letting a reader supply the inference silently.
 */

import { useEffect, useState } from "react";

import {
  type DecisionRun,
  type ExplanationView,
  type PacketLatticeFinding,
  type PacketObservation,
  type PacketWaterfall,
  getExplanation,
} from "@/lib/decisions";
import { Hint } from "@/components/Hint";
import { FieldError } from "@/lib/auth";
import {
  firedSightings,
  latticePlain,
  latticeReason,
  missingNotes,
  orderedFindings,
  sightingsState,
  verdictTone,
  waterfallState,
  widestContribution,
} from "@/lib/evidence";
import { panelPlan } from "@/lib/explainPanel";
import { useTranslation } from "@/lib/i18n";

export function EvidencePanel({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const plan = panelPlan(run);
  const [view, setView] = useState<ExplanationView | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const fetched = await getExplanation(run.id);
        if (live) setView(fetched);
      } catch (caught) {
        if (!live) return;
        // A 409 is a *state*: this run was scored before the packet
        // builder existed. Rendering it as an error box would tell a
        // reader something broke, when what happened is that a run
        // predates a feature.
        //
        // `FieldError`, not `ApiError`: `authFetch` throws the former
        // and the first version of this checked the latter, so every
        // 409 fell through to the red box. The status had to be added
        // to the error for this to be checkable at all — before that
        // the only way to tell a state from a fault was to read the
        // message, which is the thing this codebase keeps refusing to
        // do with failure codes.
        if (caught instanceof FieldError && caught.status === 409) {
          setUnavailable(caught.message);
        } else {
          setFailed(caught instanceof Error ? caught.message : String(caught));
        }
      }
    })();
    return () => {
      live = false;
    };
  }, [run.id]);

  if (failed) return <div className="error-box">{failed}</div>;
  if (unavailable) {
    return (
      <div className="panel evidence-panel">
        <div className="panel-head">
          <h3>{t("evidence.title")}</h3>
        </div>
        <p className="muted">{t("evidence.unavailable")}</p>
        <p className="muted small">{unavailable}</p>
      </div>
    );
  }
  if (!view) return null;

  const { packet } = view;
  const missing = missingNotes(view);
  const noWaterfall = waterfallState(packet.decision.waterfall, plan.showWaterfall);

  return (
    <div className="panel evidence-panel">
      <div className="panel-head">
        <h3>{t("evidence.title")}</h3>
        <span className="badge muted-badge">{t("evidence.noClaimsYet")}</span>
      </div>

      {noWaterfall === "none" && packet.decision.waterfall ? (
        <WaterfallBlock waterfall={packet.decision.waterfall} />
      ) : (
        <p className="muted">
          {t(
            noWaterfall === "run-ranked-nobody"
              ? "evidence.noComparison"
              : "evidence.comparisonWithheld",
          )}
        </p>
      )}

      <SightingsBlock observations={packet.observations} run={run} />
      <LatticeBlock findings={packet.lattice} />

      {packet.known_unknowns.length > 0 ? (
        <details className="evidence-gaps">
          <summary>
            <span>{t("evidence.gaps.title")}</span>
            <span className="badge muted-badge">{packet.known_unknowns.length}</span>
          </summary>
          <ul>
            {packet.known_unknowns.map((gap) => (
              <li key={gap.id}>
                <code>{gap.id}</code> — {t("evidence.gaps.blocks")}{" "}
                {gap.blocks_claim_types.join(", ")} <span className="muted">({gap.source})</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {missing.length > 0 ? (
        <details className="evidence-omissions">
          <summary>
            <span>{t("evidence.omissions.title")}</span>
            <span className="badge muted-badge">{missing.length}</span>
          </summary>
          <ul>
            {missing.map((item) => (
              <li key={item.note}>
                {item.kind === "skipped" ? `${t("evidence.omissions.skipped")}: ` : null}
                {item.note}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

/** The paired ΔU decomposition, as bars that sum to the total.
 *
 * The interval is printed beside every bar rather than only on the
 * total: a contribution of 0.02 with an interval crossing zero and one
 * with an interval clear of it are different findings, and a bar chart
 * without them invites reading the height alone.
 */
function WaterfallBlock({ waterfall }: { waterfall: PacketWaterfall }) {
  const { t } = useTranslation();
  const widest = widestContribution(waterfall);
  return (
    <div className="evidence-waterfall">
      <p className="evidence-lede">
        {t("evidence.waterfall.lede")} <code>{waterfall.candidate_a}</code> −{" "}
        <code>{waterfall.candidate_b}</code> · {waterfall.n_episodes}{" "}
        {t("evidence.waterfall.episodes")}
      </p>
      <table className="evidence-table">
        <thead>
          <tr>
            <th>{t("evidence.waterfall.objective")}</th>
            <th>{t("evidence.waterfall.weight")}</th>
            <th>{t("evidence.waterfall.delta")}</th>
            <th>{t("evidence.waterfall.contribution")}</th>
            <th>{t("evidence.waterfall.ci")}</th>
          </tr>
        </thead>
        <tbody>
          {waterfall.bars.map((bar) => (
            <tr key={bar.objective}>
              <td><code>{bar.objective}</code></td>
              <td>{bar.weight.toFixed(2)}</td>
              <td>{bar.delta_objective_mean.toFixed(4)}</td>
              <td>
                <span className="evidence-bar-wrap">
                  <span
                    className={`evidence-bar ${bar.contribution < 0 ? "neg" : "pos"}`}
                    style={{ width: `${(Math.abs(bar.contribution) / widest) * 100}%` }}
                  />
                  {bar.contribution.toFixed(4)}
                </span>
              </td>
              <td className="muted">
                [{bar.ci95[0].toFixed(4)}, {bar.ci95[1].toFixed(4)}]
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th colSpan={3}>{t("evidence.waterfall.total")}</th>
            <th>{waterfall.delta_utility_mean.toFixed(4)}</th>
            <th className="muted">
              [{waterfall.total_ci95[0].toFixed(4)}, {waterfall.total_ci95[1].toFixed(4)}]
            </th>
          </tr>
        </tfoot>
      </table>
      {/* The median is printed and deliberately not decomposed: the
          identity that makes the bars sum to the total holds through the
          mean and not through the median. */}
      <p className="muted small">
        {t("evidence.waterfall.median")}: {waterfall.delta_utility_median.toFixed(4)}
      </p>
    </div>
  );
}

/** What the detectors saw, as a fraction of the episodes looked at. */
function SightingsBlock({
  observations,
  run,
}: {
  observations: PacketObservation[];
  run: DecisionRun;
}) {
  const { t } = useTranslation();
  /* **The hash is an identity, not a name.** This column printed
     `29cdf6266a44` and nothing else, and a reader who has spent the page
     comparing `astar+dwa` against `rrtstar+dwa` has nowhere to look it
     up: the ids appear on no other panel. Named from the run's own
     candidate list, with the hash kept beside it — the hash is what a
     trace path and a bug report are keyed on, so removing it would trade
     one unusable column for another. */
  const named = new Map(
    (run.report?.candidates ?? []).map((candidate) => [
      candidate.candidate_id,
      `${candidate.stack_label} · ${candidate.local_controller_config}`,
    ]),
  );
  const state = sightingsState(observations);
  // "The detectors never ran" and "they ran and found nothing" both
  // render an empty table and mean opposite things.
  if (state === "no-traces") return <p className="muted">{t("evidence.sightings.none")}</p>;
  if (state === "clean") return <p className="muted">{t("evidence.sightings.clean")}</p>;
  const sightings = firedSightings(observations);
  return (
    <div className="evidence-sightings">
      <h4>{t("evidence.sightings.title")}</h4>
      <table className="evidence-table">
        <thead>
          <tr>
            <th>{t("evidence.sightings.pattern")}</th>
            <th>{t("evidence.sightings.candidate")}</th>
            <th>{t("evidence.sightings.episodes")}</th>
          </tr>
        </thead>
        <tbody>
          {sightings.map((item) => (
            <tr key={`${item.type}:${item.candidate_id}`}>
              {/* **The plain name leads and the code follows it.**
                  `near_miss_cluster` is precise, checkable against the
                  replay, and the id every report and trace path is keyed
                  on — and it is also the reason a reader who is not on
                  this team cannot tell whether the row is a problem. The
                  name says what the robot did; the hint says what had to
                  happen for the detector to fire, thresholds included,
                  so the row can be argued with rather than believed. */}
              <td>
                <span className="evidence-pattern">
                  {t(`evidence.detector.name.${item.type}`)}
                  <Hint
                    text={t(`evidence.detector.what.${item.type}`)}
                    label={t(`evidence.detector.name.${item.type}`)}
                  />
                </span>
                <code className="evidence-pattern-id">{item.type}</code>
              </td>
              <td>
                {named.has(item.candidate_id) ? (
                  <>
                    {named.get(item.candidate_id)}{" "}
                    <code className="evidence-sighting-id">{item.candidate_id}</code>
                  </>
                ) : (
                  /* A run whose packet names a candidate its report does
                     not. Printing the hash alone is the honest fallback:
                     inventing a label would be worse than an opaque one. */
                  <code>{item.candidate_id}</code>
                )}
              </td>
              {/* A fraction, never a percentage. "3%" hides that it was
                  one episode out of thirty. */}
              <td>
                {item.episodes_seen}/{item.episodes_total}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** What the contrast between the two stacks does and does not support. */
function LatticeBlock({ findings }: { findings: PacketLatticeFinding[] }) {
  const { t } = useTranslation();
  if (findings.length === 0) return null;
  return (
    <details className="evidence-lattice" open>
      <summary>
        <span>{t("evidence.lattice.plainTitle")}</span>
        <span className="badge muted-badge">{findings.length}</span>
      </summary>
      {/* The rule the whole block runs on, said once at the top rather
          than implied by seven verdict badges. */}
      <p className="muted small evidence-lattice-note">{t("evidence.lattice.plainNote")}</p>
      <ul>
        {orderedFindings(findings).map((finding) => (
          <li key={finding.detection_type}>
            <span className="evidence-pattern">
              {t(`evidence.detector.name.${finding.detection_type}`)}
              <Hint
                text={t(`evidence.detector.what.${finding.detection_type}`)}
                label={t(`evidence.detector.name.${finding.detection_type}`)}
              />
            </span>
            <span className={`badge ${verdictTone(finding.verdict)}`}>
              {t(`evidence.lattice.verdict.${finding.verdict}`)}
            </span>
            <code className="evidence-pattern-id">{finding.detection_type}</code>
            {/* The claim, then the method that reached it. The method
                note used to be the only line here, and it describes the
                experiment rather than the result. */}
            <LatticeClaim finding={finding} />
            <details className="evidence-method">
              <summary className="muted small">{t("evidence.lattice.method")}</summary>
              <LatticeReason finding={finding} />
            </details>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** What the finding amounts to, in one sentence.
 *
 * Named components are worded; the two verdicts that isolate nothing
 * name none, and their sentences do not have a slot for one. */
function LatticeClaim({ finding }: { finding: PacketLatticeFinding }) {
  const { t } = useTranslation();
  const plain = latticePlain(finding);
  return (
    <p className="evidence-claim">
      {t(plain.key, { component: plain.componentKey ? t(plain.componentKey) : "" })}
    </p>
  );
}

/** The finding's reason, in the reader's language where that is possible
 *  and in the platform's own words where it is not. */
function LatticeReason({ finding }: { finding: PacketLatticeFinding }) {
  const { t } = useTranslation();
  const reason = latticeReason(finding);
  return (
    <p className="muted small">
      {reason.translated
        ? t(reason.key, { subject: reason.subject ?? "" })
        : reason.text}
    </p>
  );
}
