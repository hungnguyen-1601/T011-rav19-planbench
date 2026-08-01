"use client";

/** Light, dark and system, without a flash of the wrong one.
 *
 * The flash is the whole difficulty. React cannot help: by the time it
 * hydrates, the browser has already painted. So the resolved theme is
 * stamped onto `<html data-theme>` by a blocking script in `<head>`
 * (see `THEME_SCRIPT`), and every colour in the stylesheet keys off that
 * attribute. The React store below only drives the switcher UI and
 * writes the preference — the paint is already correct before it runs.
 *
 * Three values, two of which are colours and one of which is a rule:
 * `light` and `dark` pin the theme, `system` follows the OS and keeps
 * following it, so a laptop that dims at sunset dims this too.
 */

import { createPersistedStore, usePersisted } from "./persisted";
import { THEME_STORAGE_KEY } from "./theme-script";

// Re-exported so callers keep one import for everything theme-shaped.
// The definitions live in `theme-script.ts` because the root layout is a
// server component and cannot import from a `"use client"` module.
export { THEME_SCRIPT, THEME_STORAGE_KEY } from "./theme-script";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_PREFERENCES: readonly ThemePreference[] = ["light", "dark", "system"];

/** What `system` means right now. Pure, so it is testable without a DOM. */
export function resolveTheme(
  preference: ThemePreference,
  systemPrefersDark: boolean,
): ResolvedTheme {
  if (preference === "system") return systemPrefersDark ? "dark" : "light";
  return preference;
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Stamp `<html>` so the stylesheet — and the next paint — agree. */
export function applyTheme(preference: ThemePreference): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = resolveTheme(preference, systemPrefersDark());
  // Kept separately so the switcher can show "System" rather than
  // whichever colour system currently means.
  root.dataset.themePref = preference;
  // Tells the browser to render native widgets (scrollbars, date
  // pickers, form controls) to match.
  root.style.colorScheme = root.dataset.theme;
}

export const themeStore = createPersistedStore<ThemePreference>({
  key: THEME_STORAGE_KEY,
  fallback: "system",
  allowed: THEME_PREFERENCES,
  backend: "local",
  onChange: applyTheme,
});

export function useThemePreference(): ThemePreference {
  return usePersisted(themeStore);
}

/**
 * Keep `system` honest: re-resolve when the OS flips.
 *
 * Without this, choosing `system` would mean "whatever the OS said when
 * this tab opened", which is not what the word means.
 */
export function watchSystemTheme(): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => applyTheme(themeStore.get());
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

// Duplicated from `sidebar.ts` rather than imported: this string is
// built at module load and must not pull that module into the critical
// path. `sidebar.test.ts` asserts the two spellings still match.
const SIDEBAR_STORAGE_KEY = "planbench.sidebar";
