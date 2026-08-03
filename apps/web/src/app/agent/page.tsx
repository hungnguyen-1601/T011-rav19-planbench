"use client";

/** The assistant: an ordinary chat.
 *
 * What this replaced: three separate forms ("Ask about results", "Turn a
 * request into a benchmark", "Evidence and report"), a provider
 * readiness table, a list of internal tool names, a list of forbidden
 * capabilities, and instructions about `pip install`. All of it was true
 * and none of it belonged in front of someone who wants to test a robot.
 * The diagnostics moved to /system; what is left is a conversation.
 *
 * Two behaviours are load-bearing and visible here:
 *
 * - A proposal is shown as a **card with a button**. Nothing is created
 *   until that button is pressed, and pressing it creates a *draft*.
 * - There is no "run" anywhere on this page. Running a benchmark is a
 *   deliberate act on the benchmark page, by a person.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/Icon";
import { useSession } from "@/lib/auth";
import {
  QUICK_PROMPTS,
  confirmDraft,
  isMessageKey,
  sendMessage,
  startConversation,
  type BenchmarkProposal,
  type ChatMessage,
  type ResultCard,
} from "@/lib/chat";
import { useTranslation } from "@/lib/i18n";

export default function AssistantPage() {
  const { t, locale } = useTranslation();
  const session = useSession();
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState("");
  const [error, setError] = useState<string | null>(null);
  const endOfThread = useRef<HTMLDivElement>(null);
  // Lets Stop actually stop: the in-flight reply is ignored on abort.
  const inFlight = useRef<AbortController | null>(null);

  const begin = useCallback(async () => {
    try {
      const conversation = await startConversation(locale);
      setConversationId(conversation.id);
      setMessages([]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [locale]);

  const userId = session?.user.id ?? "";
  useEffect(() => {
    if (!userId) return;
    void begin();
  }, [userId, begin]);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  const ask = async (text: string) => {
    const message = text.trim();
    if (!message || !conversationId || sending) return;

    const controller = new AbortController();
    inFlight.current = controller;
    setSending(true);
    setError(null);
    // Show the question immediately: waiting for a round trip to see
    // your own words makes the page feel broken.
    setMessages((current) => [
      ...current,
      {
        sequence: current.length,
        role: "user",
        content: message,
        proposal: null,
        result: null,
        created_at: new Date().toISOString(),
      },
    ]);
    setDraft("");

    try {
      const reply = await sendMessage(conversationId, message);
      if (controller.signal.aborted) return;
      setMessages((current) => [...current, reply]);
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
      setSending(false);
    }
  };

  const confirm = async (proposal: BenchmarkProposal) => {
    setConfirming(proposal.id);
    setError(null);
    try {
      const reply = await confirmDraft(conversationId, proposal.id);
      setMessages((current) => [...current, reply]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConfirming("");
    }
  };

  if (!session) {
    return (
      <>
        <div className="page-head">
          <div>
            <h2>{t("chat.title")}</h2>
            <p>{t("chat.subtitle")}</p>
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

  return (
    <div className="chat-page">
      <div className="page-head">
        <div>
          <h2>{t("chat.title")}</h2>
          <p>{t("chat.subtitle")}</p>
        </div>
        <button
          onClick={() => {
            void begin();
          }}
        >
          <Icon name="plus" size={14} /> {t("chat.newChat")}
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="chat-thread" role="log" aria-live="polite">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <EmptyState
              icon="sparkles"
              title={t("chat.empty.title")}
              body={t("chat.empty.body")}
            />
            <div className="quick-actions" style={{ justifyContent: "center" }}>
              {QUICK_PROMPTS.map((key) => (
                <button
                  key={key}
                  type="button"
                  className="quick-action"
                  onClick={() => void ask(t(key))}
                >
                  {t(key)}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <Bubble
              key={`${message.sequence}-${index}`}
              message={message}
              confirming={confirming}
              onConfirm={confirm}
            />
          ))
        )}
        {sending ? (
          <div className="chat-bubble assistant">
            <span className="spinner" aria-hidden="true" /> {t("chat.thinking")}
          </div>
        ) : null}
        <div ref={endOfThread} />
      </div>

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(draft);
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.placeholder")}
          disabled={!conversationId}
        />
        {sending ? (
          <button
            type="button"
            onClick={() => {
              inFlight.current?.abort();
              setSending(false);
            }}
            aria-label={t("chat.stop")}
          >
            {t("chat.stop")}
          </button>
        ) : (
          <button className="primary" type="submit" disabled={!draft.trim() || !conversationId}>
            {t("chat.send")}
          </button>
        )}
      </form>
      <p className="muted" style={{ fontSize: 11, textAlign: "center", marginTop: 8 }}>
        {t("chat.noRun")}
      </p>
    </div>
  );
}

function Bubble({
  message,
  confirming,
  onConfirm,
}: {
  message: ChatMessage;
  confirming: string;
  onConfirm: (proposal: BenchmarkProposal) => void;
}) {
  const { t } = useTranslation();
  // Assistant replies arrive as translation keys; a user's own words
  // are shown exactly as typed.
  const text =
    message.role === "assistant" && isMessageKey(message.content)
      ? t(message.content)
      : message.content;

  return (
    <div className={`chat-bubble ${message.role}`}>
      <div className="chat-author">
        {message.role === "user" ? t("chat.you") : t("chat.assistant")}
      </div>
      <div>{text}</div>
      {message.proposal ? (
        <ProposalCard
          proposal={message.proposal}
          busy={confirming === message.proposal.id}
          onConfirm={onConfirm}
        />
      ) : null}
      {message.result ? <ResultCardView result={message.result} /> : null}
    </div>
  );
}

function ProposalCard({
  proposal,
  busy,
  onConfirm,
}: {
  proposal: BenchmarkProposal;
  busy: boolean;
  onConfirm: (proposal: BenchmarkProposal) => void;
}) {
  const { t } = useTranslation();
  const confirmed = proposal.status === "confirmed";
  const ready = proposal.missing_fields.length === 0;

  return (
    <div className="proposal-card">
      <div className="panel-head">
        <h4 style={{ margin: 0 }}>{t("chat.proposal")}</h4>
        {confirmed ? <span className="badge ok">{t("benchmarks.state.draft")}</span> : null}
      </div>
      <table>
        <tbody>
          <tr>
            <td className="muted">{t("common.scenario")}</td>
            <td>{proposal.scenario_name || "—"}</td>
          </tr>
          <tr>
            <td className="muted">{t("benchmarks.stacks")}</td>
            {/* Stack ids are protocol tokens: never translated. */}
            <td>
              {proposal.stacks.map((stack) => (
                <code key={stack} className="chip">
                  {stack}
                </code>
              ))}
            </td>
          </tr>
          {proposal.model_label ? (
            <tr>
              <td className="muted">{t("benchmarks.ppoModel")}</td>
              <td>{proposal.model_label}</td>
            </tr>
          ) : null}
          <tr>
            <td className="muted">{t("common.seeds")}</td>
            <td>{proposal.seeds.join(", ")}</td>
          </tr>
        </tbody>
      </table>

      {proposal.assumptions.length > 0 ? (
        <p className="muted" style={{ fontSize: 11 }}>
          {t("chat.assumed")}: {proposal.assumptions.join("; ")}
        </p>
      ) : null}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
        {confirmed && proposal.benchmark_id ? (
          <Link className="quick-action primary" href={`/benchmarks/${proposal.benchmark_id}`}>
            {t("chat.openBenchmark")}
          </Link>
        ) : ready ? (
          <button className="primary" disabled={busy} onClick={() => onConfirm(proposal)}>
            {busy ? t("chat.creating") : t("chat.createDraft")}
          </button>
        ) : (
          <Link className="quick-action" href="/models">
            {t("benchmarks.uploadModel")}
          </Link>
        )}
      </div>
    </div>
  );
}

function ResultCardView({ result }: { result: ResultCard }) {
  const { t } = useTranslation();
  const percent = (value: number) => `${(value * 100).toFixed(0)}%`;

  return (
    <div className="proposal-card">
      <div className="panel-head">
        <h4 style={{ margin: 0 }}>{t("chat.results")}</h4>
        <Link href={`/benchmarks/${result.benchmark_id}`}>{t("chat.openBenchmark")}</Link>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{t("algorithms.stack")}</th>
              <th>{t("chat.successRate")}</th>
              <th>{t("chat.collisionRate")}</th>
              <th>{t("chat.clearance")}</th>
            </tr>
          </thead>
          <tbody>
            {result.aggregates.map((row) => (
              <tr key={row.algorithm}>
                <td>
                  <code>{row.algorithm}</code>
                </td>
                <td>{percent(row.success_rate)}</td>
                <td>{percent(row.collision_rate)}</td>
                <td>
                  {row.worst_min_clearance === null
                    ? "—"
                    : `${row.worst_min_clearance.toFixed(3)} m`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details style={{ marginTop: 8 }}>
        <summary className="muted">{t("chat.viewEvidence")}</summary>
        <p className="muted" style={{ fontSize: 11 }}>
          {/* The checksum is evidence, not decoration — but it belongs
              behind a disclosure, not in the main flow. */}
          <code>{result.conditions_checksum.slice(0, 24)}</code>
        </p>
      </details>
    </div>
  );
}
