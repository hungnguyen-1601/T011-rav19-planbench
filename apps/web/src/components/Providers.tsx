"use client";

/** Locale and theme, wrapped around the whole app.
 *
 * The locale used to arrive as a prop from the server, which had read
 * the cookie while rendering. A static export has no server at render
 * time — every page is written at build time, in the default locale — so
 * there is nothing to pass down and the browser is the only place the
 * preference can be read.
 *
 * `localeStore` is that read: it is backed by the same cookie the
 * removed server read looked at, and `usePersisted` deliberately reports
 * the fallback during the prerender *and* during hydration, so the first
 * client render matches the file that was shipped and React does not
 * throw the tree away. The real value lands on the commit right after,
 * which is one frame — and `<html lang>` is already correct before any
 * of this, stamped by `LOCALE_SCRIPT` ahead of the first paint.
 */

import { useEffect } from "react";

import { localeStore, LocaleContext } from "@/lib/i18n";
import { applyTheme, themeStore, watchSystemTheme } from "@/lib/theme";
import { CrumbOverrideProvider } from "@/lib/crumbOverride";
import { usePersisted } from "@/lib/persisted";

export function Providers({ children }: { children: React.ReactNode }) {
  const locale = usePersisted(localeStore);

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
