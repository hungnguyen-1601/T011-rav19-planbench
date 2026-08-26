"use client";

/** Which half of `/deployments` is on screen.
 *
 * The page carries the same two unrelated jobs the `/decisions` list
 * does — *file a new deployment* and *read the ones on file* — and the
 * filing half is thirty labelled boxes, a map, a mission placer and a
 * traffic editor. The two are stacked, so whichever is second starts
 * below the fold.
 *
 * **Filing is the default here, and that is the opposite of
 * `/decisions`.** Arriving at the list page is arriving to see what
 * happened; arriving at this one is arriving to file something, which is
 * why the form already sat above the table and why the head grew a count
 * badge to answer "how many are on file" without the list being first.
 * The tabs keep that reading and take the scrolling out of it.
 *
 * Its own key, never shared with `planbench.decision-tab` or
 * `planbench.decisions-list-tab`: one slot holding two different sets of
 * ids means each page's remembered choice silently resets the other's,
 * because `allowed` falls an unknown id back to the default.
 */

import { createPersistedStore, usePersisted } from "./persisted";

export type DeploymentsTabId = "create" | "list";

export const DEPLOYMENTS_TAB_IDS: readonly DeploymentsTabId[] = ["create", "list"];

/** Same `planbench.` prefix as the theme, the sidebar and the two
 *  decision tab keys; distinct from every one of them. */
export const DEPLOYMENTS_TAB_STORAGE_KEY = "planbench.deployments-tab";

export const deploymentsTabStore = createPersistedStore<DeploymentsTabId>({
  key: DEPLOYMENTS_TAB_STORAGE_KEY,
  fallback: "create",
  allowed: DEPLOYMENTS_TAB_IDS,
  backend: "local",
});

export function useDeploymentsTab(): DeploymentsTabId {
  return usePersisted(deploymentsTabStore);
}
