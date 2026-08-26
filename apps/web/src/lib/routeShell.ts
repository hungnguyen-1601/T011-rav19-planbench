/** The one shell a dynamic route is exported as, and how to read the
 *  real id back out of the URL.
 *
 * A static export writes one file per route it can name. `/decisions/<id>`
 * cannot be named at build time: the ids belong to records the user has
 * not created yet. So each dynamic route is exported once, under the
 * sentinel id below, and the API serves that one file for every id —
 * see `DYNAMIC_ROUTES` and `SENTINEL` in
 * `apps/api/planbench_api/static_site.py`, which must agree with this
 * value.
 *
 * Deliberately **not** a `"use client"` module. `generateStaticParams`
 * runs on the server, and a server component that imports from the
 * client graph gets a module reference rather than the string — a page
 * that builds and then exports the wrong directory name. The hook that
 * consumes the same constant is in `useRouteId.ts`, which is a client
 * module and imports *this* one, not the other way round.
 */

/** The id every dynamic route's shell is built under. */
export const ROUTE_ID_SENTINEL = "_";

/** What `generateStaticParams` returns for a shell-only dynamic route. */
export function shellParams(): { id: string }[] {
  return [{ id: ROUTE_ID_SENTINEL }];
}

/**
 * The last segment of a path, which for these routes is the record id.
 *
 * Only needed when the router says the id is the sentinel — that is, the
 * page was served from its shell because the browser asked the server
 * for a file that was never written (a reload, or a pasted link). On a
 * client-side navigation the router has the real id already.
 *
 * Query and hash are stripped so a pasted `?tab=gates` does not become
 * part of the id, and a trailing slash is ignored because the export can
 * be served either way.
 */
export function routeIdFromPathname(pathname: string): string {
  const path = pathname.split("?")[0].split("#")[0];
  const segments = path.split("/").filter((segment) => segment !== "");
  const last = segments[segments.length - 1] ?? "";
  return decodeURIComponent(last);
}
