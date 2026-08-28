/** A paragraph the reader must not skim past.
 *
 * Three kinds, and the distinction is about consequence rather than
 * loudness: `note` is context, `trap` is something that will go wrong if
 * ignored, and `missing` is the guide admitting the system does not do
 * this yet. The third exists because a guide inside the product is read
 * as a promise, and the honest half of a promise needs somewhere to
 * live that does not look like decoration.
 */
import type { ReactNode } from "react";

export type CalloutKind = "note" | "trap" | "missing";

export function Callout({
  kind = "note",
  children,
}: {
  kind?: CalloutKind;
  children: ReactNode;
}) {
  return (
    <aside className={`guide-callout guide-callout-${kind}`} data-kind={kind}>
      {children}
    </aside>
  );
}
