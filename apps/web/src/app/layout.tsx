import type { Metadata } from "next";
import localFont from "next/font/local";

import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/Providers";
// All three from non-client modules: a server component cannot call
// into the client graph, and Next only says so at runtime.
import { DEFAULT_LOCALE } from "@/lib/i18n/shared";
import { LOCALE_SCRIPT } from "@/lib/locale-script";
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
 * The root layout renders without reading anything per-request.
 *
 * It used to `await cookies()` for the locale, which made `<html lang>`
 * and the first paint of every string correct on the server. `cookies()`
 * is a dynamic API, and a static export has no request to read it from —
 * so the layout would not build at all. The read moved into
 * `LOCALE_SCRIPT`, which runs before the first paint and stamps `lang`
 * from the same cookie, so the property that mattered on `<html>`
 * survives; the strings themselves are prerendered in the default locale
 * and swapped by `Providers` on hydration.
 *
 * `lang` is therefore the *default* locale here rather than the user's:
 * it is what the prerendered file has to say, and the script corrects it
 * before anybody sees it. `suppressHydrationWarning` on `<html>` already
 * covers the attributes the two scripts add.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning covers the attributes the two scripts
    // below add to <html>, which the prerender has no way to predict.
    // The two font variables land on <html> so `globals.css` can alias
    // its public tokens to them. Nothing reads `--font-*-loaded`
    // directly — see the alias in the stylesheet.
    <html lang={DEFAULT_LOCALE} className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        {/* Runs before the first paint and stamps the remembered theme
            and sidebar width onto <html>. Without it the page paints
            dark, then flips — exactly the flash the brief ruled out. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {/* Same bargain for the language: the export prerendered
            this file with the default locale, so without this the
            document would claim English to every assistive tool
            until React hydrated. */}
        <script dangerouslySetInnerHTML={{ __html: LOCALE_SCRIPT }} />
      </head>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
