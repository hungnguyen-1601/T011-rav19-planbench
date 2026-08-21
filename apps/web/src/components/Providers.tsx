"use client";

/** Locale and theme, wrapped around the whole app.
 *
 * The locale arrives from the server, which read the cookie while
 * rendering. That is the point: if the provider decided it on the client
 * instead, the server would have rendered English and the browser would
 * repaint in Vietnamese a frame later, on every single page load.
 *
 * After the user changes it, the client store is ahead of whatever the
 * server sent, so the store wins from that moment on.
 */

import { useEffect } from "react";

import { LocaleContext, localeStore, type Locale } from "@/lib/i18n";
import { applyTheme, themeStore, watchSystemTheme } from "@/lib/theme";
import { CrumbOverrideProvider } from "@/lib/crumbOverride";
import { usePersisted } from "@/lib/persisted";

export function Providers({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: React.ReactNode;
}) {
  const stored = usePersisted(localeStore);
  // `usePersisted` returns the store's fallback during the server
  // render and on the very first client render, so trust the server's
  // value until the store has actually seen something different.
  const locale = stored === localeStore.fallback ? initialLocale : stored;

  useEffect(() => {
    // Re-apply on mount: the blocking script already did this before
    // first paint, but a soft navigation into a restored page may not
    // have run it.
    applyTheme(themeStore.get());
    return watchSystemTheme();
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return (
    <LocaleContext.Provider value={locale}>
      {/* Inside the locale provider, because the breadcrumb it feeds is
          rendered by `TopBar` and a page cannot pass a prop upward to
          something the root layout mounted above it. */}
      <CrumbOverrideProvider>{children}</CrumbOverrideProvider>
    </LocaleContext.Provider>
  );
}
