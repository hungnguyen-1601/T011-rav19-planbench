"use client";

/** Which episode a reader has pointed at, for the components that float.
 *
 * The dock hangs over every page from the shell and reads the run id
 * out of the address bar, because the URL already carries it. An
 * episode is not in the URL — it is state inside the replay panel — and
 * threading it up through a shell to a component no page renders is a
 * lot of edits for one string.
 *
 * **Not persisted.** ``decisionTabStore`` keeps its value in
 * `localStorage` because which tab somebody reads first is a preference
 * that outlives a page. This is the opposite: a selection that survived
 * a reload would attach the next question to an episode chosen before
 * it, and the reader would have no way to see that had happened.
 *
 * Cleared when the page that owns it unmounts, for the same reason.
 */

import { useSyncExternalStore } from "react";

export interface EpisodeSelection {
  runId: string;
  episodeContextId: string;
}

const EMPTY: EpisodeSelection = { runId: "", episodeContextId: "" };

let current: EpisodeSelection = EMPTY;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Publish the episode a reader chose. Called only from `chooseEpisode`.
 *
 * Never called with the episode the replay opened on: that one is a
 * default so the canvases are not blank, and nobody pointed at it.
 */
export function setEpisodeSelection(next: EpisodeSelection): void {
  if (next.runId === current.runId && next.episodeContextId === current.episodeContextId) return;
  current = next;
  emit();
}

export function clearEpisodeSelection(): void {
  setEpisodeSelection(EMPTY);
}

export function getEpisodeSelection(): EpisodeSelection {
  return current;
}

export function subscribeEpisodeSelection(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The selection, or an empty one — never the replay's own default. */
export function useEpisodeSelection(): EpisodeSelection {
  return useSyncExternalStore(
    subscribeEpisodeSelection,
    getEpisodeSelection,
    () => EMPTY,
  );
}

/** The episode to attach to a question asked on this run, if any.
 *
 * Returns `""` when the selection belongs to a different run, which is
 * what happens for the moment between walking to a new run's page and
 * choosing an episode on it: the id is still the old page's, and
 * attaching it would put the model in front of the wrong record.
 */
export function episodeForRun(runId: string, selection: EpisodeSelection): string {
  if (!runId || selection.runId !== runId) return "";
  return selection.episodeContextId;
}
