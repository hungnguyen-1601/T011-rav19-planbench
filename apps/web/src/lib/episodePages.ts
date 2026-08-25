/** Paging the episode table, decided apart from the markup.
 *
 * A warehouse sweep is three hundred episodes. Listed in full the table
 * is the page; listed five at a time with one tab per page it is sixty
 * tabs, which is the same problem wearing a different control. So the
 * strip of page numbers is itself windowed.
 *
 * Three things here are worth being wrong about, and none of them shows
 * up in a screenshot of a run with five episodes:
 *
 * - **Filtering shrinks the list under the reader.** Turning on "only
 *   episodes somebody failed" while on page 7 of 12 can leave two
 *   pages, and page 7 of two is a blank table that looks like a run
 *   with no episodes.
 * - **A selection can be off-page.** Picking an exemplar jumps the
 *   viewer to an episode that may be on page 9; leaving the table on
 *   page 1 highlights nothing and reads as the pick not registering.
 * - **The window at the edges.** A window that slides symmetrically
 *   shows fewer pages near the ends, so the strip changes width as you
 *   move through it.
 *
 * **The arithmetic itself now lives in `lib/pagination`**, which the two
 * list pages also use. What is left here is the one thing that is
 * specific to episodes — that a page of them is five — and the names the
 * detail page already calls. Two copies of "which page holds row *n*"
 * are two copies free to disagree about the empty case, which is the
 * case that produces the blank table above.
 */

import {
  clampPage as clampToPage,
  pageCount as countPages,
  pageOf as pageHolding,
  pageSlice as sliceOfPage,
  pageWindow as windowOfPages,
} from "./pagination";

/** Rows per page. Fixed rather than a preference: the point is that the
 *  table stops growing with the run. */
export const EPISODES_PER_PAGE = 5;

/** Page numbers are 0-based. Always at least one page, so an empty list
 *  is "page 1 of 1 with nothing on it" rather than "page 1 of 0". */
export function pageCount(total: number): number {
  return countPages(total, EPISODES_PER_PAGE);
}

/** Which page holds the row at `index`. */
export function pageOf(index: number): number {
  return pageHolding(index, EPISODES_PER_PAGE);
}

export function clampPage(page: number, total: number): number {
  return clampToPage(page, total, EPISODES_PER_PAGE);
}

export function pageSlice<T>(items: readonly T[], page: number): T[] {
  return sliceOfPage(items, page, EPISODES_PER_PAGE);
}

/** The page numbers the strip should offer, at most `span` of them.
 *
 * Keeps a constant width wherever it sits: near either end the window
 * stops sliding and fills inward instead, so the control does not
 * change size as the reader moves through it.
 */
export function pageWindow(page: number, total: number, span = 7): number[] {
  return windowOfPages(page, total, EPISODES_PER_PAGE, span);
}
