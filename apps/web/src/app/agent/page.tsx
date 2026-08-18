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
import { MAX_PAPER_BYTES, PAPER_FILE_TYPES, PaperResult } from "@/components/FromPaperPanel";
import { Icon } from "@/components/Icon";
import { askAgent, getCapabilities, type Capabilities, type ChatTurn } from "@/lib/agent";
import { PluginDraftView } from "@/components/PluginDraftView";
import {
  draftPluginFromPaperFile,
  extractCandidateFromPaperFile,
  type PaperExtraction,
  type PluginDraft,
} from "@/lib/decisions";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

interface Entry {
  role: "user" | "agent";
  text: string;
  turn?: ChatTurn;
  /** Set when this bubble is a paper the reader attached, rather than
   *  something the model said. Rendered by the same component the
   *  candidates page uses, so the two cannot drift. */
  paper?: PaperExtraction;
  /** Set when this bubble is a drafted plugin bundle. */
  plugin?: PluginDraft;
}

/* Every one of these has to be answerable by a tool.
 *
 * Two used to ask what gate G2 checks and how fairness is kept — both
 * answered from an indexed copy of the contract, which is gone. A
 * suggested question the agent cannot answer is worse than no
 * suggestion: it is the platform inviting a failure and then producing
 * it on the first click.
 */
const QUICK_KEYS = [
  "agent.quick.deployments",
  "agent.quick.runs",
  "agent.quick.candidates",
  "agent.quick.critique",
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
  /* Held until send, the way every chat client does it: attaching is
     not asking. A file that read itself the moment it was picked would
     spend a model call on a mis-click. */
  const [attached, setAttached] = useState<File | null>(null);
  /* The last paper actually sent, kept because the platform stores no
     copy: "now draft a plugin from it" needs the bytes again. */
  const [lastPaper, setLastPaper] = useState<File | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  /* Focus has to land somewhere when the chip unmounts. Without this the
     browser resets to <body> and the next Tab restarts at the skip
     link — a keyboard user who removed one attachment has to traverse
     the whole page to reach the composer again. */
  const attachButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!session) return;
    getCapabilities()
      .then(setCapabilities)
      .catch((caught: Error) => setError(caught.message));
  }, [session]);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, busy]);

  /** Send the attached paper, and let the answer land in the thread.
   *
   * The reading is a turn in the conversation rather than a panel beside
   * it, because that is what a person who dragged a file into a chat box
   * expects back. Nothing is registered — the bubble ends with a pointer
   * to the candidates page, where a human decides.
   */
  async function sendPaper(file: File): Promise<boolean> {
    if (busy) return false;
    const tooBig = file.size > MAX_PAPER_BYTES;
    if (tooBig) {
      // Refused here rather than after the bytes are on the wire: the
      // server answers the same way, but only once the whole file has
      // been uploaded and spooled, with the composer showing nothing
      // but a spinner for the duration.
      setError(t("agent.tooBig", { limit: String(MAX_PAPER_BYTES / (1024 * 1024)) }));
      return false;
    }
    setError(null);
    setEntries((prev) => [...prev, { role: "user", text: file.name }]);
    setBusy(true);
    // Registered in the same slot the chat path uses, so Stop cancels
    // whichever is in flight. Without this, Stop during an upload
    // cleared the spinner and the reading landed anyway, minutes later,
    // under a thread the reader had moved on from.
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const result = await extractCandidateFromPaperFile(file, controller.signal);
      if (controller.signal.aborted) return false;
      setLastPaper(file);
      setEntries((prev) => [...prev, { role: "agent", text: "", paper: result }]);
      // Cleared only now. Clearing before the request meant a refused
      // file — wrong extension, too large, a scan with no text layer —
      // vanished from the composer, leaving the reader to find it in the
      // file dialog again.
      setAttached(null);
      setDraft("");
      return true;
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message);
      return false;
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
      setBusy(false);
    }
  }

  /** One press, both things, in the order a reader means them.
   *
   * The first version disabled the message box the moment a file was
   * attached and sent only the file — so "does this paper mention
   * clearance?", typed before clipping the PDF, was accepted keystroke
   * by keystroke and then dropped. The box had no disabled styling
   * either, so it looked live while swallowing input.
   *
   * The upload endpoint takes a file and nothing else, so the question
   * cannot ride along with it. It goes as the next turn instead, which
   * is the closest honest thing to a caption: the paper is read, then
   * the question is asked, and both appear in the thread.
   */
  /** Draft an Algorithm Host plugin from the last paper sent.
   *
   * A turn in the conversation, like the reading was: the request
   * becomes a user bubble, the validated bundle comes back as the
   * reply. The verdict shown is the deterministic validator's, so a
   * model answer out of the host's shape arrives as a rejection with
   * named errors rather than as a green tick.
   */
  async function buildPlugin() {
    if (busy || !lastPaper) return;
    setError(null);
    setEntries((prev) => [...prev, { role: "user", text: t("plugin.build") }]);
    setBusy(true);
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const draft = await draftPluginFromPaperFile(lastPaper, controller.signal);
      if (controller.signal.aborted) return;
      setEntries((prev) => [...prev, { role: "agent", text: "", plugin: draft }]);
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message);
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
      setBusy(false);
    }
  }

  async function submit() {
    if (!attached) {
      await ask(draft);
      return;
    }
    const question = draft.trim();
    const sent = await sendPaper(attached);
    if (sent && question) await ask(question);
  }

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
        {capabilities?.deterministic ? <OfflineNotice /> : null}
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
              <Bubble
                key={index}
                entry={entry}
                onBuildPlugin={
                  entry.paper && lastPaper && !busy ? () => void buildPlugin() : undefined
                }
              />
            ))
          )}
          {busy ? (
            <div className="chat-bubble assistant">
              <span className="spinner" aria-hidden="true" /> {t("agent.thinking")}
            </div>
          ) : null}
          <div ref={endOfThread} />
        </div>

        {/* The attachment sits above the input rather than inside it, so
            a long filename wraps instead of squeezing the box a person is
            typing into. */}
        {/* `role="status"` so the change is announced. Attaching alters
            the send button's label and what the next press will do, and
            a reader who cannot see the chip otherwise learns none of
            that. */}
        {attached ? (
          <div className="chat-attachment" role="status" aria-live="polite">
            <Icon name="paperclip" />
            <span className="chat-attachment-name">{attached.name}</span>
            <button
              type="button"
              className="chat-attachment-remove"
              aria-label={t("agent.attachRemove")}
              onClick={() => {
                setAttached(null);
                attachButton.current?.focus();
              }}
            >
              <Icon name="close" />
            </button>
          </div>
        ) : null}

        <form
          className="chat-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <input
            ref={picker}
            type="file"
            accept={PAPER_FILE_TYPES}
            style={{ display: "none" }}
            data-testid="agent-paper-file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Cleared so the same file can be picked again after a
              // failure; an input that keeps its value fires no change.
              event.target.value = "";
              if (file) setAttached(file);
            }}
          />
          <button
            ref={attachButton}
            type="button"
            className="chat-attach"
            title={t("agent.attach")}
            aria-label={t("agent.attach")}
            disabled={busy}
            onClick={() => picker.current?.click()}
          >
            <Icon name="paperclip" />
          </button>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={attached ? t("agent.attachedPlaceholder") : t("agent.placeholder")}
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
            <button
              className="primary"
              type="submit"
              disabled={attached ? false : !draft.trim()}
            >
              {attached ? t("agent.readPaper") : t("agent.send")}
            </button>
          )}
        </form>
        {capabilities ? <Boundaries capabilities={capabilities} /> : null}
      </div>
    </div>
  );
}

/** Shown only when no model is answering.
 *
 * The vendor and model name are gone from this page: which provider
 * served a request is a deployment fact, and a reader judging an answer
 * has nothing to do with it. This is the one part that was not a
 * badge — a canned answer and a model's answer read alike, so a page
 * that let them look identical would be lying by omission.
 */
function OfflineNotice() {
  const { t } = useTranslation();
  return <span className="badge warn">{t("agent.mock")}</span>;
}

function Bubble({
  entry,
  onBuildPlugin,
}: {
  entry: Entry;
  onBuildPlugin?: () => void;
}) {
  const { t } = useTranslation();
  const turn = entry.turn;
  return (
    <div className={`chat-bubble ${entry.role === "user" ? "user" : "assistant"}`}>
      {entry.text ? <div style={{ whiteSpace: "pre-wrap" }}>{entry.text}</div> : null}
      {/* Rendered by the candidates page's own component. A second
          rendering would be free to omit the uncomfortable parts — what
          the paper never stated, what cannot be expressed here, how many
          quoted sentences were not in the text — and the reader would
          have no way to tell which one was short. */}
      {entry.paper ? (
        <>
          <PaperResult result={entry.paper} />
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
            <Link href="/candidates">{t("agent.paperRegister")}</Link>
            {onBuildPlugin ? (
              <>
                {" · "}
                <button type="button" className="link-button" onClick={onBuildPlugin}>
                  {entry.paper.stack ? t("plugin.build") : t("plugin.buildNoStack")}
                </button>
              </>
            ) : null}
          </p>
        </>
      ) : null}
      {entry.plugin ? <PluginDraftView draft={entry.plugin} /> : null}
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

/** What the assistant can and cannot do, said in words first.
 *
 * This used to be two rows of function names — `write_task_profile`,
 * `declare_safe` — which tell a reader nothing and made the one claim
 * worth making look like debug output. The claim is that this thing
 * cannot act: it reads stored data and returns sentences, and every
 * decision stays with a person.
 *
 * The raw names survive one level deeper, because the claim has to stay
 * checkable. A reviewer who wants to confirm the list matches the server
 * can open it; nobody else has to read it to understand the guarantee.
 */
function Boundaries({ capabilities }: { capabilities: Capabilities }) {
  const { t } = useTranslation();
  return (
    <details style={{ marginTop: 10 }}>
      <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>
        {t("agent.boundaries")}
      </summary>

      <p className="muted" style={{ fontSize: 12, marginTop: 8, marginBottom: 6 }}>
        {t("agent.canReadPlain")}
      </p>
      <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
        {t("agent.cannotPlain")}
      </p>

      <details style={{ marginTop: 6 }}>
        <summary className="muted" style={{ fontSize: 11, cursor: "pointer" }}>
          {t("agent.boundariesRaw")}
        </summary>
        <p className="muted" style={{ fontSize: 11, marginTop: 6, marginBottom: 4 }}>
          {t("agent.canRead")}:{" "}
          {capabilities.tools.map((name) => (
            <code key={name} style={{ marginRight: 6 }}>
              {name}
            </code>
          ))}
        </p>
        <p className="muted" style={{ fontSize: 11, marginBottom: 0 }}>
          {t("agent.cannot")}:{" "}
          {capabilities.forbidden.map((name) => (
            <code key={name} style={{ marginRight: 6 }}>
              {name}
            </code>
          ))}
        </p>
      </details>
    </details>
  );
}

