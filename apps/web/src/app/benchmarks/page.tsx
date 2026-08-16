"use client";

/** Benchmark list + creation. Approval actions live on the detail page. */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/Icon";
import { SplitBadge } from "@/components/SplitBadge";
import { StateBadge } from "@/components/StateBadge";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { listModels, type ModelSummary } from "@/lib/models";
import { NO_REPLANNING, ReplanningControls } from "@/components/ReplanningControls";
import type { AlgorithmInfo, BenchmarkResource, ReplanningConfig } from "@/lib/benchmarkTypes";
import type { ScenarioProtocolMetadata, ScenarioSplit } from "@/lib/platformTypes";
import type { MapSummary, ScenarioResource } from "@/lib/types";

export default function BenchmarksPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [benchmarks, setBenchmarks] = useState<BenchmarkResource[]>([]);
  const [algorithms, setAlgorithms] = useState<AlgorithmInfo[]>([]);
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioResource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("dwa-baseline");
  const [mapId, setMapId] = useState("");
  const [scenarioId, setScenarioId] = useState("");
  const [selected, setSelected] = useState<string[]>(["astar+dwa"]);
  // PPO needs a model from the registry. Loaded once and filtered to
  // the usable ones, so the dropdown never offers something that will
  // be refused at launch.
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [modelId, setModelId] = useState("");
  const [seedText, setSeedText] = useState("1,2,3");
  // One rule for the whole sweep. It sits beside the seeds rather than
  // beside the stack checkboxes on purpose: replanning is a condition of
  // the comparison, and a per-algorithm control would be the unfairness
  // the whole platform exists to rule out.
  const [replanning, setReplanning] = useState<ReplanningConfig>(NO_REPLANNING);
  // P05: which scenarios are held out. Resolved by scenario *name*,
  // because the split belongs to the evaluation protocol and not to the
  // stored scenario row — two imports of `intersection` are two rows and
  // one held-out scenario.
  const [splits, setSplits] = useState<Record<string, ScenarioSplit>>({});

  const refresh = useCallback(async () => {
    try {
      const [list, algorithmList, mapList, scenarioList, modelList, protocol] = await Promise.all([
        authFetch<BenchmarkResource[]>("/benchmarks"),
        authFetch<AlgorithmInfo[]>("/algorithms"),
        authFetch<MapSummary[]>("/maps"),
        authFetch<ScenarioResource[]>("/scenarios"),
        // usable_only: a model that is disabled or failed validation
        // would be refused at launch, so it is never offered here.
        listModels(true),
        authFetch<ScenarioProtocolMetadata[]>("/scenario-protocol"),
      ]);
      setBenchmarks(list);
      setAlgorithms(algorithmList);
      setMaps(mapList);
      setScenarios(scenarioList);
      setModels(modelList);
      setSplits(
        Object.fromEntries(protocol.map((row) => [row.scenario_name, row.split])) as Record<
          string,
          ScenarioSplit
        >,
      );
      if (!modelId && modelList.length > 0) setModelId(modelList[0].id);
      if (!mapId && mapList.length > 0) setMapId(mapList[0].id);
      if (!scenarioId && scenarioList.length > 0) setScenarioId(scenarioList[0].id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [mapId, scenarioId, modelId]);

  useEffect(() => {
    if (!session) return;
    void refresh();
    // refresh's identity changes every render; re-run only when the
    // session appears or changes, not on each keystroke in the form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const seeds = seedText
        .split(",")
        .map((value) => Number(value.trim()))
        .filter((value) => Number.isInteger(value));
      await authFetch<BenchmarkResource>("/benchmarks", {
        method: "POST",
        body: JSON.stringify({
          name,
          map_id: mapId,
          scenario_id: scenarioId,
          // A model *id*, never a path: the server resolves it to a
          // file at launch and records the checksum that ran.
          algorithms: selected.map((id) => ({
            id,
            config: id === "astar+ppo" ? { model_id: modelId } : {},
          })),
          seeds,
          // Omitted when off, so a payload that never mentions
          // replanning cannot turn it on and cannot change the
          // conditions checksum of a run that did not use it.
          ...(replanning.enabled ? { replanning } : {}),
        }),
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!session) {
    return (
      <>
        <div className="page-head">
          <div>
            <h2>{t("benchmarks.title")}</h2>
            <p>{t("benchmarks.subtitle")}</p>
          </div>
        </div>
        <div className="panel">
          <EmptyState
            icon="user"
            title={t("dashboard.empty.signedOut.title")}
            body={t("common.signInTo")}
            actionHref="/login"
            actionLabel={t("topbar.signIn")}
          />
        </div>
      </>
    );
  }

  // Creating a benchmark needs an account and nothing else.
  const isMember = Boolean(session);

  const selectedScenario = scenarios.find((item) => item.id === scenarioId);
  const selectedSplit: ScenarioSplit = selectedScenario
    ? (splits[selectedScenario.scenario.name] ?? "unassigned")
    : "unassigned";

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("benchmarks.title")}</h2>
          <p>{t("benchmarks.subtitle")}</p>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}

      {isMember ? (
        <div className="panel">
          <h3>{t("benchmarks.new")}</h3>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <label className="field">
              {t("benchmarks.name")}
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="field">
              {t("benchmarks.pickMap")}
              <select value={mapId} onChange={(event) => setMapId(event.target.value)}>
                {maps.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              {t("benchmarks.pickScenario")}
              <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
                {scenarios.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.scenario.name}
                  </option>
                ))}
              </select>
              {selectedScenario ? (
                <span style={{ marginTop: 6 }}>
                  <SplitBadge split={selectedSplit} />
                </span>
              ) : null}
            </label>
            <label className="field">
              {t("benchmarks.seedsLabel")}
              <input value={seedText} onChange={(event) => setSeedText(event.target.value)} />
            </label>
            <button
              className="primary"
              disabled={
                busy ||
                !mapId ||
                !scenarioId ||
                selected.length === 0 ||
                // PPO with no model would be refused by the server; the
                // button is disabled so nobody has to discover that.
                (selected.includes("astar+ppo") && !modelId)
              }
              title={
                busy
                  ? t("disabled.busy")
                  : !mapId
                    ? t("disabled.noMap")
                    : !scenarioId
                      ? t("disabled.noScenario")
                      : selected.length === 0
                        ? t("disabled.noAlgorithm")
                        : selected.includes("astar+ppo") && !modelId
                          ? t("disabled.noPpoModel")
                          : undefined
              }
              onClick={() => void create()}
            >
              {busy ? t("benchmarks.creating") : t("benchmarks.createDraft")}
            </button>
          </div>
          <ReplanningControls value={replanning} onChange={setReplanning} scope="benchmark" />
          {selectedSplit === "holdout" && selectedScenario ? (
            // Warn before the run, not after: the cost of consulting a
            // held-out scenario is paid the moment the result is seen.
            // It does not block — a held-out set exists to be used once —
            // but nobody gets to use it without being told what it is.
            <div className="notice" style={{ marginTop: 12 }}>
              {t("protocol.holdoutWarning", { scenario: selectedScenario.scenario.name })}
            </div>
          ) : null}
          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
              {t("benchmarks.stacksUnderTest")}
            </div>
            {algorithms.map((algorithm) => (
              <label key={algorithm.id} className="inline" style={{ marginRight: 16 }}>
                <input
                  type="checkbox"
                  checked={selected.includes(algorithm.id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, algorithm.id]
                        : current.filter((id) => id !== algorithm.id),
                    )
                  }
                />
                {algorithm.id}
                {algorithm.benchmarkable ? null : (
                  <span className="badge warn" title={algorithm.description}>
                    {t("algorithms.reference")}
                  </span>
                )}
              </label>
            ))}
          </div>

          {selected.includes("astar+ppo") ? (
            <div style={{ marginTop: 14 }}>
              {models.length === 0 ? (
                // Not a validation error: a person who has never
                // uploaded a model has done nothing wrong, and telling
                // them what PPO needs is more use than a red box.
                <div className="notice">
                  <strong>{t("benchmarks.noModels.title")}</strong>
                  <p style={{ margin: "6px 0 10px", fontSize: 12 }}>
                    {t("benchmarks.noModels.body")}
                  </p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <Link className="quick-action" href="/models">
                      <Icon name="plus" size={14} /> {t("benchmarks.uploadModel")}
                    </Link>
                    <button
                      type="button"
                      onClick={() =>
                        setSelected((current) => current.filter((id) => id !== "astar+ppo"))
                      }
                    >
                      {t("benchmarks.useDwaInstead")}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
                  <label className="field" style={{ flex: 1, minWidth: 220 }}>
                    {t("benchmarks.ppoModel")}
                    <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name} v{model.version}
                        </option>
                      ))}
                    </select>
                  </label>
                  {modelId ? (
                    <Link className="button-link" href={`/models/${modelId}`}>
                      {t("benchmarks.viewModel")}
                    </Link>
                  ) : null}
                  <Link className="button-link" href="/models">
                    {t("benchmarks.uploadModel")}
                  </Link>
                </div>
              )}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="panel">
        <h3>{t("benchmarks.list")}</h3>
        {benchmarks.length === 0 ? (
          <EmptyState
            icon="benchmark"
            title={t("benchmarks.empty.title")}
            body={t("benchmarks.empty.body")}
            actionHref="/agent"
            actionLabel={t("agent.askAssistant")}
            secondaryActionHref="/library"
            secondaryActionLabel={t("library.openLibrary")}
          />
        ) : (
          <div className="table-scroll wide">
          <table>
            <thead>
              <tr>
                <th>{t("common.name")}</th>
                <th>{t("benchmarks.stacks")}</th>
                <th>{t("common.seeds")}</th>
                <th>{t("common.status")}</th>
                <th>{t("benchmarks.createdBy")}</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((benchmark) => (
                <tr key={benchmark.id}>
                  <td>
                    <Link href={`/benchmarks/${benchmark.id}`}>{benchmark.spec.name}</Link>
                  </td>
                  <td>{benchmark.spec.algorithms.map((a) => a.id).join(", ")}</td>
                  <td>{benchmark.spec.seeds.join(", ")}</td>
                  <td>
                    <StateBadge state={benchmark.state} />
                  </td>
                  <td className="muted">
                    {benchmark.created_by}
                    {benchmark.is_owner ? (
                      <span className="badge ok" style={{ marginLeft: 6 }}>
                        {t("benchmarks.you")}
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </>
  );
}
