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
import { FieldError } from "@/lib/auth";
import {
  firedSightings,
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

      <SightingsBlock observations={packet.observations} />
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
function SightingsBlock({ observations }: { observations: PacketObservation[] }) {
  const { t } = useTranslation();
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
              <td><code>{item.type}</code></td>
              <td><code>{item.candidate_id}</code></td>
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
        <span>{t("evidence.lattice.title")}</span>
        <span className="badge muted-badge">{findings.length}</span>
      </summary>
      <ul>
        {orderedFindings(findings).map((finding) => (
          <li key={finding.detection_type}>
            <code>{finding.detection_type}</code>{" "}
            <span className={`badge ${verdictTone(finding.verdict)}`}>
              {t(`evidence.lattice.verdict.${finding.verdict}`)}
            </span>
            {finding.subject ? <code className="evidence-subject">{finding.subject}</code> : null}
            <p className="muted small">{finding.reason}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
