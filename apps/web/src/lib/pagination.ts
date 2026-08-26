"use client";

/** Paging a list that has already been filtered, decided apart from the markup.
 *
 * Two pages want the same control — the comparison runs on
 * `/decisions` and the deployments on `/deployments` — so the
 * arithmetic is written once here and drawn once in
 * `components/Pager`. The alternative is two pagers that disagree about
 * what "page 1 of 0" means.
 *
 * **Filter first, then page.** The order matters and it is the thing
 * most easily got backwards: paging the raw list and filtering the page
 * would give a "10 per page" table showing three rows, and a result
 * count that changes meaning depending on which page you are standing
 * on. Every function here therefore takes the list the reader can
 * actually see, and the count beside the pager is that list's length —
 * never the page's.
 *
 * **A changed filter is a changed list, and a changed list starts at
 * page 1.** Leaving the page number alone across a filter change is how
 * a reader on page 7 of 12 turns on "ranked only" and gets a blank
 * table that reads as "no runs" — the exact reading this platform's
 * list page exists to prevent. `usePagination` takes a `resetKey` for
 * that, and the rule is a pure function so it can be tested without a
 * browser.
 *
 * Page numbers are **0-based** in this module and rendered 1-based, the
 * same split `lib/episodePages` already used.
 */

import { useState } from "react";

/** Ten rows a page, for both lists that use this.
 *
 * Fixed rather than a preference: the point of paging is that the table
 * stops growing with the platform, and a reader who can set it to 500
 * has un-fixed exactly that. */
export const DEFAULT_PER_PAGE = 10;

/** Always at least one page, so an empty list is "page 1 of 1 with
 *  nothing on it" rather than "page 1 of 0". */
export function pageCount(total: number, perPage: number = DEFAULT_PER_PAGE): number {
  return Math.max(1, Math.ceil(total / Math.max(1, perPage)));
}

/** Which page holds the row at `index`. */
export function pageOf(index: number, perPage: number = DEFAULT_PER_PAGE): number {
  return index < 0 ? 0 : Math.floor(index / Math.max(1, perPage));
}

export function clampPage(
  page: number,
  total: number,
  perPage: number = DEFAULT_PER_PAGE,
): number {
  return Math.max(0, Math.min(page, pageCount(total, perPage) - 1));
}

export function pageSlice<T>(
  items: readonly T[],
  page: number,
  perPage: number = DEFAULT_PER_PAGE,
): T[] {
  const size = Math.max(1, perPage);
  const start = clampPage(page, items.length, size) * size;
  return items.slice(start, start + size);
}

/** The page numbers a numbered strip should offer, at most `span`.
 *
 * Keeps a constant width wherever it sits: near either end the window
 * stops sliding and fills inward instead, so the control does not
 * change size as the reader moves through it.
 */
export function pageWindow(
  page: number,
  total: number,
  perPage: number = DEFAULT_PER_PAGE,
  span = 7,
): number[] {
  const count = pageCount(total, perPage);
  const width = Math.min(span, count);
  const current = clampPage(page, total, perPage);
  const first = Math.max(0, Math.min(current - Math.floor(width / 2), count - width));
  return Array.from({ length: width }, (_, offset) => first + offset);
}

/** What the pager remembers: a page, and which list it was a page *of*. */
export interface PagerState {
  page: number;
  key: string;
}

/** The state a pager should hold once the list it pages has changed.
 *
 * Returns the remembered state unchanged when the key still matches —
 * identity matters, because `usePagination` compares by reference to
 * decide whether it has anything to write back.
 */
export function pagerStateFor(remembered: PagerState, key: string): PagerState {
  return remembered.key === key ? remembered : { page: 0, key };
}

export interface Pagination<T> {
  /** 0-based. */
  page: number;
  pageCount: number;
  /** The rows for the current page. */
  visible: T[];
  /** Everything that survived the filter — what "N results" counts. */
  total: number;
  setPage: (page: number) => void;
}

/** Page an already-filtered list.
 *
 * `resetKey` is whatever describes *which* list this is — on
 * `/decisions` it is the three filter selections joined together. When
 * it changes, the page goes back to the first one during the same
 * render rather than in an effect: an effect would paint one frame of
 * page 7 against the new list before correcting itself, and that frame
 * is the blank table this rule exists to prevent.
 */
export function usePagination<T>(
  items: readonly T[],
  options: { perPage?: number; resetKey?: string } = {},
): Pagination<T> {
  const { perPage = DEFAULT_PER_PAGE, resetKey = "" } = options;
  const [remembered, setRemembered] = useState<PagerState>({ page: 0, key: resetKey });
  const state = pagerStateFor(remembered, resetKey);
  // React's own "adjust state when a prop changes" pattern: setting
  // state during render of the *same* component re-runs it before
  // anything is committed to the DOM, so nothing paints twice.
  if (state !== remembered) setRemembered(state);

  const page = clampPage(state.page, items.length, perPage);
  return {
    page,
    pageCount: pageCount(items.length, perPage),
    visible: pageSlice(items, page, perPage),
    total: items.length,
    setPage: (next: number) =>
      setRemembered({ page: clampPage(next, items.length, perPage), key: resetKey }),
  };
}
