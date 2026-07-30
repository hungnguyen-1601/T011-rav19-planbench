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

  const isOperator = session?.role === "operator" || session?.role === "admin";

  return (
    <>
      <h2>Agent console</h2>
      {!session ? (
        <div className="error-box">
          <Link href="/login">Sign in</Link> to use the agent.
        </div>
      ) : null}
      {error ? <div className="error-box">{error}</div> : null}

      {capabilities ? <Capabilities capabilities={capabilities} /> : null}

      <div className="panel">
        <h3>Ask about recorded results</h3>
        <p className="muted">
          The agent answers from tool results and indexed documentation. If the tools return nothing
          relevant it says so rather than answering from memory.
        </p>
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
              placeholder="Which scenarios exist? / Summarise benchmark <id>"
              onChange={(event) => setQuestion(event.target.value)}
              disabled={!session}
            />
            <button type="submit" disabled={!session || asking || !question.trim()}>
              {asking ? "Thinking…" : "Ask"}
            </button>
          </div>
        </form>

        {exchanges.map((exchange, index) => (
          <div className="transcript" key={index}>
            <p className="transcript-q">{exchange.question}</p>
            <pre className="transcript-a">{exchange.response.turn.text}</pre>
            <p className="muted">
              {exchange.response.provider} ({exchange.response.model})
              {exchange.response.deterministic ? " — keyword-matched, not model-written" : ""}
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
        <h3>Turn a request into a benchmark</h3>
        <p className="muted">
          The agent may draft and submit a benchmark. It cannot approve or run one that a reviewer
          has not approved.
        </p>
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
              placeholder="Benchmark DWA on the doorway scenario with seeds 1 2"
              onChange={(event) => setMission(event.target.value)}
              disabled={!isOperator}
            />
            <label className="inline">
              <input
                type="checkbox"
                checked={submitForApproval}
                onChange={(event) => setSubmitForApproval(event.target.checked)}
              />
              submit for approval
            </label>
            <button type="submit" disabled={!isOperator || parsing || !mission.trim()}>
              {parsing ? "Parsing…" : "Parse mission"}
            </button>
          </div>
        </form>
        {session && !isOperator ? (
          <p className="muted">Creating benchmarks is an operator action.</p>
        ) : null}
        {missionResult ? <MissionOutcome result={missionResult} /> : null}
      </div>

      <div className="panel">
        <h3>Evidence and report</h3>
        <p className="muted">
          Evidence comes straight from storage. Every citation in a generated report is checked
          against it — an invented id discards the whole report.
        </p>
        <div className="toolbar">
          <input
            value={benchmarkId}
            placeholder="benchmark id"
            onChange={(event) => setBenchmarkId(event.target.value.trim())}
          />
          <input
            style={{ flex: 1, minWidth: 240 }}
            value={reportQuestion}
            placeholder="question (optional)"
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
            Collect evidence
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
            Generate report
          </button>
        </div>

        {evidence ? (
          <>
            <h4>{evidence.items.length} evidence items</h4>
            <table>
              <thead>
                <tr>
                  <th>Citation</th>
                  <th>Statement</th>
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
          </>
        ) : null}

        {report ? <ReportView report={report} /> : null}
      </div>
    </>
  );
}

function Capabilities({ capabilities }: { capabilities: AgentCapabilities }) {
  const configured = capabilities.providers.filter((provider) => provider.ready);
  return (
    <div className="panel">
      <h3>Provider</h3>
      <div className="toolbar">
        <span className={`badge ${capabilities.deterministic ? "warn" : "ok"}`}>
          {capabilities.provider}
        </span>
        <code>{capabilities.model}</code>
        <span className="muted">{capabilities.knowledge_documents} documents indexed</span>
      </div>
      {capabilities.deterministic ? (
        <div className="error-box">
          Running the offline deterministic provider: answers are keyword-matched, not written by a
          model. Configure a provider key to change that — the readiness table below says what each
          one still needs.
        </div>
      ) : null}

      <h4>Providers</h4>
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Ready</th>
            <th>Key variable</th>
            <th>Missing</th>
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
                  {provider.ready ? "yes" : "no"}
                </span>
              </td>
              <td className="muted">
                {provider.api_key_env ? <code>{provider.api_key_env}</code> : "none needed"}
              </td>
              <td className="muted">{provider.missing || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {configured.length === 0 ? (
        <p className="muted">
          No external provider configured — see <code>.env.example</code>.
        </p>
      ) : null}

      <h4>Tools ({capabilities.tools.length})</h4>
      <p>
        {capabilities.tools.map((tool) => (
          <code key={tool} className="chip">
            {tool}
          </code>
        ))}
      </p>
      <h4>Cannot do</h4>
      <p className="muted">
        Enforced by absence, not by prompt — there is no tool and no API path for any of these:
      </p>
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
  if (result.refusal) {
    return (
      <div className="finding finding-primary">
        <div className="finding-head">
          <strong>Refused</strong>
          <span className="badge err">nothing was created</span>
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
        <strong>Draft accepted</strong>
        {result.benchmark ? (
          <span className="badge warn">{result.benchmark.state}</span>
        ) : (
          <span className="badge muted-badge">not submitted</span>
        )}
      </div>
      {result.draft ? (
        <table>
          <tbody>
            <tr>
              <th>Scenario</th>
              <td>
                <code>{result.draft.scenario}</code>
              </td>
            </tr>
            <tr>
              <th>Stacks</th>
              <td>
                {result.draft.algorithms.map((algorithm) => (
                  <code key={algorithm} className="chip">
                    {algorithm}
                  </code>
                ))}
              </td>
            </tr>
            <tr>
              <th>Seeds</th>
              <td className="muted">[{result.draft.seeds.join(", ")}]</td>
            </tr>
          </tbody>
        </table>
      ) : null}
      <p className="muted">{result.next_step}</p>
      {result.benchmark ? (
        <p>
          <Link href={`/benchmarks/${result.benchmark.id}`}>
            Open benchmark <code>{result.benchmark.id}</code>
          </Link>{" "}
          — a reviewer approves it there.
        </p>
      ) : null}
      <details>
        <summary className="muted">Session transcript ({result.session.events.length})</summary>
        <table>
          <thead>
            <tr>
              <th>State</th>
              <th>Action</th>
              <th>Detail</th>
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
      </details>
    </div>
  );
}

function ReportView({ report }: { report: GeneratedReport }) {
  return (
    <div className={`finding${report.refused ? " finding-primary" : ""}`}>
      <div className="finding-head">
        <strong>{report.refused ? "Refused" : "Report"}</strong>
        {report.provisional ? (
          <span className="badge warn">provisional</span>
        ) : (
          <span className="badge ok">accepted results</span>
        )}
        <span className="muted">
          {report.citations.length} citations over {report.evidence_count} evidence items
        </span>
      </div>
      {report.refused ? <p className="muted">Reason: {report.refusal_reason}</p> : null}
      <pre className="transcript-a">{report.text}</pre>
      <p className="muted">
        {report.provider} ({report.model})
        {report.deterministic ? " — keyword-matched, not model-written" : ""}
      </p>
    </div>
  );
}
