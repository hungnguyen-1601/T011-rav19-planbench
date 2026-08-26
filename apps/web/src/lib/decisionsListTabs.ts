"use client";

/** Which half of the `/decisions` list page is on screen.
 *
 * The list page carries two unrelated jobs in one column: *what has
 * already been measured* — the tallies, the filters and the table of
 * runs — and *start another comparison*, which is a form with two
 * candidate pickers, a scope, a map and an episode count. Neither is a
 * detail of the other, and the launch form is the taller of the two, so
 * the reader who came to read the list met the form first and scrolled
 * past it every time.
 *
 * **The reading half is the default.** Arriving at `/decisions` is
 * arriving to see what happened; queueing a run is a deliberate act, and
 * one click is the right price for it. This also flips the old source
 * order on screen, which is the point of the change.
 *
 * Its own store rather than `lib/decisionTabs`, and its own storage key:
 * that one holds the *detail* page's four sections, and one key for two
 * different sets of ids would mean a reader who left the detail page on
 * "reasoning" opens the list page on a tab that does not exist there —
 * the `allowed` list would fall it back, so the effect is that one
 * page's choice silently resets the other's.
 *
 * Everything else — why `localStorage` rather than the address bar, and
 * why the arrow-key rule lives in a module — is argued in
 * `lib/decisionTabs`, and the same reasons hold here.
 */

import { createPersistedStore, usePersisted } from "./persisted";

export type DecisionsListTabId = "overview" | "launch";

export const DECISIONS_LIST_TAB_IDS: readonly DecisionsListTabId[] = ["overview", "launch"];

/** Same `planbench.` prefix as the theme and sidebar keys, and distinct
 *  from `planbench.decision-tab`, which is the detail page's. */
export const DECISIONS_LIST_TAB_STORAGE_KEY = "planbench.decisions-list-tab";

export const decisionsListTabStore = createPersistedStore<DecisionsListTabId>({
  key: DECISIONS_LIST_TAB_STORAGE_KEY,
  fallback: "overview",
  allowed: DECISIONS_LIST_TAB_IDS,
  backend: "local",
});

export function useDecisionsListTab(): DecisionsListTabId {
  return usePersisted(decisionsListTabStore);
}
