"use client";

/** Agent console (M8).
 *
 * Three things this page is careful about, because getting them wrong
 * would undo the guarantees the backend enforces:
 *
 * 1. It always shows which provider answered. `deterministic: true`
 *    means the reply was keyword-matched offline, not written by a
 *    model — a reader must never have to guess which they are looking at.
 * 2. A refused mission is rendered as a refusal with its reasons, not as
 *    an error and not as an empty result.
 * 3. There is no approve button here. The agent cannot approve its own
 *    benchmark, and neither can this page: approval lives on the
 *    benchmark detail page, for a reviewer.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authFetch, useSession } from "@/lib/auth";
import { StateBadge } from "@/components/StateBadge";
import { useTranslation } from "@/lib/i18n";
import type {
  AgentCapabilities,
  ChatResponse,
  EvidenceBundle,
  GeneratedReport,
  MissionResponse,
} from "@/lib/platformTypes";

interface Exchange {
  question: string;
  response: ChatResponse;
}

export default function AgentPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [capabilities, setCapabilities] = useState<AgentCapabilities | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [asking, setAsking] = useState(false);

  const [mission, setMission] = useState("");
  const [submitForApproval, setSubmitForApproval] = useState(true);
  const [missionResult, setMissionResult] = useState<MissionResponse | null>(null);
  const [parsing, setParsing] = useState(false);

  const [benchmarkId, setBenchmarkId] = useState("");
  const [evidence, setEvidence] = useState<EvidenceBundle | null>(null);
  const [report, setReport] = useState<GeneratedReport | null>(null);
  const [reportQuestion, setReportQuestion] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setCapabilities(await authFetch<AgentCapabilities>("/agent/capabilities"));
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  const guard = useCallback(async <T,>(work: () => Promise<T>, done: (value: T) => void) => {
    setError(null);
    try {
      done(await work());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  // Every signed-in member can drive the agent; what it produces is a
  // draft they own, and the gates on running it are unchanged.
  const isMember = Boolean(session);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("agent.title")}</h2>
          <p>{t("agent.subtitle")}</p>
        </div>
      </div>
      {!session ? (
        <div className="notice">
          <Link href="/login">{t("topbar.signIn")}</Link> — {t("common.signInTo")}
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      {capabilities ? <Capabilities capabilities={capabilities} /> : null}

      <div className="panel">
        <h3>{t("agent.askTitle")}</h3>
        <p className="muted">{t("agent.askHint")}</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!question.trim()) return;
            setAsking(true);
            const asked = question;
            void guard(
              () =>
                authFetch<ChatResponse>("/agent/chat", {
                  method: "POST",
                  body: JSON.stringify({ message: asked }),
                }),
              (response) => {
                setExchanges((current) => [...current, { question: asked, response }]);
                setQuestion("");
              },
            ).finally(() => setAsking(false));
          }}
        >
          <div className="toolbar">
            <input
              style={{ flex: 1, minWidth: 320 }}
              value={question}
              placeholder={t("agent.askPlaceholder")}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={!session}
            />
            <button type="submit" disabled={!session || asking || !question.trim()}>
              {asking ? t("agent.thinking") : t("agent.ask")}
            </button>
          </div>
        </form>

        {exchanges.map((exchange, index) => (
          <div className="transcript" key={index}>
            <p className="transcript-q">{exchange.question}</p>
            <pre className="transcript-a">{exchange.response.turn.text}</pre>
            <p className="muted">
              {exchange.response.provider} ({exchange.response.model})
              {exchange.response.deterministic ? ` — ${t("agent.keywordMatched")}` : ""}
              {exchange.response.turn.tools_used.length > 0
                ? ` · tools: ${exchange.response.turn.tools_used.join(", ")}`
                : ""}
              {exchange.response.turn.iterations > 1
                ? ` · ${exchange.response.turn.iterations} iterations`
                : ""}
            </p>
            {exchange.response.turn.truncated ? (
              <div className="error-box">
                Stopped after the tool-call budget was exhausted without a final answer. Nothing is
                asserted.
              </div>
            ) : null}
            {exchange.response.turn.tool_errors.map((toolError, errorIndex) => (
              <p className="muted" key={errorIndex}>
                tool error — {toolError}
              </p>
            ))}
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>{t("agent.missionTitle")}</h3>
        <p className="muted">{t("agent.missionHint")}</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!mission.trim()) return;
            setParsing(true);
            void guard(
              () =>
                authFetch<MissionResponse>("/agent/missions", {
                  method: "POST",
                  body: JSON.stringify({ mission, submit: submitForApproval }),
                }),
              (result) => {
                setMissionResult(result);
                if (result.benchmark) setBenchmarkId(result.benchmark.id);
              },
            ).finally(() => setParsing(false));
          }}
        >
          <div className="toolbar">
            <input
              style={{ flex: 1, minWidth: 320 }}
              value={mission}
              placeholder={t("agent.missionPlaceholder")}
              onChange={(event) => setMission(event.target.value)}
              disabled={!isMember}
            />
            <label className="inline">
              <input
                type="checkbox"
                checked={submitForApproval}
                onChange={(event) => setSubmitForApproval(event.target.checked)}
              />
              {t("agent.submitForApproval")}
            </label>
            <button type="submit" disabled={!isMember || parsing || !mission.trim()}>
              {parsing ? t("agent.parsing") : t("agent.parse")}
            </button>
          </div>
        </form>
        {missionResult ? <MissionOutcome result={missionResult} /> : null}
      </div>

      <div className="panel">
        <h3>{t("agent.evidenceTitle")}</h3>
        <p className="muted">{t("agent.evidenceHint")}</p>
        <div className="toolbar">
          <input
            value={benchmarkId}
            placeholder={t("agent.benchmarkId")}
            onChange={(event) => setBenchmarkId(event.target.value.trim())}
          />
          <input
            style={{ flex: 1, minWidth: 240 }}
            value={reportQuestion}
            placeholder={t("agent.question", { optional: t("common.optional") })}
            onChange={(event) => setReportQuestion(event.target.value)}
          />
          <button
            type="button"
            className="secondary"
            disabled={!benchmarkId || working}
            onClick={() => {
              setWorking(true);
              void guard(
                () =>
                  authFetch<EvidenceBundle>(
                    `/agent/benchmarks/${benchmarkId}/evidence?question=${encodeURIComponent(reportQuestion)}`,
                  ),
                setEvidence,
              ).finally(() => setWorking(false));
            }}
          >
            {t("agent.collectEvidence")}
          </button>
          <button
            type="button"
            disabled={!benchmarkId || working}
            onClick={() => {
              setWorking(true);
              void guard(
                () =>
                  authFetch<GeneratedReport>(`/agent/benchmarks/${benchmarkId}/report`, {
                    method: "POST",
                    body: JSON.stringify({ question: reportQuestion }),
                  }),
                setReport,
              ).finally(() => setWorking(false));
            }}
          >
            {t("agent.generateReport")}
          </button>
        </div>

        {evidence ? (
          <>
            <h4>{t("agent.evidenceItems", { count: evidence.items.length })}</h4>
            <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("agent.citation")}</th>
                  <th>{t("agent.statement")}</th>
                </tr>
              </thead>
              <tbody>
                {evidence.items.map((item, index) => (
                  <tr key={index}>
                    <td>
                      <code>
                        {item.citation.kind}:{item.citation.locator}
                      </code>
                    </td>
                    <td>{item.statement}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        ) : null}

        {report ? <ReportView report={report} /> : null}
      </div>
    </>
  );
}

function Capabilities({ capabilities }: { capabilities: AgentCapabilities }) {
  const { t } = useTranslation();
  const configured = capabilities.providers.filter((provider) => provider.ready);
  return (
    <div className="panel">
      <h3>{t("agent.provider")}</h3>
      <div className="toolbar">
        <span className={`badge ${capabilities.deterministic ? "warn" : "ok"}`}>
          {capabilities.provider}
        </span>
        <code>{capabilities.model}</code>
        <span className="muted">
          {t("agent.documentsIndexed", { count: capabilities.knowledge_documents })}
        </span>
      </div>
      {capabilities.deterministic ? (
        <div className="error-box">{t("agent.deterministicWarning")}</div>
      ) : null}

      <h4>{t("agent.providers")}</h4>
      <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{t("agent.provider")}</th>
            <th>{t("agent.ready")}</th>
            <th>{t("agent.keyVariable")}</th>
            <th>{t("agent.missing")}</th>
          </tr>
        </thead>
        <tbody>
          {capabilities.providers.map((provider) => (
            <tr key={provider.name}>
              <td>
                <code>{provider.name}</code>
              </td>
              <td>
                <span className={`badge ${provider.ready ? "ok" : "muted-badge"}`}>
                  {provider.ready ? t("common.yes") : t("common.no")}
                </span>
              </td>
              <td className="muted">
                {provider.api_key_env ? (
                  <code>{provider.api_key_env}</code>
                ) : (
                  t("agent.noneNeeded")
                )}
              </td>
              <td className="muted">{provider.missing || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {configured.length === 0 ? <p className="muted">{t("agent.noProvider")}</p> : null}

      <h4>{t("agent.tools", { count: capabilities.tools.length })}</h4>
      <p>
        {capabilities.tools.map((tool) => (
          <code key={tool} className="chip">
            {tool}
          </code>
        ))}
      </p>
      <h4>{t("agent.cannotDo")}</h4>
      <p className="muted">{t("agent.forbiddenHint")}</p>
      <p>
        {capabilities.forbidden.map((item) => (
          <code key={item} className="chip chip-off">
            {item}
          </code>
        ))}
      </p>
    </div>
  );
}

function MissionOutcome({ result }: { result: MissionResponse }) {
  const { t } = useTranslation();
  if (result.refusal) {
    return (
      <div className="finding finding-primary">
        <div className="finding-head">
          <strong>{t("agent.refused")}</strong>
          <span className="badge err">{t("agent.nothingCreated")}</span>
        </div>
        <p>{result.refusal.reason}</p>
        {result.refusal.errors.length > 0 ? (
          <ul>
            {result.refusal.errors.map((detail, index) => (
              <li key={index} className="muted">
                {detail}
              </li>
            ))}
          </ul>
        ) : null}
        <p className="muted">{result.next_step}</p>
      </div>
    );
  }
  return (
    <div className="finding">
      <div className="finding-head">
        <strong>{t("agent.draftAccepted")}</strong>
        {result.benchmark ? (
          <StateBadge state={result.benchmark.state} />
        ) : (
          <span className="badge muted-badge">{t("agent.notSubmitted")}</span>
        )}
      </div>
      {result.draft ? (
        <table>
          <tbody>
            <tr>
              <th>{t("common.scenario")}</th>
              <td>
                <code>{result.draft.scenario}</code>
              </td>
            </tr>
            <tr>
              <th>{t("benchmarks.stacks")}</th>
              <td>
                {result.draft.algorithms.map((algorithm) => (
                  <code key={algorithm} className="chip">
                    {algorithm}
                  </code>
                ))}
              </td>
            </tr>
            <tr>
              <th>{t("common.seeds")}</th>
              <td className="muted">[{result.draft.seeds.join(", ")}]</td>
            </tr>
          </tbody>
        </table>
      ) : null}
      <p className="muted">{result.next_step}</p>
      {result.benchmark ? (
        <p>
          <Link href={`/benchmarks/${result.benchmark.id}`}>
            {t("agent.openBenchmark")} <code>{result.benchmark.id}</code>
          </Link>{" "}
          {t("agent.runItThere")}
        </p>
      ) : null}
      <details>
        <summary className="muted">
          {t("agent.transcript", { count: result.session.events.length })}
        </summary>
        <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{t("agent.state")}</th>
              <th>{t("detail.action")}</th>
              <th>{t("agent.detail")}</th>
            </tr>
          </thead>
          <tbody>
            {result.session.events.map((event, index) => (
              <tr key={index}>
                <td>
                  <code>{event.state}</code>
                </td>
                <td>{event.action}</td>
                <td className="muted">{event.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </details>
    </div>
  );
}

function ReportView({ report }: { report: GeneratedReport }) {
  const { t } = useTranslation();
  return (
    <div className={`finding${report.refused ? " finding-primary" : ""}`}>
      <div className="finding-head">
        <strong>{report.refused ? t("agent.refused") : t("agent.reportTitle")}</strong>
        {report.provisional ? (
          <span className="badge warn">{t("agent.provisional")}</span>
        ) : (
          <span className="badge ok">{t("agent.acceptedResults")}</span>
        )}
        <span className="muted">
          {t("agent.citationCount", {
            citations: report.citations.length,
            evidence: report.evidence_count,
          })}
        </span>
      </div>
      {report.refused ? (
        <p className="muted">{t("agent.reason", { reason: report.refusal_reason })}</p>
      ) : null}
      <pre className="transcript-a">{report.text}</pre>
      <p className="muted">
        {report.provider} ({report.model})
        {report.deterministic ? ` — ${t("agent.keywordMatched")}` : ""}
      </p>
    </div>
  );
}
