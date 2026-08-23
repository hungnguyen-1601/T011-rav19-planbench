"use client";

/** Leaderboard (M5): stacks ranked within identical conditions.
 *
 * Groups are the whole point. Two rows only mean something next to each
 * other when they share a `conditions_checksum`; the UI therefore never
 * renders one flat table, because that would invite exactly the
 * cross-condition comparison the fairness record exists to prevent.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import type { Leaderboard, LeaderboardEntry, LeaderboardGroup } from "@/lib/platformTypes";

const DEFAULT_WEIGHTS = { success: 0.4, safety: 0.3, efficiency: 0.2, smoothness: 0.1 };

export default function LeaderboardPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [acceptedOnly, setAcceptedOnly] = useState(true);
  const [scenario, setScenario] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        accepted_only: String(acceptedOnly),
        weight_success: String(weights.success),
        weight_safety: String(weights.safety),
        weight_efficiency: String(weights.efficiency),
        weight_smoothness: String(weights.smoothness),
      });
      if (scenario) query.set("scenario_name", scenario);
      setBoard(await authFetch<Leaderboard>(`/leaderboard?${query}`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [acceptedOnly, scenario, weights]);


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
        </div>
        {!acceptedOnly ? (
          <div className="error-box">{t("leaderboard.unreviewedWarning")}</div>
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

      {board?.groups.map((group) => <GroupTable key={group.conditions_checksum} group={group} />)}
    </>
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
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("leaderboard.rank")}</th>
              <th>{t("algorithms.stack")}</th>
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
