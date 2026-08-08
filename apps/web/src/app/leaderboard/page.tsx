"use client";

/** Leaderboard (M5): stacks ranked within identical conditions.
 *
 * Groups are the whole point. Two rows only mean something next to each
 * other when they share a `conditions_checksum` *and* were shown the
 * same thing (P02); the UI therefore never renders one flat table,
 * because that would invite exactly the comparison the fairness record
 * and the observation class exist to prevent.
 *
 * Mixing observation classes is possible but opt-in, and a mixed table
 * is rendered with the warning attached — a screenshot of the ranking
 * should never travel without it.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { DifficultyCurveChart } from "@/components/DifficultyCurveChart";
import { EmptyState } from "@/components/EmptyState";
import { GeneralizationGapChart } from "@/components/GeneralizationGapChart";
import { authFetch, useSession } from "@/lib/auth";
import { buildDifficultyCurve, buildGapSeries } from "@/lib/charts";
import { useTranslation } from "@/lib/i18n";
import type {
  DifficultyCalibrationSummary,
  GeneralizationSummary,
  Leaderboard,
  LeaderboardEntry,
  LeaderboardGroup,
} from "@/lib/platformTypes";

const DEFAULT_WEIGHTS = { success: 0.4, safety: 0.3, efficiency: 0.2, smoothness: 0.1 };

export default function LeaderboardPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [generalization, setGeneralization] = useState<GeneralizationSummary | null>(null);
  const [calibration, setCalibration] = useState<DifficultyCalibrationSummary | null>(null);
  // The board the difficulty curve is drawn from: the same one when no
  // scenario filter is set, an unfiltered one when there is.
  const [curveBoard, setCurveBoard] = useState<Leaderboard | null>(null);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [acceptedOnly, setAcceptedOnly] = useState(true);
  const [groupByObservation, setGroupByObservation] = useState(true);
  const [scenario, setScenario] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        accepted_only: String(acceptedOnly),
        group_by_observation_class: String(groupByObservation),
        weight_success: String(weights.success),
        weight_safety: String(weights.safety),
        weight_efficiency: String(weights.efficiency),
        weight_smoothness: String(weights.smoothness),
      });
      if (scenario) query.set("scenario_name", scenario);
      const ranked = await authFetch<Leaderboard>(`/leaderboard?${query}`);
      setBoard(ranked);
      // The gap follows the same acceptance rule as the ranking, and
      // ignores the scenario filter: it is a statement about dev against
      // held-out scenarios, so narrowing it to one scenario would be a
      // different question with the same name.
      setGeneralization(
        await authFetch<GeneralizationSummary>(
          `/generalization?accepted_only=${String(acceptedOnly)}`,
        ),
      );
      // The difficulty curve is a shape across scenarios, so it is built
      // from an unfiltered board for the same reason. Refetched rather
      // than reused: one scenario is one point, and a "curve" through a
      // single point is a line the reader would draw themselves.
      setCurveBoard(
        scenario
          ? await authFetch<Leaderboard>(
              `/leaderboard?accepted_only=${String(acceptedOnly)}` +
                `&group_by_observation_class=${String(groupByObservation)}`,
            )
          : ranked,
      );
      setCalibration(
        await authFetch<DifficultyCalibrationSummary>("/difficulty-calibration"),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [acceptedOnly, groupByObservation, scenario, weights]);


  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("leaderboard.title")}</h2>
          <p>{t("leaderboard.subtitle")}</p>
        </div>
      </div>
      {!session ? (
        <div className="notice">
          <Link href="/login">{t("topbar.signIn")}</Link> — {t("common.signInRequired")}
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <h3>{t("leaderboard.scoring")}</h3>
        <div className="toolbar">
          {(Object.keys(DEFAULT_WEIGHTS) as (keyof typeof DEFAULT_WEIGHTS)[]).map((key) => (
            <label key={key} className="field">
              {t(`leaderboard.weight.${key}`)}
              <input
                type="number"
                min={0}
                step={0.05}
                value={weights[key]}
                onChange={(event) =>
                  setWeights({ ...weights, [key]: Math.max(0, Number(event.target.value)) })
                }
              />
            </label>
          ))}
          <label className="field">
            {t("leaderboard.scenarioFilter")}
            <input
              value={scenario}
              placeholder={t("leaderboard.allScenarios")}
              onChange={(event) => setScenario(event.target.value.trim())}
            />
          </label>
          <label className="inline">
            <input
              type="checkbox"
              checked={acceptedOnly}
              onChange={(event) => setAcceptedOnly(event.target.checked)}
            />
            {t("leaderboard.acceptedOnly")}
          </label>
          <label className="inline" title={t("leaderboard.observationGroupingHint")}>
            <input
              type="checkbox"
              checked={groupByObservation}
              onChange={(event) => setGroupByObservation(event.target.checked)}
            />
            {t("leaderboard.groupByObservation")}
          </label>
        </div>
        {!acceptedOnly ? (
          <div className="error-box">{t("leaderboard.unreviewedWarning")}</div>
        ) : null}
        {!groupByObservation ? (
          <div className="error-box">{t("leaderboard.mixedObservationWarning")}</div>
        ) : null}
        {board ? <p className="muted formula">{board.score_formula}</p> : null}
      </div>

      {loading ? <p className="muted">{t("common.loading")}</p> : null}

      {board && board.groups.length === 0 && !loading ? (
        <div className="panel">
          <EmptyState
            icon="trophy"
            title={t("leaderboard.empty.title")}
            body={
              acceptedOnly ? t("leaderboard.emptyAccepted") : t("leaderboard.emptyAny")
            }
            actionHref="/benchmarks"
            actionLabel={t("dashboard.action.createBenchmark")}
          />
        </div>
      ) : null}

      <DifficultyCurvePanel board={curveBoard} calibration={calibration} />

      {board?.groups.map((group) => <GroupTable key={group.conditions_checksum} group={group} />)}

      {generalization && generalization.entries.length > 0 ? (
        <GeneralizationPanel summary={generalization} />
      ) : null}
    </>
  );
}

/** Success rate against measured difficulty (F09).
 *
 * The panel refuses to draw a curve it cannot honestly draw. Without a
 * calibration there is no x axis at all, and the answer is to run
 * `scripts/calibrate_difficulty.py` — not to fall back on curriculum
 * order, which is a hand-written intention and would produce a chart that
 * looks measured and is not.
 *
 * Scenarios with results but no measured difficulty are named under the
 * chart. They are missing from every line, and a reader comparing two
 * stacks has to know how much of the evidence is not on screen.
 */
function DifficultyCurvePanel({
  board,
  calibration,
}: {
  board: Leaderboard | null;
  calibration: DifficultyCalibrationSummary | null;
}) {
  const { t } = useTranslation();
  const curve = useMemo(() => buildDifficultyCurve(board, calibration), [board, calibration]);
  if (!board) return null;
  return (
    <div className="panel">
      <h3>{t("charts.difficultyCurve")}</h3>
      <p className="muted" style={{ fontSize: 12 }}>
        {t("charts.difficultyCurveHint")}
      </p>
      {curve.calibrationVersion === null ? (
        <div className="notice">{t("charts.noCalibration")}</div>
      ) : null}
      {curve.series.length === 0 ? (
        <p className="muted">{t("charts.noCurveData")}</p>
      ) : (
        <>
          <DifficultyCurveChart curve={curve} />
          <p className="muted" style={{ fontSize: 12 }}>
            {t("charts.difficultyBaseline", {
              algorithm: curve.baselineAlgorithm ?? "—",
              version: curve.calibrationVersion ?? "—",
            })}
          </p>
        </>
      )}
      {curve.uncalibrated.length > 0 ? (
        <p className="muted" style={{ fontSize: 12 }}>
          {t("charts.uncalibratedScenarios", { scenarios: curve.uncalibrated.join(", ") })}
        </p>
      ) : null}
      {curve.stale.length > 0 ? (
        <p className="muted" style={{ fontSize: 12 }}>
          {t("charts.staleScenarios", { scenarios: curve.stale.join(", ") })}
        </p>
      ) : null}
    </div>
  );
}

/** Dev against held-out results (P05), as a table and as bars (F09).
 *
 * The table stays. It is the surface where a missing held-out result is
 * visible as missing — a chart can only omit that bar, and an omission is
 * easy to read past. The bars are there because a gap is a comparison,
 * and a comparison is faster to see than to read.
 */
function GeneralizationPanel({ summary }: { summary: GeneralizationSummary }) {
  const { t } = useTranslation();
  const series = useMemo(() => buildGapSeries(summary), [summary]);
  return (
    <div className="panel">
      <h3>{t("generalization.title")}</h3>
      <p className="muted" style={{ fontSize: 12 }}>
        {t("generalization.hint")}
      </p>
      {summary.warnings.map((warning) => (
        <div className="notice" key={warning}>
          {warning}
        </div>
      ))}
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("algorithms.stack")}</th>
              <th>{t("detail.metric")}</th>
              <th>{t("generalization.dev")}</th>
              <th>{t("generalization.holdout")}</th>
              <th>{t("generalization.gap")}</th>
            </tr>
          </thead>
          <tbody>
            {summary.entries.flatMap((entry) =>
              summary.metrics.map((metric) => {
                const dev = entry.dev?.metrics[metric.name];
                const holdout = entry.holdout?.metrics[metric.name];
                const gap = entry.gap?.[metric.name];
                // A positive gap means dev scored higher. Whether that is
                // a degradation depends on the metric's direction, which
                // the backend states rather than the UI assuming.
                const worse =
                  gap === undefined ? null : metric.higher_is_better ? gap > 0 : gap < 0;
                return (
                  <tr key={`${entry.algorithm}-${metric.name}`}>
                    <td>
                      <code>{entry.algorithm}</code>
                    </td>
                    <td className="muted">{metric.name}</td>
                    <td title={entry.dev?.scenarios.join(", ")}>{fmt(dev ?? null, 3)}</td>
                    <td title={entry.holdout?.scenarios.join(", ")}>{fmt(holdout ?? null, 3)}</td>
                    <td>
                      {gap === undefined ? (
                        <span className="muted">{t("generalization.noGap")}</span>
                      ) : (
                        <span
                          className={worse ? "badge warn" : "badge ok"}
                          title={
                            worse
                              ? t("generalization.worseOnHoldout")
                              : t("generalization.betterOnHoldout")
                          }
                        >
                          {gap > 0 ? "+" : ""}
                          {gap.toFixed(3)}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>
      </div>
      {/* One chart per metric: success rate, travel time and path
          efficiency do not share a unit, and a single axis carrying all
          three would invite comparison by height. */}
      {series
        .filter((one) => one.rows.length > 0)
        .map((one) => (
          <div key={one.metric} style={{ marginTop: 12 }}>
            <h4 style={{ marginBottom: 4 }}>{one.metric}</h4>
            <GeneralizationGapChart series={one} />
            {one.incomplete.length > 0 ? (
              <p className="muted" style={{ fontSize: 12 }}>
                {t("charts.incompleteGap", { algorithms: one.incomplete.join(", ") })}
              </p>
            ) : null}
          </div>
        ))}
      {summary.entries.map((entry) =>
        entry.warnings.map((warning) => (
          <p className="muted" key={`${entry.algorithm}-${warning}`} style={{ fontSize: 12 }}>
            <code>{entry.algorithm}</code> — {warning}
          </p>
        )),
      )}
      {summary.holdout_usage.length > 0 ? (
        <p className="muted" style={{ fontSize: 12 }} title={t("generalization.holdoutUsageHint")}>
          {t("generalization.holdoutUsage")}: {summary.holdout_usage.length} —{" "}
          {summary.holdout_usage.map((use) => use.scenario_name).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

function GroupTable({ group }: { group: LeaderboardGroup }) {
  const { t } = useTranslation();
  return (
    <div className="panel">
      <h3>
        {group.scenario_name}{" "}
        <span className="muted">{t("leaderboard.on", { map: group.map_name })}</span>
      </h3>
      <p className="muted">
        {/* Seeds and the checksum are protocol values: never translated. */}
        {t("leaderboard.groupHint", {
          seeds: group.seeds.join(", "),
          checksum: group.conditions_checksum,
        })}
      </p>
      {/* What every row here was shown. Stated on the group, because it
       *  is a property of the comparison, not of one algorithm. */}
      {group.local_observation_class ? (
        <p className="muted" title={t("leaderboard.observationHint")}>
          {t("leaderboard.groupObservation", { observation: group.local_observation_class })}
        </p>
      ) : null}
      {/* Stated separately from the controller line because the two can
       *  disagree: replanning upgrades the global class and leaves the
       *  controller alone. Without this, a replanning group and a
       *  non-replanning one look identical here. */}
      {group.global_observation_class ? (
        <p className="muted" title={t("leaderboard.observationHint")}>
          {t(
            group.global_observation_class.includes("human_states")
              ? "leaderboard.groupGlobalObservationReplanning"
              : "leaderboard.groupGlobalObservation",
            { observation: group.global_observation_class },
          )}
        </p>
      ) : null}
      {group.cross_observation_class_warning ? (
        <div className="error-box">{t("leaderboard.mixedObservationWarning")}</div>
      ) : null}
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("leaderboard.rank")}</th>
              <th>{t("algorithms.stack")}</th>
              <th title={t("leaderboard.observationHint")}>{t("leaderboard.observation")}</th>
              <th>{t("leaderboard.score")}</th>
              <th>{t("leaderboard.success")}</th>
              <th>{t("leaderboard.collision")}</th>
              <th>{t("leaderboard.travel")}</th>
              <th>{t("leaderboard.efficiency")}</th>
              <th>{t("leaderboard.clearance")}</th>
              <th>{t("leaderboard.benchmark")}</th>
            </tr>
          </thead>
          <tbody>
            {group.entries.map((entry, index) => (
              <Row
                key={`${entry.benchmark_id}-${entry.algorithm}`}
                entry={entry}
                rank={index + 1}
              />
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">{t("leaderboard.notComparable")}</p>
    </div>
  );
}

function Row({ entry, rank }: { entry: LeaderboardEntry; rank: number }) {
  const { t } = useTranslation();
  return (
    <tr>
      <td className="muted">{rank}</td>
      <td>
        <code>{entry.algorithm}</code>
      </td>
      <td>
        {entry.local_observation_class === null ? (
          <span className="muted" title={t("leaderboard.observationUnknownHint")}>
            {t("leaderboard.observationUnknown")}
          </span>
        ) : (
          <span
            className="muted"
            title={t("leaderboard.observationRowHint", {
              global: entry.global_observation_class ?? "—",
              local: entry.local_observation_class,
            })}
          >
            <code>{entry.local_observation_class}</code>
          </span>
        )}
      </td>
      <td>
        {entry.overall_score === null ? (
          <span className="muted" title={t("leaderboard.noScore")}>
            —
          </span>
        ) : (
          <strong>{entry.overall_score.toFixed(3)}</strong>
        )}
      </td>
      <td>{(entry.success_rate * 100).toFixed(0)}%</td>
      <td>{(entry.collision_rate * 100).toFixed(0)}%</td>
      <td>{fmt(entry.mean_travel_time)}</td>
      <td>{fmt(entry.mean_path_efficiency, 3)}</td>
      <td>{fmt(entry.worst_min_clearance, 3)}</td>
      <td>
        <Link href={`/benchmarks/${entry.benchmark_id}`}>{entry.benchmark_name}</Link>
      </td>
    </tr>
  );
}

function fmt(value: number | null, digits = 2): string {
  return value === null ? "—" : value.toFixed(digits);
}
