"use client";

/** The floating agent, now with the agent behind it.
 *
 * **What changed, and why it had to.** This started as a placeholder
 * that disabled its own composer, which was the honest thing to do while
 * nothing was wired to it. The agent it was waiting for already exists —
 * `POST /agent/chat`, backed by the provider factory — and it was
 * reachable only from a tile on the dashboard, because the sidebar entry
 * came off when this dock arrived. So the app had a dead chat box on
 * every page and a live one behind a link. This closes that: the dock
 * asks the same endpoint the `/agent` page asks.
 *
 * **The thread lives here, not on the server.** `/agent/chat` is
 * stateless by design, so there is no hidden context making the second
 * answer depend on a first the reader cannot see. Keeping the transcript
 * in component state has a second effect worth naming: only the panel
 * unmounts when the dock closes, so an answer that lands while it is
 * shut is waiting when it reopens rather than lost.
 *
 * **Questions only.** Papers, plugin drafts and the capability table
 * stay on `/agent`, which is linked from the footer of the panel. A
 * 380px card is the wrong place to inspect what a model was allowed to
 * do, and duplicating that surface would mean two implementations of it
 * drifting apart.
 *
 * **Floating rather than docked, deliberately.** A panel in the layout
 * takes width from the page whether or not anybody is talking to it, and
 * every canvas on this app is measured in pixels rather than
 * percentages — a shell that changes the content width changes what
 * `MissionCanvas` thinks a click means. Floating over the page costs the
 * layout nothing and can be dismissed with Escape.
 *
 * The launcher sits bottom-right because bottom-left already belongs to
 * the framework's own dev overlay, and two circles in one corner is one
 * corner nobody can use.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { askAgent, type ChatTurn } from "@/lib/agent";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { useDismiss } from "@/lib/useDismiss";

interface Entry {
  role: "user" | "agent";
  text: string;
  /** Present on an answer: which tools ran, and whether the budget ran
   *  out before one. Kept beside the text rather than folded into it,
   *  because it is evidence about the answer and not part of it. */
  turn?: ChatTurn;
  /** The answer came from the offline keyword responder rather than a
   *  model. Read off the response instead of asking
   *  `/agent/capabilities` on open: the dock would pay for that request
   *  on every page whether or not anybody typed, and the two answers
   *  read alike, so the flag has to travel with the answer it describes
   *  in any case. */
  deterministic?: boolean;
}

export function AgentDock() {
  const { t } = useTranslation();
  const session = useSession();
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const endOfThread = useRef<HTMLDivElement | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  // Escape and an outside click both close it. The launcher is outside
  // the panel, so it is held in the same ref subtree — otherwise
  // clicking the button to close would register as an outside click,
  // close the panel, and then reopen it on the same gesture.
  const dockRef = useRef<HTMLDivElement | null>(null);
  useDismiss(open, () => setOpen(false), dockRef);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, busy, open]);

  /** Ask, and let the answer land in the thread.
   *
   * The request is deliberately not cancelled when the panel closes.
   * Somebody who clicks away from a question they asked has not
   * withdrawn it, and a model call thrown away on a mis-click is a model
   * call nobody gets back. Stop is the way to withdraw one, and it says
   * so.
   */
  async function ask() {
    const message = draft.trim();
    if (!message || busy) return;
    setDraft("");
    setError(null);
    setEntries((prev) => [...prev, { role: "user", text: message }]);
    setBusy(true);
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const response = await askAgent(message, controller.signal);
      if (controller.signal.aborted) return;
      setEntries((prev) => [
        ...prev,
        {
          role: "agent",
          text: response.turn.text,
          turn: response.turn,
          deterministic: response.deterministic,
        },
      ]);
    } catch (caught) {
      // An aborted request is not a failure to report: the reader
      // pressed Stop and already knows.
      if (!controller.signal.aborted) setError((caught as Error).message);
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
      setBusy(false);
    }
  }

  return (
    <div className="agent-dock" ref={dockRef}>
      {open ? (
        <div
          className="agent-dock-panel"
          ref={panelRef}
          role="dialog"
          aria-label={t("agentDock.title")}
        >
          <header className="agent-dock-head">
            <span className="agent-dock-mark" aria-hidden="true">
              <Icon name="sparkles" size={16} />
            </span>
            <div>
              <strong>{t("agentDock.title")}</strong>
              <p className="muted small">{t("agentDock.subtitle")}</p>
            </div>
            <button
              type="button"
              className="agent-dock-close"
              aria-label={t("common.close")}
              onClick={() => setOpen(false)}
            >
              <Icon name="close" size={15} />
            </button>
          </header>

          <div className="agent-dock-log" role="log" aria-live="polite">
            {/* Signed out, the composer would take a question and get a
                401 back. Saying so up front costs the reader nothing;
                finding out after typing costs them the question. */}
            {!session ? (
              <p className="muted small">
                {t("agentDock.signedOut")} <Link href="/login">{t("topbar.signIn")}</Link>
              </p>
            ) : entries.length === 0 ? (
              <p className="muted small">{t("agentDock.placeholder")}</p>
            ) : (
              entries.map((entry, index) => (
                <div
                  key={index}
                  className={`chat-bubble ${entry.role === "user" ? "user" : "assistant"}`}
                >
                  <p>{entry.text}</p>
                  {entry.deterministic ? (
                    <p className="muted small">{t("agentDock.mock")}</p>
                  ) : null}
                  {/* An answer whose tool budget ran out has stopped
                      mid-thought. Left unsaid, it reads as a finished
                      one. */}
                  {entry.turn?.truncated ? (
                    <p className="muted small">{t("agentDock.truncated")}</p>
                  ) : null}
                  {entry.turn && entry.turn.tools_used.length > 0 ? (
                    <p className="muted small">
                      {t("agentDock.toolsUsed", { tools: entry.turn.tools_used.join(", ") })}
                    </p>
                  ) : null}
                  {entry.turn && entry.turn.tool_errors.length > 0 ? (
                    <p className="muted small">
                      {t("agentDock.toolErrors", { errors: entry.turn.tool_errors.join(", ") })}
                    </p>
                  ) : null}
                </div>
              ))
            )}
            {busy ? <p className="muted small">{t("agentDock.thinking")}</p> : null}
            {error ? (
              <p className="muted small" role="alert">
                {error}
              </p>
            ) : null}
            <div ref={endOfThread} />
          </div>

          <form
            className="agent-dock-composer"
            onSubmit={(event) => {
              // Handled here rather than left to the browser: the
              // default is a navigation nobody asked for, and it would
              // take the transcript with it.
              event.preventDefault();
              void ask();
            }}
          >
            <input
              type="text"
              value={draft}
              disabled={!session}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("agentDock.inputPlaceholder")}
              aria-label={t("agentDock.inputPlaceholder")}
            />
            {busy ? (
              <button
                type="button"
                onClick={() => inFlight.current?.abort()}
                aria-label={t("agentDock.stop")}
              >
                {t("agentDock.stop")}
              </button>
            ) : (
              <button type="submit" disabled={!session || !draft.trim()}>
                {t("agentDock.send")}
              </button>
            )}
          </form>

          {/* Papers, plugin drafts and the capability table live on the
              full page. Named here so the dock is a shortcut to the
              agent rather than a smaller, quieter version of it. */}
          <p className="agent-dock-more muted small">
            <Link href="/agent">{t("agentDock.openFull")}</Link>
          </p>
        </div>
      ) : null}

      <button
        type="button"
        className="agent-dock-launcher"
        aria-expanded={open}
        aria-label={t("agentDock.title")}
        title={t("agentDock.title")}
        onClick={() => setOpen((current) => !current)}
      >
        <Icon name={open ? "close" : "sparkles"} size={20} />
      </button>
    </div>
  );
}
