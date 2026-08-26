"use client";

/** Choose a candidate one layer at a time: global, then local, then config.
 *
 * **Why not one dropdown of whole stacks.** With five registry entries a
 * single `astar+dwa` list was readable. Two global planners and four
 * controllers is eight; the list grows as the *product* of the layers
 * while the thing being chosen is one item from each. A picker that
 * grows quadratically to express a choice that is linear is the wrong
 * shape, and it is wrong before anybody notices it is long.
 *
 * **Why the lists cascade rather than being independent.** The registry
 * is not a full cross product: `rrtstar+ppo` does not exist. Two free
 * dropdowns would let somebody build it and find out from a server
 * refusal. So the controllers offered are the ones paired with the
 * chosen global planner, and the configurations are the ones belonging
 * to the chosen controller.
 *
 * **The stack id is looked up, never assembled.** Every entry today is
 * spelled `<global>+<local>`, and building the id from the two halves
 * would work — until an entry is not. `AlgorithmInfo.global_planner` and
 * `.local_controller` are the facts; the id is a display convention
 * (registry.py says so). So the pair selects the entry and the entry
 * supplies its own id.
 */

import { Hint } from "@/components/Hint";
import { useTranslation } from "@/lib/i18n";
import type { LocalControllerConfig } from "@/lib/decisions";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";

export interface CandidateSelection {
  /** The registry stack id, e.g. `astar+dwa`. What the API takes. */
  stack: string;
  local_config: string;
}

/** The stacks a comparison may use: reference implementations excluded.
 *
 * One exists to validate the pipeline and must never support a
 * conclusion (decision D12), so offering it here would put it one click
 * from one.
 */
export function usableStacks(stacks: AlgorithmInfo[]): AlgorithmInfo[] {
  return stacks.filter((entry) => entry.benchmarkable);
}

export function globalPlanners(stacks: AlgorithmInfo[]): string[] {
  return [...new Set(usableStacks(stacks).map((entry) => entry.global_planner))].sort();
}

/** Controllers the registry actually pairs with this global planner. */
export function controllersFor(stacks: AlgorithmInfo[], globalPlanner: string): string[] {
  return [
    ...new Set(
      usableStacks(stacks)
        .filter((entry) => entry.global_planner === globalPlanner)
        .map((entry) => entry.local_controller),
    ),
  ].sort();
}

/** The registry entry for a pair, or `undefined` if there is none.
 *
 * Looked up rather than assembled — see the module docstring.
 */
export function stackFor(
  stacks: AlgorithmInfo[],
  globalPlanner: string,
  controller: string,
): AlgorithmInfo | undefined {
  return usableStacks(stacks).find(
    (entry) => entry.global_planner === globalPlanner && entry.local_controller === controller,
  );
}

export function configsFor(
  configs: LocalControllerConfig[],
  controller: string,
): LocalControllerConfig[] {
  return configs.filter((config) => config.controller === controller);
}

export function CandidatePicker({
  label,
  value,
  onChange,
  stacks,
  configs,
  disabled = false,
  detailed = false,
}: {
  label: string;
  value: CandidateSelection;
  onChange: (next: CandidateSelection) => void;
  stacks: AlgorithmInfo[];
  configs: LocalControllerConfig[];
  disabled?: boolean;
  /** Show each layer as a labelled field on engineering-console surfaces. */
  detailed?: boolean;
}) {
  const { t } = useTranslation();
  const selected = usableStacks(stacks).find((entry) => entry.id === value.stack);
  const chosenGlobal = selected?.global_planner ?? "";
  const chosenLocal = selected?.local_controller ?? "";

  const globals = globalPlanners(stacks);
  const controllers = controllersFor(stacks, chosenGlobal);
  const available = configsFor(configs, chosenLocal);

  /** Move to a pair, keeping the configuration when it still applies.
   *
   * Switching controller drops the configuration rather than carrying
   * it: `dwa_coarse` on a PPO policy is a name from another vocabulary,
   * and the server would refuse it after the click. Switching global
   * planner keeps both when the same controller exists there, because
   * "the same controller under a different planner" is exactly the
   * comparison this platform is for.
   */
  const select = (nextGlobal: string, nextLocal: string) => {
    const controllerList = controllersFor(stacks, nextGlobal);
    const controller = controllerList.includes(nextLocal) ? nextLocal : (controllerList[0] ?? "");
    const entry = stackFor(stacks, nextGlobal, controller);
    const forController = configsFor(configs, controller);
    const config = forController.some((one) => one.name === value.local_config)
      ? value.local_config
      : (forController[0]?.name ?? "");
    onChange({ stack: entry?.id ?? "", local_config: config });
  };

  // Free text while the lists are still loading or after a failed
  // request. Losing the ability to start a comparison because a
  // convenience list did not arrive would be worse than the two text
  // boxes this replaced.
  if (globals.length === 0) {
    return (
      <label className="field">
        <span>{label}</span>
        <input
          value={value.stack}
          disabled={disabled}
          onChange={(event) => onChange({ ...value, stack: event.target.value })}
          placeholder="astar+dwa"
        />
        <input
          value={value.local_config}
          disabled={disabled}
          onChange={(event) => onChange({ ...value, local_config: event.target.value })}
          placeholder="dwa_coarse"
        />
      </label>
    );
  }

  return (
    <div className={`field${detailed ? " candidate-picker--detailed" : ""}`}>
      <span className="candidate-picker-label">{label}</span>
      <label className="candidate-picker-field">
      {detailed ? (
        <span>
          {t("candidates.pick.global")}
          <Hint text={t("bench.help.global")} label={t("candidates.pick.global")} />
        </span>
      ) : null}
      <select
        value={chosenGlobal}
        disabled={disabled}
        aria-label={t("candidates.pick.global")}
        onChange={(event) => select(event.target.value, chosenLocal)}
      >
        <option value="">{t("candidates.pick.global")}</option>
        {globals.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      </label>
      <label className="candidate-picker-field">
      {detailed ? (
        <span>
          {t("candidates.pick.local")}
          <Hint text={t("bench.help.local")} label={t("candidates.pick.local")} />
        </span>
      ) : null}
      <select
        value={chosenLocal}
        disabled={disabled || controllers.length === 0}
        aria-label={t("candidates.pick.local")}
        onChange={(event) => select(chosenGlobal, event.target.value)}
      >
        <option value="">{t("candidates.pick.local")}</option>
        {controllers.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      </label>
      <label className="candidate-picker-field">
      {detailed ? <span>{t("candidates.pick.config")}</span> : null}
      <select
        value={value.local_config}
        disabled={disabled || available.length === 0}
        aria-label={t("candidates.pick.config")}
        onChange={(event) => onChange({ ...value, local_config: event.target.value })}
      >
        <option value="">{t("candidates.pick.config")}</option>
        {available.map((config) => (
          <option key={config.name} value={config.name}>
            {config.name}
          </option>
        ))}
      </select>
      </label>
      {/* A controller with no named configuration is not an error — it
          is one nobody has written configurations for yet, and saying so
          is more use than an empty dropdown. */}
      {chosenLocal && available.length === 0 ? (
        <span className="muted">{t("candidates.pick.noConfigs")}</span>
      ) : null}
    </div>
  );
}
