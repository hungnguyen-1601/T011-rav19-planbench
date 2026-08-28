/** The frame every guide page is read inside: the guide's rail, then the
 *  article.
 *
 * A layout rather than a piece of each page, so moving between articles
 * replaces the article and leaves the rail alone — the reader's place in
 * a list of eleven does not jump on every navigation.
 */

import type { ReactNode } from "react";

import { GuideRail } from "./GuideRail";

export default function GuideLayout({ children }: { children: ReactNode }) {
  return (
    <div className="guide-shell">
      <GuideRail />
      <div className="guide-main">{children}</div>
    </div>
  );
}
