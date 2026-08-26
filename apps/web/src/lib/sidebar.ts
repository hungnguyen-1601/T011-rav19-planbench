"use client";

/** Whether the sidebar is collapsed, remembered across reloads.
 *
 * The state is mirrored onto `<html data-sidebar>` and the *widths live
 * in CSS*, keyed off that attribute. React never sets a pixel value.
 * That is what lets the blocking script in `<head>` apply the collapsed
 * width before the first paint: a user who collapsed the sidebar
 * yesterday does not watch it slide shut on every page load today.
 */

import { createPersistedStore, usePersisted } from "./persisted";
import { SIDEBAR_STORAGE_KEY } from "./theme-script";

// Defined in `theme-script.ts` so the blocking script — which the server
// inlines and which must import nothing — and this module cannot drift.
export { SIDEBAR_STORAGE_KEY } from "./theme-script";

export type SidebarState = "expanded" | "collapsed";

export const SIDEBAR_STATES: readonly SidebarState[] = ["expanded", "collapsed"];

export function applySidebar(state: SidebarState): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (state === "collapsed") root.dataset.sidebar = "collapsed";
  else delete root.dataset.sidebar;
}

export const sidebarStore = createPersistedStore<SidebarState>({
  key: SIDEBAR_STORAGE_KEY,
  fallback: "expanded",
  allowed: SIDEBAR_STATES,
  backend: "local",
  onChange: applySidebar,
});

export function useSidebarState(): SidebarState {
  return usePersisted(sidebarStore);
}

export function toggleSidebar(): void {
  sidebarStore.set(sidebarStore.get() === "collapsed" ? "expanded" : "collapsed");
}
