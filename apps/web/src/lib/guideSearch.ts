/** Matching what the reader typed against the guide's headings.
 *
 * Titles only — articles, their sections and their tabs. Not the prose:
 * that needs an index built at compile time, and an index built from
 * text still being written is an index that is wrong every day. What
 * this does answer is the question people actually arrive with — *which
 * article talks about G2* — and the empty state says plainly that the
 * body is not searched and `Ctrl+F` inside an article is.
 *
 * **Diacritic-insensitive, both ways.** Vietnamese is routinely typed
 * without tones, so `khai` has to find *Khai deployment*; and a reader
 * on an English keyboard types `deployment` for the same heading. The
 * fold is applied to the query and the title alike, so neither side has
 * to be spelled the way the other was.
 */

/** Lowercase, strip tone marks, and flatten đ/Đ.
 *
 * `normalize("NFD")` splits a letter from its tone so the combining
 * marks can be dropped, but `đ` is a letter in its own right rather
 * than `d` plus a mark — NFD leaves it whole, and a reader typing `do`
 * for `đo` would find nothing.
 */
export function fold(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .trim();
}

export interface SearchTarget {
  /** Where selecting this result goes. */
  href: string;
  /** Shown as the result. Already in the reader's language. */
  title: string;
  /** The article it belongs to, when the result is a section or a tab. */
  context?: string;
}

export function matches(target: SearchTarget, query: string): boolean {
  const needle = fold(query);
  if (!needle) return true;
  return fold(target.title).includes(needle) || fold(target.context ?? "").includes(needle);
}

export function search(targets: readonly SearchTarget[], query: string): SearchTarget[] {
  return targets.filter((target) => matches(target, query));
}
