import type { Metadata } from "next";
import { cookies } from "next/headers";

import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/Providers";
// Both from non-client modules: a server component cannot call into
// the client graph, and Next only says so at runtime.
import { LOCALE_COOKIE, localeFromCookie } from "@/lib/i18n/shared";
import { THEME_SCRIPT } from "@/lib/theme-script";
import "./globals.css";

export const metadata: Metadata = {
  title: "PlanBench",
  description: "Agentic AI PlanBench — AMR/AGV path & motion planning benchmark",
};

/**
 * The root layout is a *server* component and reads the locale cookie.
 *
 * That is what makes `<html lang>` and the first paint of every string
 * correct, instead of English-then-Vietnamese on every load. The cost is
 * that pages render on demand rather than being prerendered — which
 * costs this app nothing, since every page fetches from the API on mount
 * anyway.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const store = await cookies();
  const locale = localeFromCookie(store.get(LOCALE_COOKIE)?.value);

  return (
    // suppressHydrationWarning covers the attributes the script below
    // adds to <html>, which the server has no way to predict.
    <html lang={locale} suppressHydrationWarning>
      <head>
        {/* Runs before the first paint and stamps the remembered theme
            and sidebar width onto <html>. Without it the page paints
            dark, then flips — exactly the flash the brief ruled out. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <Providers initialLocale={locale}>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
