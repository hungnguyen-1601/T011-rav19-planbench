"use client";

/** Which article module belongs to which slug, in which language.
 *
 * Two properties this file exists to hold, both easy to lose by accident:
 *
 * **`dynamic()` is called once, here, at module scope.** Calling it while
 * rendering builds a *new component type* on every render, so React
 * unmounts the article and mounts a different one — the skeleton flashes
 * back on each parent render, and Next has no stable import to attach a
 * preload to.
 *
 * **The paths are written out.** `import(\`./${locale}/${slug}.mdx\`)`
 * would compile, and would hand the bundler a directory rather than a
 * file: it then packs every article of both languages into one chunk, so
 * opening one page downloads all twenty-two. Spelling each path is what
 * keeps the reader's browser fetching only the article they asked for, in
 * the language they read. Both languages are *in the build output* — that
 * is unavoidable and fine; what matters is what the browser fetches.
 */

import dynamic from "next/dynamic";
import type { ComponentType } from "react";

import { ArticleSkeleton } from "@/components/guide/ArticleSkeleton";
import type { Locale } from "@/lib/i18n/shared";

/** `ssr: false` on purpose.
 *
 * `DEFAULT_LOCALE` is English and the desktop build is a static export,
 * so anything prerendered is prerendered in English. For the short
 * strings elsewhere in the app that costs a blink; for a two-thousand
 * word article it means a Vietnamese reader watches a full screen of
 * English and then sees it replaced. A skeleton the right height, then
 * the right language, is the better trade — and nothing here needs to be
 * in the HTML: the app is behind a sign-in, on a desktop, with no search
 * engine to please.
 *
 * **The options are repeated at every call, and that is not an oversight.**
 * A shared `const options` fails the build outright — *"next/dynamic
 * options must be an object literal"* — because the compiler reads them
 * while building, to decide what to prerender, and it cannot follow a
 * variable to do it. The duplication is the price of the same rule that
 * makes the import paths literal: everything `dynamic()` needs has to be
 * readable without running the file.
 */
export const GUIDE_MODULES = {
  vi: {
    overview: dynamic(() => import("./vi/overview.mdx"), {
      ssr: false,
      loading: ArticleSkeleton,
    }),
  },
  en: {
    overview: dynamic(() => import("./en/overview.mdx"), {
      ssr: false,
      loading: ArticleSkeleton,
    }),
  },
} satisfies Record<Locale, Record<string, ComponentType>>;
