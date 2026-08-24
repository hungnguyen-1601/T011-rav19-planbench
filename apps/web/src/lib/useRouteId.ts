"use client";

/** The record id of a dynamic route, whichever way the page was reached.
 *
 * Two ways in, and they do not agree:
 *
 * - **Client-side navigation.** The router has the real id, `useParams`
 *   returns it, and there is nothing to work out.
 * - **A reload or a pasted link.** The browser asked for a file the
 *   export never wrote, so the API answered with the route's shell —
 *   built under `ROUTE_ID_SENTINEL`. `useParams` therefore says `_`, and
 *   the only place the real id survives is the address bar.
 *
 * The address bar is read in an effect, never during render. The
 * prerendered HTML was produced with the sentinel; reading `location`
 * while rendering would make the first client render disagree with the
 * file it is hydrating, and React answers a mismatch by discarding the
 * whole tree and rendering it again from scratch.
 *
 * Until that effect has run the hook returns `""` rather than the
 * sentinel, so a page can guard its fetch with `if (!id) return;` and
 * never asks the API for a record called `_`. An empty id and the
 * sentinel render identically — neither has data yet — so nothing about
 * the hydrated markup changes.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { ROUTE_ID_SENTINEL, routeIdFromPathname } from "./routeShell";

export function useRouteId(): string {
  const params = useParams<{ id: string }>();
  const routed = params?.id ?? "";
  const servedFromShell = routed === ROUTE_ID_SENTINEL;
  const [fromLocation, setFromLocation] = useState("");

  useEffect(() => {
    if (!servedFromShell) return;
    setFromLocation(routeIdFromPathname(window.location.pathname));
  }, [servedFromShell]);

  return servedFromShell ? fromLocation : routed;
}
