/** "There is nothing here yet, and here is what to do about it."
 *
 * Every empty state carries an action, because an empty panel that only
 * says "no data" leaves the reader to guess whether they are looking at
 * a bug, a permission problem, or a page they have not used yet.
 */

import Link from "next/link";

import { Icon, type IconName } from "./Icon";

export function EmptyState({
  icon = "inbox",
  title,
  body,
  actionHref,
  actionLabel,
}: {
  icon?: IconName;
  title: string;
  body?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon" aria-hidden="true">
        <Icon name={icon} size={19} />
      </span>
      <strong>{title}</strong>
      {body ? <p>{body}</p> : null}
      {actionHref && actionLabel ? (
        <Link className="quick-action" href={actionHref} style={{ marginTop: 6 }}>
          {actionLabel}
        </Link>
      ) : null}
    </div>
  );
}
