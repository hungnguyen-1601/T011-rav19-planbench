"use client";

/** Previous, where you are, next. The one pager both list pages use.
 *
 * Deliberately three controls and no numbered strip. The strip in
 * `/decisions/[id]` exists because an exemplar episode can be on page 9
 * and the reader has to be able to *jump* there; nothing on these two
 * lists is addressed by page number, so a row of digits would be a
 * control nobody aims at. What a reader of a list needs is the next ten
 * and the knowledge that there are more.
 *
 * **The buttons say what they do.** A bare `‹` is announced as
 * "left single quotation mark" or as nothing at all, so the arrow is
 * decoration (`aria-hidden`) beside a real word. The same word is on
 * screen: an icon-only pager is also the one that has to be guessed at
 * by anybody who has not used this app before.
 *
 * **Disabled at the ends rather than wrapping.** Wrapping from the last
 * page to the first is indistinguishable, at a glance, from the list
 * having reset itself.
 *
 * `aria-live` on the position, because pressing "next" changes a table
 * the reader is not looking at — without it the only feedback is
 * visual.
 *
 * Nothing is drawn for a single page: a pair of permanently dead
 * buttons under a seven-row table is noise that says "there is more"
 * when there is not.
 */

import { useTranslation } from "@/lib/i18n";

export function Pager({
  page,
  pageCount,
  onPage,
  labelKey,
}: {
  /** 0-based, as everything in `lib/pagination` is. */
  page: number;
  pageCount: number;
  onPage: (page: number) => void;
  /** Translation key naming *which* list this pages, for a screen
   *  reader that meets the control before the table. */
  labelKey: string;
}) {
  const { t } = useTranslation();
  if (pageCount <= 1) return null;
  const first = page <= 0;
  const last = page >= pageCount - 1;
  return (
    <nav className="pager" aria-label={t(labelKey)}>
      <button
        type="button"
        className="pager-step"
        disabled={first}
        onClick={() => onPage(page - 1)}
      >
        <span aria-hidden="true">‹</span>
        {t("pager.previous")}
      </button>
      <span className="pager-position" aria-live="polite">
        {t("pager.pageOf", { page: String(page + 1), total: String(pageCount) })}
      </span>
      <button
        type="button"
        className="pager-step"
        disabled={last}
        onClick={() => onPage(page + 1)}
      >
        {t("pager.next")}
        <span aria-hidden="true">›</span>
      </button>
    </nav>
  );
}
