/** One anchored part of an article.
 *
 * The `id` is what `/guide/operation#buoc-3-deployment` lands on, and it
 * is written by the author rather than slugified from the title — the
 * title differs by language and the id must not. A test pins every id
 * here against the manifest, in both files.
 */
import type { ReactNode } from "react";

export function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="guide-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
