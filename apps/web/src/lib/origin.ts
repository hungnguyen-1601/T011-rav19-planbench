/** Where the backend is. One value, imported by everything that calls it.
 *
 * **Why this is its own module.** It used to live in `api.ts`, which
 * `auth.ts` imported for it. That was fine only while `api.ts` needed
 * nothing from `auth.ts` — and the moment it needed the session token,
 * the two would have imported each other. ESM tolerates a cycle, but the
 * order in which the two modules finish initialising then depends on
 * which one the bundler reaches first, and a `const` read during that
 * window is `undefined` rather than an error. Splitting the one value
 * they share removes the question.
 *
 * The comment below is the original, kept because the reasoning it
 * records is still the reason for the fallback chain.
 */

/**
 * `NEXT_PUBLIC_API_URL` still wins and is still baked in at build time —
 * Docker passes it as a build arg, `scripts/dev_stack.sh` exports it,
 * and `.env.development` sets it for `next dev`, so none of those change
 * behaviour.
 *
 * The fallback is the page's own origin rather than a fixed port,
 * because the desktop build has no fixed port: the API picks a free one
 * at startup and serves the exported UI from the same process, so the
 * origin the page was loaded from *is* the API. Falling back to a
 * literal `localhost:8000` there would send every request to whatever
 * happened to be on 8000, or to nothing.
 *
 * `window` is guarded because this module is also evaluated while the
 * export is being prerendered, in Node, where there is no location — and
 * nothing fetches during a prerender, so the value used there only has
 * to be a legal URL.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
