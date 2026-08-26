"use client";

/** Which section of a decision page is on screen, and how it is remembered.
 *
 * The detail page used to print every panel one under the other, which
 * on an ordinary run is a dozen screens of scrolling. The panels are
 * unchanged — only which of them is visible at a time.
 *
 * **Remembered in `localStorage`, not in the address bar.** Two reasons,
 * and the second is the one that decides it:
 *
 * - The choice is a *reading preference*, the same kind of thing as the
 *   theme and the sidebar, and this repo already has one place where
 *   those live (`lib/persisted`). A second mechanism for the same kind
 *   of value is a second thing to keep working.
 * - A query parameter would have to be written through the router, and
 *   these pages are served from a route shell on reload (see
 *   `useRouteId`) — the address bar is already carrying an id the router
 *   does not know about, and pushing a second parameter onto it is the
 *   part of that arrangement most likely to break.
 *
 * The cost of `localStorage` is that the tab is not in a link somebody
 * can send. Nothing on this page is per-run: "show me the evidence tab"
 * is how one person reads *every* run, so remembering it once for the
 * reader is closer to what is wanted than pinning it to one run's URL.
 */

import { createPersistedStore, usePersisted } from "./persisted";

export type DecisionTabId = "conclusion" | "episode" | "reasoning" | "more";

export const DECISION_TAB_IDS: readonly DecisionTabId[] = [
  "conclusion",
  "episode",
  "reasoning",
  "more",
];

/** Same `planbench.` prefix as the theme and sidebar keys. */
export const DECISION_TAB_STORAGE_KEY = "planbench.decision-tab";

export const decisionTabStore = createPersistedStore<DecisionTabId>({
  key: DECISION_TAB_STORAGE_KEY,
  fallback: "conclusion",
  allowed: DECISION_TAB_IDS,
  backend: "local",
});

export function useDecisionTab(): DecisionTabId {
  return usePersisted(decisionTabStore);
}

/** Where an arrow key moves the selection, or `null` for any other key.
 *
 * Written here rather than inside the component for the reason the rest
 * of this repo's rules are: there is no jsdom, so a decision made inside
 * a `onKeyDown` handler is a decision no test can reach.
 *
 * Wraps at both ends, which is what the ARIA authoring practices
 * describe for a tab list and what a reader pressing → four times
 * expects. `Home` and `End` are the other two keys that pattern names.
 */
export function tabAfterKey(key: string, current: number, count: number): number | null {
  if (count === 0) return null;
  switch (key) {
    case "ArrowRight":
      return (current + 1) % count;
    case "ArrowLeft":
      return (current - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}
