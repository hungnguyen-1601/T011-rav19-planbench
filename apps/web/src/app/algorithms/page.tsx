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
import Link from "next/link";
import { authFetch, useSession } from "@/lib/auth";
import type { AlgorithmInfo } from "@/lib/benchmarkTypes";

interface SchemaField {
  name: string;
  type: string;
  required: boolean;
  description: string;
  fallback: string;
}

export default function AlgorithmsPage() {
  const session = useSession();
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
      <h2>Algorithm registry</h2>
      <p className="muted">
        Every entry is a complete navigation stack — a global planner paired with a local planner.
        Benchmarks compare stacks against stacks; a global planner is never compared against a
        local one.
      </p>
      {!session ? (
        <div className="error-box">
          <Link href="/login">Sign in</Link> to view the registry.
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

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
                {algorithm.benchmarkable ? "benchmarkable" : "reference only"}
              </span>
              <span className="muted">{algorithm.kind}</span>
              {required.length > 0 ? (
                <span className="badge warn">needs {required.map((f) => f.name).join(", ")}</span>
              ) : null}
            </div>
            <p>{algorithm.description}</p>

            {!algorithm.benchmarkable ? (
              <div className="error-box">
                Reference adapter — runs the pipeline but must not be used to draw benchmark
                conclusions.
              </div>
            ) : null}
            {required.length > 0 ? (
              <p className="muted">
                Requires configuration a person has to supply, so the agent cannot propose this
                stack: it has no way to know which checkpoint is the right one, and inventing a
                path would be fabrication.
              </p>
            ) : null}

            <button
              type="button"
              className="secondary"
              onClick={() => setExpanded(expanded === algorithm.id ? null : algorithm.id)}
            >
              {expanded === algorithm.id ? "Hide" : "Show"} configuration ({fields.length})
            </button>

            {expanded === algorithm.id ? (
              fields.length === 0 ? (
                <p className="muted">No configurable parameters.</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Parameter</th>
                      <th>Type</th>
                      <th>Default</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fields.map((field) => (
                      <tr key={field.name}>
                        <td>
                          <code>{field.name}</code>
                          {field.required ? <span className="badge warn">required</span> : null}
                        </td>
                        <td className="muted">{field.type}</td>
                        <td className="muted">{field.fallback}</td>
                        <td>{field.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
