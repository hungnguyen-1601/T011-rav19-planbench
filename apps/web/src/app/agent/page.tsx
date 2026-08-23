"use client";

/** Ask the model about what the platform recorded.
 *
 * **The shape is the one people already know.** A thread that fills the
 * screen, a composer pinned to the bottom of it, the reader's own words
 * on the right and the answer running the full width on the left. That
 * is not fashion: an answer here is prose with tool evidence under it,
 * sometimes a whole extracted paper, and a bubble sized to a chat
 * message wraps that into a column too narrow to read. The question is
 * short and stays in a bubble; the answer is long and does not.
 *
 * Three things on screen are load-bearing rather than decorative:
 *
 * - **The provider badge.** An answer from the offline responder reads
 *   exactly like an answer from a model. The badge says which, before
 *   the first question rather than after a confusing one.
 * - **The tools that ran.** They are the reason to believe an answer
 *   came from stored data. An answer with no tool calls is the model
 *   talking from memory, and the page shows that plainly instead of
 *   hiding it. It is a chip in the same row as the others rather than a
 *   footnote, because "read nothing" is the most important thing that
 *   row can say and it used to be the quietest.
 * - **What the agent cannot do**, published from the server's own list
 *   rather than written here, so the claim stays true when the list
 *   changes.
 *
 * What the redesign deliberately did **not** do: give the thread a
 * history rail. The server keeps no conversation — `/agent/chat` is
 * stateless — so a rail listing past chats would be listing something
 * that does not exist, and building one means first deciding where a
 * transcript lives and who may read it. That is a data question, not a
 * layout one.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { MAX_PAPER_BYTES, PAPER_FILE_TYPES, PaperResult } from "@/components/FromPaperPanel";
import { Icon } from "@/components/Icon";
import { PluginDraftView } from "@/components/PluginDraftView";
import { askAgent, getCapabilities, type Capabilities, type ChatTurn } from "@/lib/agent";
import { useSession } from "@/lib/auth";
import {
  draftPluginFromPaperFile,
  extractCandidateFromPaperFile,
  type PaperExtraction,
  type PluginDraft,
} from "@/lib/decisions";
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

/** How far the textarea may grow before it scrolls instead.
 *
 * Past this the composer is eating the thread it belongs to, and the
 * reader loses sight of what they are replying to while replying to it.
 */
const COMPOSER_MAX_HEIGHT = 200;

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
  const composer = useRef<HTMLTextAreaElement>(null);
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

  /* Measured, not guessed. `rows` cannot express "as tall as the text"
     and a fixed height either wastes three lines on a short question or
     hides the top of a long one. Reset to `auto` first so the box can
     shrink again when the text does. */
  useEffect(() => {
    const box = composer.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, COMPOSER_MAX_HEIGHT)}px`;
  }, [draft, attached]);

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
      const drafted = await draftPluginFromPaperFile(lastPaper, controller.signal);
      if (controller.signal.aborted) return;
      setEntries((prev) => [...prev, { role: "agent", text: "", plugin: drafted }]);
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message);
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
   * by keystroke and then dropped.
   *
   * The upload endpoint takes a file and nothing else, so the question
   * cannot ride along with it. It goes as the next turn instead, which
   * is the closest honest thing to a caption: the paper is read, then
   * the question is asked, and both appear in the thread.
   */
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

  const canSend = attached !== null || draft.trim().length > 0;

  return (
    <div className="agent-page">
      <header className="agent-head">
        <span className="agent-avatar" aria-hidden="true">
          <Icon name="sparkles" size={16} />
        </span>
        <div className="agent-head-text">
          <h2>{t("agent.title")}</h2>
          <p className="muted">{t("agent.subtitle")}</p>
        </div>
        {/* The badge belongs beside the name rather than over the
            composer: it qualifies every answer in the thread, not the
            next question. */}
        {capabilities?.deterministic ? (
          <span className="badge warn agent-head-badge">{t("agent.mock")}</span>
        ) : null}
        <Boundaries />
      </header>

      <div className="agent-thread" role="log" aria-live="polite">
        <div className="agent-thread-inner">
          {entries.length === 0 ? (
            <Welcome onPick={(question) => void ask(question)} />
          ) : (
            entries.map((entry, index) => (
              <Message
                key={index}
                entry={entry}
                onBuildPlugin={
                  entry.paper && lastPaper && !busy ? () => void buildPlugin() : undefined
                }
              />
            ))
          )}
          {busy ? (
            <div className="agent-msg agent">
              <Who />
              <p className="muted agent-thinking">
                <span className="spinner" aria-hidden="true" /> {t("agent.thinking")}
              </p>
            </div>
          ) : null}
          {/* In the thread rather than under the header, because it is
              about the turn that just failed and reads as a line in the
              conversation. */}
          {error ? <div className="error-box">{error}</div> : null}
          <div ref={endOfThread} />
        </div>
      </div>

      <div className="agent-composer-wrap">
        <form
          className="agent-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {/* Inside the box and above the text, so a long filename wraps
              across the composer instead of squeezing the line being
              typed into a slot. */}
          {attached ? (
            <div className="agent-chip" role="status" aria-live="polite">
              <Icon name="paperclip" size={14} />
              <span className="agent-chip-name">{attached.name}</span>
              <button
                type="button"
                className="agent-chip-remove"
                aria-label={t("agent.attachRemove")}
                onClick={() => {
                  setAttached(null);
                  attachButton.current?.focus();
                }}
              >
                <Icon name="close" size={13} />
              </button>
            </div>
          ) : null}

          <textarea
            ref={composer}
            className="agent-input"
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              /* Enter sends, Shift+Enter writes a line. The old box was
                 an `<input>`, which made the second impossible: a
                 question with a pasted error message in it had to be
                 flattened to one line before it could be asked. */
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (!busy && canSend) void submit();
              }
            }}
            placeholder={attached ? t("agent.attachedPlaceholder") : t("agent.placeholder")}
            aria-label={t("agent.placeholder")}
          />

          <div className="agent-composer-tools">
            <input
              ref={picker}
              type="file"
              accept={PAPER_FILE_TYPES}
              className="sr-only"
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
              className="agent-attach"
              title={t("agent.attach")}
              aria-label={t("agent.attach")}
              disabled={busy}
              onClick={() => picker.current?.click()}
            >
              <Icon name="paperclip" size={16} />
            </button>
            <span className="agent-composer-hint muted">{t("agent.enterHint")}</span>
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
              <button className="primary" type="submit" disabled={!canSend}>
                {attached ? t("agent.readPaper") : t("agent.send")}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

/** The first screen, which is a prompt rather than an empty box.
 *
 * A chat that opens blank asks the reader to guess what it knows. These
 * four are the questions its tools can actually answer, so the first
 * click is a working demonstration of the thing rather than a coin
 * toss.
 */
function Welcome({ onPick }: { onPick: (question: string) => void }) {
  const { t } = useTranslation();
  return (
    <div className="agent-welcome">
      <span className="agent-welcome-mark" aria-hidden="true">
        <Icon name="sparkles" size={22} />
      </span>
      <h3>{t("agent.empty.title")}</h3>
      <p className="muted">{t("agent.empty.body")}</p>
      <div className="agent-suggestions">
        {QUICK_KEYS.map((key) => (
          <button key={key} type="button" className="agent-suggestion" onClick={() => onPick(t(key))}>
            {t(key)}
          </button>
        ))}
      </div>
    </div>
  );
}

function Who() {
  const { t } = useTranslation();
  return (
    <p className="agent-msg-who">
      <Icon name="sparkles" size={13} />
      {t("agent.name")}
    </p>
  );
}

function Message({
  entry,
  onBuildPlugin,
}: {
  entry: Entry;
  onBuildPlugin?: () => void;
}) {
  const { t } = useTranslation();
  const turn = entry.turn;
  const isUser = entry.role === "user";
  return (
    <div className={`agent-msg ${isUser ? "user" : "agent"}`}>
      {isUser ? null : <Who />}
      {entry.text ? <div className="agent-msg-body">{entry.text}</div> : null}
      {/* Rendered by the candidates page's own component. A second
          rendering would be free to omit the uncomfortable parts — what
          the paper never stated, what cannot be expressed here, how many
          quoted sentences were not in the text — and the reader would
          have no way to tell which one was short. */}
      {entry.paper ? (
        <>
          <PaperResult result={entry.paper} />
          <p className="muted small agent-msg-after">
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
      {turn ? <Evidence turn={turn} /> : null}
      {isUser || !entry.text ? null : <CopyAnswer text={entry.text} />}
    </div>
  );
}

/** What the answer was read from, as chips rather than a footnote.
 *
 * The no-tool case is a chip in the same row and not a quieter line
 * under it. It is the most consequential thing this row can say — the
 * answer came from the model's memory, not from anything recorded — and
 * as small grey prose it read like a disclaimer nobody finishes.
 */
function Evidence({ turn }: { turn: ChatTurn }) {
  const { t } = useTranslation();
  return (
    <div className="agent-evidence">
      {turn.tools_used.length > 0 ? (
        <>
          <span className="agent-evidence-label">{t("agent.toolsUsed")}</span>
          {turn.tools_used.map((name, index) => (
            <code key={`${name}-${index}`} className="agent-tool">
              {name}
            </code>
          ))}
        </>
      ) : (
        <span className="agent-tool warn">{t("agent.noTools")}</span>
      )}
      {turn.tool_errors.length > 0 ? (
        <span className="agent-tool warn">
          {t("agent.toolErrors")}: {turn.tool_errors.join("; ")}
        </span>
      ) : null}
      {turn.truncated ? <span className="agent-tool warn">{t("agent.truncated")}</span> : null}
    </div>
  );
}

/** Copy the answer, not the evidence around it.
 *
 * What people paste into a ticket is the sentences. The tool names and
 * the truncation warning describe how much to trust them, which is the
 * one part that must not travel without the page it was read on.
 */
function CopyAnswer({ text }: { text: string }) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const timer = setTimeout(() => setDone(false), 1600);
    return () => clearTimeout(timer);
  }, [done]);
  return (
    <button
      type="button"
      className="agent-copy"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setDone(true));
      }}
    >
      <Icon name={done ? "check" : "copy"} size={13} />
      {done ? t("agent.copied") : t("agent.copy")}
    </button>
  );
}

/** What the assistant can and cannot do, in two sentences.
 *
 * No function names. They were kept one fold deeper for a while, for
 * checkability, and earned their removal: a reader who wants to verify
 * the sentences against the server reads `GET /agent/capabilities`,
 * which publishes the exact lists and is held to them by tests. The
 * page's job is the claim, not the audit trail.
 *
 * It sits in the header now rather than under the composer. At the foot
 * of a thread that grows it was below the fold from the second answer
 * onward — a statement about what this thing may do, placed where it is
 * read last.
 */
function Boundaries() {
  const { t } = useTranslation();
  return (
    <details className="agent-boundaries">
      <summary className="muted small">{t("agent.boundaries")}</summary>
      <div className="agent-boundaries-body">
        <p className="muted small">{t("agent.canReadPlain")}</p>
        <p className="muted small">{t("agent.cannotPlain")}</p>
      </div>
    </details>
  );
}
