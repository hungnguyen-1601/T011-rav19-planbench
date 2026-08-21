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
 */

/** Rows per page. Fixed rather than a preference: the point is that the
 *  table stops growing with the run. */
export const EPISODES_PER_PAGE = 5;

/** Page numbers are 0-based. Always at least one page, so an empty list
 *  is "page 1 of 1 with nothing on it" rather than "page 1 of 0". */
export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / EPISODES_PER_PAGE));
}

/** Which page holds the row at `index`. */
export function pageOf(index: number): number {
  return index < 0 ? 0 : Math.floor(index / EPISODES_PER_PAGE);
}

export function clampPage(page: number, total: number): number {
  return Math.max(0, Math.min(page, pageCount(total) - 1));
}

export function pageSlice<T>(items: readonly T[], page: number): T[] {
  const start = clampPage(page, items.length) * EPISODES_PER_PAGE;
  return items.slice(start, start + EPISODES_PER_PAGE);
}

/** The page numbers the strip should offer, at most `span` of them.
 *
 * Keeps a constant width wherever it sits: near either end the window
 * stops sliding and fills inward instead, so the control does not
 * change size as the reader moves through it.
 */
export function pageWindow(page: number, total: number, span = 7): number[] {
  const count = pageCount(total);
  const width = Math.min(span, count);
  const current = clampPage(page, total);
  const first = Math.max(0, Math.min(current - Math.floor(width / 2), count - width));
  return Array.from({ length: width }, (_, offset) => first + offset);
}
