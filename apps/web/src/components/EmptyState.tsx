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
  secondaryActionHref,
  secondaryActionLabel,
  secondaryActionOnClick,
}: {
  icon?: IconName;
  title: string;
  body?: string;
  actionHref?: string;
  actionLabel?: string;
  secondaryActionHref?: string;
  secondaryActionLabel?: string;
  secondaryActionOnClick?: () => void;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon" aria-hidden="true">
        <Icon name={icon} size={19} />
      </span>
      <strong>{title}</strong>
      {body ? <p>{body}</p> : null}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center", marginTop: 8 }}>
        {actionHref && actionLabel ? (
          <Link className="quick-action primary" href={actionHref}>
            {actionLabel}
          </Link>
        ) : null}
        {secondaryActionHref && secondaryActionLabel ? (
          <Link className="quick-action" href={secondaryActionHref}>
            {secondaryActionLabel}
          </Link>
        ) : secondaryActionOnClick && secondaryActionLabel ? (
          <button type="button" className="secondary" onClick={secondaryActionOnClick}>
            {secondaryActionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
