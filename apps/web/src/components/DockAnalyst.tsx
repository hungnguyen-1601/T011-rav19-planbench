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
    return <p className="muted small">{t("agentDock.analyst.pickAnEpisode")}</p>;
  }
  const answeredByFloor =
    slot.state === "ready" && slot.view.model?.answered_by === "floor";
  return (
    <>
      <EpisodeVerdictPanel
        slot={slot}
        episodeSelected
        onAskTheModel={() => void ask()}
        asking={asking}
      />
      {/* **Said, not left to be inferred.** When every proposal is
          refused the platform answers from the packet in fixed phrasing,
          and that text reads exactly like the model's. A reader who
          typed a question and is shown template sentences that are not
          about it has been told something untrue by omission. */}
      {answeredByFloor ? (
        <p className="muted small" role="status">
          {t("agentDock.analyst.answeredByFloor")}
        </p>
      ) : null}
      <label className="agent-dock-analyst-ask">
        <span className="visually-hidden">{t("agentDock.analyst.questionLabel")}</span>
        <input
          type="text"
          value={question}
          maxLength={1000}
          placeholder={t("agentDock.analyst.questionPlaceholder")}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !asking) void ask();
          }}
          disabled={asking}
        />
      </label>
      {/* Left empty on purpose is a real choice, not an oversight: it
          asks the one question every quality figure for this scope was
          measured against. Anything typed here is outside that. */}
      <p className="muted small">{t("agentDock.analyst.questionHint")}</p>
    </>
  );
}
