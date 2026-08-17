"use client";

/** Ask the model about what the platform recorded.
 *
 * What this replaced: a keyword matcher that drafted benchmarks for a
 * page that no longer exists. It never called a model, so a key in
 * `.env` changed nothing about it, and the drafts it produced pointed at
 * a 404. Deleting it was the honest move — a chat box that cannot use
 * the model it appears to be is worse than no chat box.
 *
 * Three things on screen are load-bearing rather than decorative:
 *
 * - **The provider badge.** An answer from the offline responder reads
 *   exactly like an answer from a model. The badge says which, before
 *   the first question rather than after a confusing one.
 * - **The tools that ran.** They are the reason to believe an answer
 *   came from stored data. An answer with no tool calls is the model
 *   talking from memory, and the page shows that plainly instead of
 *   hiding it.
 * - **What the agent cannot do**, published from the server's own list
 *   rather than written here, so the claim stays true when the list
 *   changes.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { EmptyState } from "@/components/EmptyState";
import { Icon } from "@/components/Icon";
import { askAgent, getCapabilities, type Capabilities, type ChatTurn } from "@/lib/agent";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

interface Entry {
  role: "user" | "agent";
  text: string;
  turn?: ChatTurn;
}

const QUICK_KEYS = [
  "agent.quick.deployments",
  "agent.quick.runs",
  "agent.quick.gates",
  "agent.quick.contract",
] as const;

export default function AgentPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endOfThread = useRef<HTMLDivElement>(null);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!session) return;
    getCapabilities()
      .then(setCapabilities)
      .catch((caught: Error) => setError(caught.message));
  }, [session]);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, busy]);

  async function ask(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setDraft("");
    setError(null);
    setEntries((prev) => [...prev, { role: "user", text: message }]);
    setBusy(true);
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const response = await askAgent(message, controller.signal);
      setEntries((prev) => [
        ...prev,
        { role: "agent", text: response.turn.text, turn: response.turn },
      ]);
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message);
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
      setBusy(false);
    }
  }

  if (!session) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <h2>{t("agent.title")}</h2>
            <p>{t("agent.subtitle")}</p>
          </div>
        </div>
        <div className="notice">
          <Link href="/login">{t("topbar.signIn")}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>{t("agent.title")}</h2>
          <p>{t("agent.subtitle")}</p>
        </div>
        {capabilities ? <ProviderBadge capabilities={capabilities} /> : null}
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="chat-main">
        <div className="chat-thread" role="log" aria-live="polite">
          {entries.length === 0 ? (
            <div className="chat-welcome">
              <EmptyState
                icon="sparkles"
                title={t("agent.empty.title")}
                body={t("agent.empty.body")}
              />
              <div className="quick-actions" style={{ justifyContent: "center" }}>
                {QUICK_KEYS.map((key) => (
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
            entries.map((entry, index) => (
              <Bubble key={index} entry={entry} />
            ))
          )}
          {busy ? (
            <div className="chat-bubble assistant">
              <span className="spinner" aria-hidden="true" /> {t("agent.thinking")}
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
            placeholder={t("agent.placeholder")}
            aria-label={t("agent.placeholder")}
          />
          {busy ? (
            <button
              type="button"
              onClick={() => {
                inFlight.current?.abort();
                setBusy(false);
              }}
            >
              {t("agent.stop")}
            </button>
          ) : (
            <button className="primary" type="submit" disabled={!draft.trim()}>
              {t("agent.send")}
            </button>
          )}
        </form>
        {capabilities ? <Boundaries capabilities={capabilities} /> : null}
      </div>
    </div>
  );
}

function ProviderBadge({ capabilities }: { capabilities: Capabilities }) {
  const { t } = useTranslation();
  return (
    <div className="toolbar" style={{ alignItems: "center" }}>
      <code>
        {capabilities.provider}
        {capabilities.model ? ` · ${capabilities.model}` : ""}
      </code>
      <span className={capabilities.deterministic ? "badge warn" : "badge ok"}>
        {t(capabilities.deterministic ? "agent.mock" : "agent.live")}
      </span>
      <span className="muted" style={{ fontSize: 12 }}>
        {t("agent.indexed", { count: String(capabilities.knowledge_documents) })}
      </span>
    </div>
  );
}

function Bubble({ entry }: { entry: Entry }) {
  const { t } = useTranslation();
  const turn = entry.turn;
  return (
    <div className={`chat-bubble ${entry.role === "user" ? "user" : "assistant"}`}>
      <div style={{ whiteSpace: "pre-wrap" }}>{entry.text}</div>
      {turn ? (
        <>
          {turn.tools_used.length > 0 ? (
            <p className="muted" style={{ fontSize: 11, marginTop: 6, marginBottom: 0 }}>
              {t("agent.toolsUsed")}:{" "}
              {turn.tools_used.map((name, index) => (
                <code key={`${name}-${index}`} style={{ marginRight: 6 }}>
                  {name}
                </code>
              ))}
            </p>
          ) : (
            /* No tool ran, so nothing here came from stored data. Saying
               so is the difference between an answer and a guess. */
            <p className="muted" style={{ fontSize: 11, marginTop: 6, marginBottom: 0 }}>
              {t("agent.noTools")}
            </p>
          )}
          {turn.tool_errors.length > 0 ? (
            <p className="muted" style={{ fontSize: 11, marginBottom: 0 }}>
              {t("agent.toolErrors")}: {turn.tool_errors.join("; ")}
            </p>
          ) : null}
          {turn.truncated ? <div className="notice">{t("agent.truncated")}</div> : null}
        </>
      ) : null}
    </div>
  );
}

function Boundaries({ capabilities }: { capabilities: Capabilities }) {
  const { t } = useTranslation();
  return (
    <details style={{ marginTop: 10 }}>
      <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>
        {t("agent.boundaries")}
      </summary>
      <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
        {t("agent.canRead")}:{" "}
        {capabilities.tools.map((name) => (
          <code key={name} style={{ marginRight: 6 }}>
            {name}
          </code>
        ))}
      </p>
      <p className="muted" style={{ fontSize: 12 }}>
        {t("agent.cannot")}:{" "}
        {capabilities.forbidden.map((name) => (
          <code key={name} style={{ marginRight: 6 }}>
            {name}
          </code>
        ))}
      </p>
    </details>
  );
}
