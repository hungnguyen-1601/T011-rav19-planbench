/** What stands in the article's place while its chunk arrives.
 *
 * Given a height rather than left to collapse: an empty box that grows
 * when the text lands pushes the whole page down under the reader, and
 * the sidebar and heading are already painted by then.
 */
export function ArticleSkeleton() {
  return (
    <div className="guide-skeleton" aria-hidden="true">
      {[...Array(6)].map((_, index) => (
        <div key={index} className="guide-skeleton-line" />
      ))}
    </div>
  );
}
