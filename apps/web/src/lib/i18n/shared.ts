/** The parts of i18n that both the server and the browser need.
 *
 * Deliberately **not** a `"use client"` module. The root layout is a
 * server component and has to read the locale cookie while rendering —
 * that is the whole reason there is no flash of the wrong language — and
 * a server component cannot call a function that lives on the client.
 *
 * So dictionaries, lookup and cookie parsing live here, where either
 * side can use them. The store, the context and the hooks live in
 * `./index.ts`, which is client-only because it touches `document`.
 */

import en from "./locales/en.json";
import vi from "./locales/vi.json";

export type Locale = "en" | "vi";
export const LOCALES: readonly Locale[] = ["en", "vi"];
export const LOCALE_COOKIE = "planbench.locale";
export const DEFAULT_LOCALE: Locale = "en";

export type Dictionary = Record<string, string>;
export type Vars = Record<string, string | number>;

export const DICTIONARIES: Record<Locale, Dictionary> = {
  en: en as Dictionary,
  vi: vi as Dictionary,
};

/**
 * Look up `key`, substituting `{placeholders}`.
 *
 * Pure and dictionary-agnostic, so the fallback chain is testable
 * without a browser, a provider, or React.
 */
export function translate(
  dictionary: Dictionary,
  fallback: Dictionary,
  key: string,
  vars?: Vars,
): string {
  const template = dictionary[key] ?? fallback[key] ?? key;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

/** The language to start in when nobody has chosen yet. */
export function detectLocale(candidates: readonly string[] | undefined): Locale {
  for (const candidate of candidates ?? []) {
    // "vi", "vi-VN" and "VI" all mean Vietnamese.
    const base = candidate.toLowerCase().split("-")[0];
    if ((LOCALES as readonly string[]).includes(base)) return base as Locale;
  }
  return DEFAULT_LOCALE;
}

/** Parse the locale out of a cookie value, for the server render. */
export function localeFromCookie(value: string | null | undefined): Locale {
  return value !== null && value !== undefined && (LOCALES as readonly string[]).includes(value)
    ? (value as Locale)
    : DEFAULT_LOCALE;
}
