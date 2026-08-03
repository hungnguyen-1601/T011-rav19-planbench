"use client";

/** Stack registry (M4/M6): what can be benchmarked, and what it needs.
 *
 * Two distinctions this page exists to make visible:
 *
 * - `benchmarkable=false` marks a reference adapter. It exists to prove
 *   the pipeline runs end to end, not to produce a result anyone should
 *   quote, and a table that hid the flag would invite exactly that.
 * - a stack with required config (`astar+ppo` needs a trained
 *   checkpoint) cannot be run until a human supplies it — which is also
 *   why the agent is not allowed to propose one.
 */

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { authFetch, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";

interface SchemaField {
  name: string;
  type: string;
  required: boolean;
  description: string;
  fallback: string;
}

export default function AlgorithmsPage() {
  const { t } = useTranslation();
  // The registry is public: it describes what the software can do, not
  // anyone's data, and hiding it behind sign-in helped nobody.
  useSession();
  const [algorithms, setAlgorithms] = useState<AlgorithmInfo[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setAlgorithms(await authFetch<AlgorithmInfo[]>("/algorithms"));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("algorithms.title")}</h2>
          <p>{t("algorithms.pageHint")}</p>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {algorithms.length === 0 && !error ? <p className="muted">{t("common.loading")}</p> : null}
      {algorithms.length === 0 && error ? (
        <EmptyState
          icon="cpu"
          title={t("algorithms.empty.title")}
          body={t("algorithms.empty.body")}
        />
      ) : null}

      {algorithms.map((algorithm) => {
        const fields = schemaFields(algorithm.config_schema);
        const required = fields.filter((field) => field.required);
        return (
          <div className="panel" key={algorithm.id}>
            <div className="toolbar">
              <h3 style={{ margin: 0 }}>
                <code>{algorithm.id}</code>
              </h3>
              <span className={`badge ${algorithm.benchmarkable ? "ok" : "err"}`}>
                {algorithm.benchmarkable ? t("algorithms.benchmarkable") : t("algorithms.reference")}
              </span>
              <span className="muted">{algorithm.kind}</span>
              {required.length > 0 ? (
                <span className="badge warn">
                  {t("algorithms.needs", { fields: required.map((f) => f.name).join(", ") })}
                </span>
              ) : null}
            </div>
            <p>{algorithm.description}</p>

            {!algorithm.benchmarkable ? (
              <div className="error-box">{t("algorithms.referenceWarning")}</div>
            ) : null}
            {required.length > 0 ? (
              <p className="muted">{t("algorithms.requiredHint")}</p>
            ) : null}

            <button
              type="button"
              className="secondary"
              onClick={() => setExpanded(expanded === algorithm.id ? null : algorithm.id)}
            >
              {expanded === algorithm.id
                ? t("algorithms.hideConfig", { count: fields.length })
                : t("algorithms.showConfig", { count: fields.length })}
            </button>

            {expanded === algorithm.id ? (
              fields.length === 0 ? (
                <p className="muted">{t("algorithms.noParams")}</p>
              ) : (
                <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("algorithms.parameter")}</th>
                      <th>{t("algorithms.type")}</th>
                      <th>{t("algorithms.default")}</th>
                      <th>{t("algorithms.description")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fields.map((field) => (
                      <tr key={field.name}>
                        <td>
                          <code>{field.name}</code>
                          {field.required ? (
                            <span className="badge warn">{t("algorithms.required")}</span>
                          ) : null}
                        </td>
                        <td className="muted">{field.type}</td>
                        <td className="muted">{field.fallback}</td>
                        <td>{field.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              )
            ) : null}
          </div>
        );
      })}
    </>
  );
}

/** Flatten a Pydantic-generated JSON Schema into displayable rows. */
function schemaFields(schema: Record<string, unknown>): SchemaField[] {
  const properties = (schema?.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set((schema?.required as string[]) ?? []);
  return Object.entries(properties).map(([name, spec]) => ({
    name,
    type: typeName(spec),
    required: required.has(name),
    description: String(spec.description ?? ""),
    fallback: "default" in spec ? JSON.stringify(spec.default) : "—",
  }));
}

function typeName(spec: Record<string, unknown>): string {
  if (typeof spec.type === "string") return spec.type;
  if (Array.isArray(spec.anyOf)) {
    return (spec.anyOf as Record<string, unknown>[])
      .map((option) => (typeof option.type === "string" ? option.type : "?"))
      .join(" | ");
  }
  return "object";
}
