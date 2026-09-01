"use client";

/** The episode analyst, in the dock.
 *
 * The dock's own composer asks a free-form question and gets prose
 * back; this asks the one fixed question — *which side did this episode
 * go to, and which difference bears on that* — and gets structure back:
 * a register, a subject, refs the platform resolved. That difference is
 * the whole reason the two are not one box. Prose cannot be put through
 * the ten rules, because there is nothing in it for a rule to read.
 *
 * **It needs an episode and says so when it has none.** The analyst
 * answers about one episode against one packet; with nothing selected
 * there is no packet, and a dock that pretended otherwise would produce
 * an answer about whichever episode the replay happened to open on —
 * which nobody chose.
 */

import { useEffect, useState } from "react";

import { EpisodeVerdictPanel, type VerdictSlot } from "@/components/EpisodeVerdictPanel";
import { Icon } from "@/components/Icon";
import { getEpisodeVerdict, postEpisodeAnalysis } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

export function DockAnalyst({ runId, episodeId }: { runId: string; episodeId: string }) {
  const { t } = useTranslation();
  const [slot, setSlot] = useState<VerdictSlot>({ state: "idle" });
  const [asking, setAsking] = useState(false);
  /** What the reader typed. Empty is the question this scope's quality
   *  figures were measured on, and sending empty is how somebody asks
   *  for the answer those figures describe. */
  const [question, setQuestion] = useState("");

  // The deterministic half, fetched whenever the reader points at a
  // different episode. It costs nothing and needs no model, so there is
  // no reason to make somebody press a button for it — the button is
  // for the half that spends money.
  useEffect(() => {
    if (!runId || !episodeId) {
      setSlot({ state: "idle" });
      return;
    }
    const controller = new AbortController();
    setSlot({ state: "loading" });
    getEpisodeVerdict(runId, episodeId, "", "", controller.signal)
      .then((view) => setSlot({ state: "ready", view }))
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setSlot({ state: "error", message: caught instanceof Error ? caught.message : String(caught) });
      });
    return () => controller.abort();
  }, [runId, episodeId]);

  async function ask(): Promise<void> {
    if (!runId || !episodeId || asking) return;
    setAsking(true);
    try {
      const view = await postEpisodeAnalysis(runId, episodeId, "", "", undefined, question);
      setSlot({ state: "ready", view });
    } catch (caught) {
      // The deterministic verdict is already on screen and stays there.
      // A model that could not be reached costs the reader the model's
      // half, not the answer.
      setSlot((current) =>
        current.state === "ready"
          ? current
          : { state: "error", message: caught instanceof Error ? caught.message : String(caught) },
      );
    } finally {
      setAsking(false);
    }
  }

  if (!runId || !episodeId) {
    // Wrapped in the log the same way the answer is: this sits in the
    // panel's scrolling slot, and a bare paragraph there would stretch
    // to fill the height the composer is supposed to leave it.
    return (
      <div className="agent-dock-log">
        <p className="muted small">{t("agentDock.analyst.pickAnEpisode")}</p>
      </div>
    );
  }
  const answeredByFloor =
    slot.state === "ready" && slot.view.model?.answered_by === "floor";
  return (
    <>
      {/* The scrolling half. Everything that grows when an answer
          arrives lives here, and only here — the composer below must
          not move when it does. */}
      <div className="agent-dock-log">
        <EpisodeVerdictPanel
          slot={slot}
          episodeSelected
          onAskTheModel={() => void ask()}
          asking={asking}
        />
        {/* **Said, not left to be inferred.** When every proposal is
            refused the platform answers from the packet in fixed
            phrasing, and that text reads exactly like the model's. A
            reader who typed a question and is shown template sentences
            that are not about it has been told something untrue by
            omission. */}
        {answeredByFloor ? (
          <p className="muted small" role="status">
            {t("agentDock.analyst.answeredByFloor")}
          </p>
        ) : null}
      </div>

      {/* The pinned half, in the same slot and the same shape the chat
          composer uses. A form rather than a bare input so Enter
          submits the way it does in every other text box, and
          `preventDefault` because the browser's own answer to a submit
          is a navigation that would take the answer with it. */}
      <form
        className="agent-dock-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void ask();
        }}
      >
        {/* `sr-only` is the class this stylesheet actually defines. It
            was written as `visually-hidden`, which matches nothing, so
            the label rendered as ordinary text and took a third of the
            composer's width away from the box beside it. */}
        <label className="sr-only" htmlFor="dock-analyst-ask">
          {t("agentDock.analyst.questionLabel")}
        </label>
        <input
          id="dock-analyst-ask"
          type="text"
          value={question}
          maxLength={1000}
          placeholder={t("agentDock.analyst.questionPlaceholder")}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={asking}
        />
        {/* Never disabled on an empty box: empty is the fixed question,
            and a send button greyed out until something is typed would
            hide the one question this scope's figures describe.

            The glyph is `aria-hidden`, so the button needs a name of
            its own — an icon-only control with no label is a button a
            screen reader can only call "button". */}
        <button
          type="submit"
          className="agent-dock-send"
          disabled={asking}
          aria-label={asking ? t("agentDock.thinking") : t("agentDock.send")}
          title={asking ? t("agentDock.thinking") : t("agentDock.send")}
        >
          <Icon name="send" size={16} />
        </button>
      </form>

      {/* Under the composer, where a chat puts what its reader should
          know about the answers. Left empty on purpose is a real
          choice, not an oversight: it asks the one question every
          quality figure for this scope was measured against. */}
      <p className="agent-dock-note muted small">{t("agentDock.analyst.questionHint")}</p>
    </>
  );
}
