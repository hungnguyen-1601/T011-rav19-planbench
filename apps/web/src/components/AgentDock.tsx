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
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { askAgent, type ChatContext, type ChatTurn } from "@/lib/agent";
import { DockAnalyst } from "@/components/DockAnalyst";
import { episodeForRun, useEpisodeSelection } from "@/lib/episodeSelection";
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
  /** A context was offered with this question. */
  contextOffered?: boolean;
  /** The server confirmed the record on screen and told the model about
   *  it. Kept apart from `contextOffered` because "never attached" and
   *  "attaching failed" are two different sentences, and only the second
   *  misleads — the reader watched a chip say this question was about
   *  the run in front of them. */
  contextUsed?: boolean;
  /** The answer came from the offline keyword responder rather than a
   *  model. Read off the response instead of asking
   *  `/agent/capabilities` on open: the dock would pay for that request
   *  on every page whether or not anybody typed, and the two answers
   *  read alike, so the flag has to travel with the answer it describes
   *  in any case. */
  deterministic?: boolean;
}

/** The run this page is about, or "" on a page that is about no run.
 *
 * Read from the route rather than passed down: the dock floats over
 * every page from the shell, and threading a prop through every one of
 * them to reach a component none of them render is a lot of edits for a
 * fact the URL already carries. */
function runOnScreen(pathname: string | null): string {
  const match = /^\/decisions\/([^/]+)\/?$/.exec(pathname ?? "");
  return match ? decodeURIComponent(match[1]) : "";
}

export function AgentDock() {
  const { t } = useTranslation();
  const session = useSession();
  const pathname = usePathname();
  const runId = runOnScreen(pathname);
  // Which episode the reader pointed at on this run, if any. Empty
  // for a run whose replay nobody has chosen from, and empty the
  // moment they walk to another run: an id belonging to the page
  // before would put the model in front of the wrong record.
  const episodeId = episodeForRun(runId, useEpisodeSelection());
  // Attached by default, because a question typed on a run's page is
  // almost always about that run. Detaching is one click and it stays
  // detached only until the page changes: the reader who walked to a
  // different run means the new one.
  const [attached, setAttached] = useState(true);
  useEffect(() => {
    setAttached(true);
  }, [runId]);
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
    const context: ChatContext | undefined =
      attached && runId
        ? episodeId
          ? { run_id: runId, episode_context_id: episodeId }
          : { run_id: runId }
        : undefined;
    setEntries((prev) => [...prev, { role: "user", text: message }]);
    setBusy(true);
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const response = await askAgent(message, controller.signal, context);
      if (controller.signal.aborted) return;
      setEntries((prev) => [
        ...prev,
        {
          role: "agent",
          text: response.turn.text,
          turn: response.turn,
          contextUsed: response.context_used,
          contextOffered: Boolean(context),
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

          {/* Declared, not silent. A question that quietly carried the
              open run would be exactly the hidden context `/agent/chat`
              was kept stateless to avoid — the reader has to be able to
              see what their question was about, and say no. */}
          {session && runId ? (
            <div className="agent-dock-context">
              <Icon name="paperclip" size={13} />
              <span className="small">
                {attached ? t("agentDock.contextOn") : t("agentDock.contextAttach")}
              </span>
              <button type="button" className="small" onClick={() => setAttached((on) => !on)}>
                {attached ? t("agentDock.contextDetach") : t("agentDock.contextAttach")}
              </button>
            </div>
          ) : null}

          {/* **The analyst takes the dock when there is an episode to
              answer about.** It answers one fixed question against one
              packet and its answer goes through the ten rules, which is
              why it can be shown at all; the composer below answers
              anything and cannot, because prose has nothing in it for a
              rule to read. The chat stays for the pages where no
              episode is selected, which is most of them — an analyst
              with no packet has nothing to be right about. */}
          {session && runId && episodeId ? (
            <div className="agent-dock-log">
              <DockAnalyst runId={runId} episodeId={episodeId} />
            </div>
          ) : (
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
                  {/* Offered and refused is a different fact from never
                      offered, and only the first one misleads: the
                      reader watched a chip say their question was about
                      this run. */}
                  {entry.contextOffered && entry.contextUsed === false ? (
                    <p className="muted small">{t("agentDock.contextLost")}</p>
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
          )}

          {session && runId && episodeId ? null : (
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
          )}

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
