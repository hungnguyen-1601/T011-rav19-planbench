import type { Metadata } from "next";
import localFont from "next/font/local";
import { cookies } from "next/headers";

import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/Providers";
// Both from non-client modules: a server component cannot call into
// the client graph, and Next only says so at runtime.
import { LOCALE_COOKIE, localeFromCookie } from "@/lib/i18n/shared";
import { THEME_SCRIPT } from "@/lib/theme-script";
import "./globals.css";

/**
 * The two faces, loaded from files in the repo rather than fetched.
 *
 * **`next/font/local`, not `next/font/google`.** The Google loader
 * downloads at *build* time and self-hosts afterwards, so the runtime is
 * offline-safe either way — but `next build` itself then needs the
 * network, and no CSS fallback can rescue a build that produced no CSS.
 * A demo build has to be reproducible on a machine with none.
 *
 * `display: "swap"`: text paints in the fallback immediately and swaps
 * when the face arrives. The alternative is a blank paragraph for as
 * long as the font takes, which on a slow connection is a page that
 * looks broken rather than a page that looks plain.
 *
 * Only the weights the stylesheet asks for. Provenance, licences and
 * SHA-256 for every file are in `fonts/README.md`.
 */
const sans = localFont({
  src: [
    { path: "./fonts/BeVietnamPro-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/BeVietnamPro-Medium.woff2", weight: "500", style: "normal" },
    { path: "./fonts/BeVietnamPro-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "./fonts/BeVietnamPro-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-sans-loaded",
  display: "swap",
});

const mono = localFont({
  src: [
    { path: "./fonts/JetBrainsMono-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/JetBrainsMono-Medium.woff2", weight: "500", style: "normal" },
    { path: "./fonts/JetBrainsMono-SemiBold.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-mono-loaded",
  display: "swap",
});

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
    // The two font variables land on <html> so `globals.css` can alias
    // its public tokens to them. Nothing reads `--font-*-loaded`
    // directly — see the alias in the stylesheet.
    <html lang={locale} className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
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
