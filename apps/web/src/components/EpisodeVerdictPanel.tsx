"use client";

/** One episode: which side it went to, what happened to each, what differed.
 *
 * Its own file rather than a helper inside the page, for the reason
 * ``ProgressSync`` is: Next forbids a page module from exporting
 * anything but the route's own hooks, so a component defined there
 * cannot be rendered by a test — and this is precisely the component
 * worth rendering in one.
 *
 * **Three blocks, and they never share a heading.** A fault found on
 * one side is a diagnosis; it is not an account of the difference
 * between the two, and it reads as one the moment they run together —
 * most of all when the fault is on the side that won. The platform
 * already keeps them apart; this renders them apart.
 *
 * The caveat is printed verbatim from the payload. Rewording it in the
 * client is how a sentence meant to say "this is one episode, not the
 * run" becomes a sentence that says less.
 */

import { useTranslation } from "@/lib/i18n";
import {
  contrastStrength,
  detectionSeconds,
  hasDirection,
  orderedDiagnoses,
  sideOf,
  verdictHeadlineKey,
  type EpisodeDiagnosis,
  type EpisodeVerdictView,
} from "@/lib/episodeVerdict";

export type VerdictSlot =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ready"; view: EpisodeVerdictView }
  | { state: "unavailable"; message: string }
  | { state: "error"; message: string };

export function EpisodeVerdictPanel({
  slot,
  episodeSelected,
  onSeek,
}: {
  slot: VerdictSlot;
  /** Whether a reader has pointed at an episode. Not "whether the
   *  replay is showing one": the replay opens on the first episode so
   *  the canvases are not blank, and explaining that one would answer a
   *  question nobody asked. */
  episodeSelected: boolean;
  onSeek?: (side: "a" | "b", seconds: number) => void;
}) {
  const { t } = useTranslation();

  if (!episodeSelected) {
    return (
      <section className="panel episode-verdict" aria-live="polite">
        <h3>{t("episodeVerdict.title")}</h3>
        <p className="muted">{t("episodeVerdict.chooseAnEpisode")}</p>
      </section>
    );
  }

  if (slot.state === "idle" || slot.state === "loading") {
    return (
      <section className="panel episode-verdict" aria-live="polite">
        <h3>{t("episodeVerdict.title")}</h3>
        <p className="muted">{t("episodeVerdict.loading")}</p>
      </section>
    );
  }

  if (slot.state === "unavailable") {
    return (
      <section className="panel episode-verdict">
        <h3>{t("episodeVerdict.title")}</h3>
        <p className="muted">{slot.message}</p>
      </section>
    );
  }

  if (slot.state === "error") {
    return (
      <section className="panel episode-verdict">
        <h3>{t("episodeVerdict.title")}</h3>
        <p className="form-error">{slot.message}</p>
      </section>
    );
  }

  const { view } = slot;
  const { verdict } = view;
  const directed = hasDirection(verdict);

  return (
    <section className="panel episode-verdict">
      <h3>{t("episodeVerdict.title")}</h3>

      <p className="episode-verdict-headline">
        {t(verdictHeadlineKey(verdict), {
          winner: verdict.winner ?? "",
          loser: verdict.loser ?? "",
          reason: verdict.undecided_reason,
        })}
      </p>
      {/* Verbatim. A caveat the client may reword is a caveat the client
          may dilute, and this one guards the reading that costs most. */}
      <p className="episode-verdict-caveat">{verdict.caveat}</p>

      <h4>{t("episodeVerdict.diagnoses")}</h4>
      <div className="episode-verdict-diagnoses">
        {orderedDiagnoses(view).map((diagnosis) => (
          <DiagnosisColumn
            key={diagnosis.candidate_id}
            diagnosis={diagnosis}
            isWinner={diagnosis.candidate_id === verdict.winner}
            onSeek={
              onSeek
                ? (seconds) => {
                    const side = sideOf(view, diagnosis.candidate_id);
                    if (side) onSeek(side, seconds);
                  }
                : undefined
            }
          />
        ))}
      </div>

      {/* Never "why C1 won". These are differences with evidence behind
          them; which of them bears on the outcome is a question the
          platform answers with a claim level, not a heading. */}
      <h4>{t("episodeVerdict.contrasts")}</h4>
      {!directed ? (
        <p className="muted">{t("episodeVerdict.noDirection")}</p>
      ) : view.contrasts.length === 0 ? (
        <p className="muted">{t("episodeVerdict.noContrast")}</p>
      ) : (
        <ul className="episode-verdict-contrasts">
          {view.contrasts.map((contrast, index) => (
            <li key={`${contrast.kind}-${index}`}>
              <span className={`contrast-strength contrast-${contrastStrength(contrast.kind)}`}>
                {t(`episodeVerdict.strength.${contrastStrength(contrast.kind)}`)}
              </span>{" "}
              <span className="contrast-kind">{t(`episodeVerdict.kind.${contrast.kind}`)}</span>
              <span className="contrast-detail"> — {contrast.detail}</span>
            </li>
          ))}
        </ul>
      )}

      {/* What was looked at and deliberately not offered. A list that
          simply omitted it would read as though nobody checked. */}
      {view.ruled_out.length > 0 && (
        <details className="episode-verdict-ruled-out">
          <summary>{t("episodeVerdict.ruledOut", { count: view.ruled_out.length })}</summary>
          <ul>
            {view.ruled_out.map((item, index) => (
              <li key={`${item.kind}-${index}`}>{item.detail}</li>
            ))}
          </ul>
        </details>
      )}

      {view.omissions.length > 0 && (
        <details className="episode-verdict-omissions">
          <summary>{t("episodeVerdict.omissions", { count: view.omissions.length })}</summary>
          <ul>
            {view.omissions.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function DiagnosisColumn({
  diagnosis,
  isWinner,
  onSeek,
}: {
  diagnosis: EpisodeDiagnosis;
  isWinner: boolean;
  onSeek?: (seconds: number) => void;
}) {
  const { t } = useTranslation();
  const outcome = diagnosis.outcome;
  return (
    <div className={`episode-verdict-column${isWinner ? " is-winner" : ""}`}>
      <h5>{diagnosis.candidate_id}</h5>
      {outcome ? (
        <dl className="episode-verdict-outcome">
          <dt>{t("episodeVerdict.outcome.result")}</dt>
          <dd>
            {outcome.success
              ? t("episodeVerdict.outcome.reachedGoal")
              : outcome.failure_reason || t("episodeVerdict.outcome.failed")}
          </dd>
          <dt>{t("episodeVerdict.outcome.collisions")}</dt>
          <dd>{outcome.collision_count}</dd>
          {outcome.min_clearance !== null && (
            <>
              <dt>{t("episodeVerdict.outcome.clearance")}</dt>
              <dd>{outcome.min_clearance.toFixed(2)} m</dd>
            </>
          )}
          {outcome.travel_time_s !== null && (
            <>
              <dt>{t("episodeVerdict.outcome.travelTime")}</dt>
              <dd>{outcome.travel_time_s.toFixed(1)} s</dd>
            </>
          )}
          <dt>{t("episodeVerdict.outcome.replans")}</dt>
          <dd>{outcome.replan_count}</dd>
        </dl>
      ) : (
        /* No row is not a defeat: the candidate may never have run this
           episode, may have been eliminated before it, or may not have
           been recorded. */
        <p className="muted">{t("episodeVerdict.outcome.noRecord")}</p>
      )}

      {diagnosis.detections.length === 0 ? (
        <p className="muted">{t("episodeVerdict.noDetections")}</p>
      ) : (
        <ul className="episode-verdict-detections">
          {diagnosis.detections.map((detection, index) => {
            const seconds = detectionSeconds(detection);
            const label = t(`episodeVerdict.detection.${detection.type}`);
            return (
              <li key={`${detection.type}-${index}`}>
                {seconds !== null && onSeek ? (
                  <button type="button" className="link-button" onClick={() => onSeek(seconds)}>
                    {label}
                  </button>
                ) : (
                  <span>{label}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {diagnosis.no_path_attempts !== null && diagnosis.no_path_attempts > 0 && (
        <p className="episode-verdict-attempts">
          {t("episodeVerdict.noPathAttempts", {
            count: diagnosis.no_path_attempts,
            total: diagnosis.planning_attempts ?? 0,
          })}
        </p>
      )}
    </div>
  );
}
