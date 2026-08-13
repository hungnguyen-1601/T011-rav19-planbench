"use client";

/** Candidates — what a comparison chooses between.
 *
 * **The gap this fills.** Until now the only way to name a candidate was
 * to type `astar+dwa` and `dwa_coarse` into two free-text boxes on the
 * launch panel: no list of what exists, no note that one of the stacks
 * is a reference implementation nobody should compare against, and no
 * sign of a typo until the server refused it.
 *
 * **Three tables, because a candidate is made of two things and is
 * neither of them.** A registry stack is an algorithm; a local-controller
 * config is a set of sampling numbers; a *candidate* is one of each,
 * identified by the hash of the pair. Showing only the last would hide
 * what there was to choose from; showing only the first two would hide
 * that the choice has an identity every trace keys on (HĐ-1.3).
 */

import { useCallback, useEffect, useState } from "react";

import { CandidatePicker, usableStacks, type CandidateSelection } from "@/components/CandidatePicker";
import { EmptyState } from "@/components/EmptyState";
import { authFetch, useSession } from "@/lib/auth";
import {
  listCandidates,
  listLocalControllers,
  localConfigOf,
  registerCandidate,
  type LocalControllerConfig,
  type RegisteredCandidate,
} from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";

export default function CandidatesPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [stacks, setStacks] = useState<AlgorithmInfo[]>([]);
  const [configs, setConfigs] = useState<LocalControllerConfig[]>([]);
  const [candidates, setCandidates] = useState<RegisteredCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [registry, named, registered] = await Promise.all([
        authFetch<AlgorithmInfo[]>("/algorithms"),
        listLocalControllers(),
        listCandidates(),
      ]);
      setStacks(registry);
      setConfigs(named);
      setCandidates(registered);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section>
      <div className="page-head">
        <h1>{t("candidates.title")}</h1>
        <p className="muted">{t("candidates.subtitle")}</p>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {loading ? <p className="muted">{t("common.loading")}</p> : null}

      <RegisterPanel
        stacks={stacks}
        configs={configs}
        enabled={session !== null}
        onDone={refresh}
      />
      <RegisteredTable candidates={candidates} configs={configs} />
      <StackTable stacks={stacks} />
      <ConfigTable configs={configs} />
    </section>
  );
}

/** Register a candidate: pick a stack, pick a config, that is all.
 *
 * **There is no id field, and its absence is the design.** HĐ-1.3 makes
 * `candidate_id` a hash over the stack, its parameters and its code
 * version, so the server computes it. A caller-supplied id would let two
 * different configurations share an identity that every trace, pairing
 * and ΔU keys on.
 */
function RegisterPanel({
  stacks,
  configs,
  enabled,
  onDone,
}: {
  stacks: AlgorithmInfo[];
  configs: LocalControllerConfig[];
  enabled: boolean;
  onDone: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [choice, setChoice] = useState<CandidateSelection>({ stack: "", local_config: "" });
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [registered, setRegistered] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setFailed(null);
    setRegistered(null);
    try {
      const made = await registerCandidate(choice);
      setRegistered(made.candidate_id);
      await onDone();
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  if (!enabled) {
    return (
      <div className="panel">
        <div className="panel-head">
          <h3>{t("candidates.register.title")}</h3>
        </div>
        <p className="muted">{t("candidates.register.signedOut")}</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("candidates.register.title")}</h3>
      </div>

      {failed ? <div className="error-box">{failed}</div> : null}
      {registered ? (
        <div className="notice">
          {t("candidates.register.done")} <code>{registered}</code>
        </div>
      ) : null}

      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        <CandidatePicker
          label={t("candidates.register.candidate")}
          value={choice}
          onChange={setChoice}
          stacks={stacks}
          configs={configs}
          disabled={busy}
        />
        <button
          type="button"
          className="primary"
          disabled={busy || !choice.stack || !choice.local_config}
          onClick={() => void submit()}
        >
          {t("candidates.register.submit")}
        </button>
      </div>

      <p className="muted" style={{ marginTop: 8 }}>
        {t("candidates.register.note")}
      </p>
    </div>
  );
}

function RegisteredTable({
  candidates,
  configs,
}: {
  candidates: RegisteredCandidate[];
  configs: LocalControllerConfig[];
}) {
  const { t } = useTranslation();
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("candidates.registered.title")}</h3>
      </div>
      {candidates.length === 0 ? (
        <EmptyState
          icon="cpu"
          title={t("candidates.registered.empty.title")}
          body={t("candidates.registered.empty.body")}
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("candidates.registered.id")}</th>
                <th>{t("candidates.registered.stack")}</th>
                <th>{t("candidates.registered.config")}</th>
                <th>{t("candidates.registered.tuning")}</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr key={candidate.candidate_id}>
                  <td>
                    <code>{candidate.candidate_id}</code>
                  </td>
                  <td>{candidate.stack_label}</td>
                  <td className="muted">{localConfigOf(candidate, configs) ?? "—"}</td>
                  <td>
                    {/* Null is not zero. The objectives layer charges an
                        undeclared candidate for the silence rather than
                        substituting nothing (HĐ-1.6), so "not declared"
                        has to reach the screen as its own answer. */}
                    {candidate.tuning ? (
                      <span className="badge ok">{t("candidates.registered.declared")}</span>
                    ) : (
                      <span className="badge warn" title={t("candidates.registered.silenceNote")}>
                        {t("candidates.registered.undeclared")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ marginTop: 8 }}>
        {t("candidates.registered.idNote")}
      </p>
    </div>
  );
}

function StackTable({ stacks }: { stacks: AlgorithmInfo[] }) {
  const { t } = useTranslation();
  if (stacks.length === 0) return null;
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("candidates.stacks.title")}</h3>
      </div>
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("candidates.stacks.id")}</th>
              <th>{t("candidates.stacks.globalPlanner")}</th>
              <th>{t("candidates.stacks.usable")}</th>
              <th>{t("candidates.stacks.description")}</th>
            </tr>
          </thead>
          <tbody>
            {stacks.map((stack) => (
              <tr key={stack.id}>
                <td>
                  <strong>{stack.id}</strong>
                </td>
                <td className="muted">
                  {stack.global_planner} + {stack.local_controller}
                  {/* A sampling planner needs more seeds to say anything,
                      and a table that hid this would invite comparing one
                      lucky tree against A*. */}
                  {stack.stochastic_global_planner ? (
                    <>
                      <br />
                      <span className="badge warn" title={t("candidates.stacks.stochasticNote")}>
                        {t("candidates.stacks.stochastic")}
                      </span>
                    </>
                  ) : null}
                </td>
                <td>
                  {stack.benchmarkable ? (
                    <span className="badge ok">{t("candidates.stacks.benchmarkable")}</span>
                  ) : (
                    <span className="badge muted-badge" title={t("candidates.stacks.referenceNote")}>
                      {t("candidates.stacks.reference")}
                    </span>
                  )}
                </td>
                <td className="muted">{stack.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConfigTable({ configs }: { configs: LocalControllerConfig[] }) {
  const { t } = useTranslation();
  if (configs.length === 0) return null;
  const columns = [...new Set(configs.flatMap((config) => Object.keys(config.params)))];
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("candidates.configs.title")}</h3>
      </div>
      {/* The numbers, not just the names. `dwa_coarse` and `dwa_default`
          differ by 7×15 samples against 20×40, and that difference is the
          entire reason a sampling choice is a candidate rather than a
          constant inside whichever script ran. */}
      <p className="muted">{t("candidates.configs.note")}</p>
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("candidates.configs.name")}</th>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.name}>
                <td>
                  <strong>{config.name}</strong>
                </td>
                {columns.map((column) => (
                  <td key={column}>{config.params[column] ?? "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
