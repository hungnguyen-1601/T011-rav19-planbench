"use client";

/** English and Vietnamese in the browser: the store, the context, the hook.
 *
 * The dictionaries and the lookup itself are in `./shared.ts`, which is
 * *not* a client module — the server layout reads the locale cookie
 * while rendering, and that is what removes the flash of the wrong
 * language. Re-exports below are for components, which are all clients.
 *
 * The locale lives in a **cookie**, not localStorage, for the same
 * reason: a cookie is the only preference the server can see while it
 * renders.
 *
 * Missing keys fall back to English rather than throwing or rendering
 * blank: a half-translated screen is usable, an empty one is not.
 */

import { createContext, useContext } from "react";

import {
  DEFAULT_LOCALE,
  DICTIONARIES,
  LOCALES,
  LOCALE_COOKIE,
  localeFromCookie,
  translate,
  type Locale,
  type Vars,
} from "./shared";
import { createPersistedStore, readCookie, usePersisted } from "../persisted";

export {
  DEFAULT_LOCALE,
  DICTIONARIES,
  LOCALES,
  LOCALE_COOKIE,
  detectLocale,
  localeFromCookie,
  translate,
} from "./shared";
export type { Dictionary, Locale, Vars } from "./shared";

export const localeStore = createPersistedStore<Locale>({
  key: LOCALE_COOKIE,
  fallback: DEFAULT_LOCALE,
  allowed: LOCALES,
  backend: "cookie",
  onChange: (locale) => {
    if (typeof document !== "undefined") document.documentElement.lang = locale;
  },
});

/**
 * The locale the server rendered with.
 *
 * Provided by the root layout, which read the cookie. The client store
 * cannot be trusted for the *first* render — it would read the cookie
 * itself and could disagree with the server's HTML — so the context
 * value wins until the user actually changes the language.
 */
export const LocaleContext = createContext<Locale>(DEFAULT_LOCALE);

export interface Translator {
  locale: Locale;
  t: (key: string, vars?: Vars) => string;
}

export function useTranslation(): Translator {
  const locale = useContext(LocaleContext);
  const dictionary = DICTIONARIES[locale] ?? DICTIONARIES[DEFAULT_LOCALE];
  return {
    locale,
    t: (key: string, vars?: Vars) =>
      translate(dictionary, DICTIONARIES[DEFAULT_LOCALE], key, vars),
  };
}

/** Subscribe to locale changes. Only the provider needs this. */
export function useStoredLocale(): Locale {
  return usePersisted(localeStore);
}

/** Read the current locale outside React (before hydration). */
export function currentLocale(): Locale {
  return localeFromCookie(readCookie(LOCALE_COOKIE));
}
