/** One number, with what it counts and where to go to see it.
 *
 * `null` renders as an em dash, not as zero. "We could not load this"
 * and "there are none" look identical on a stat card and mean opposite
 * things — a dashboard that quietly shows 0 for a failed request is
 * worse than one that admits it does not know.
 */

import Link from "next/link";

import { Icon, type IconName } from "./Icon";

export function StatCard({
  label,
  value,
  hint,
  icon,
  href,
  loading = false,
}: {
  label: string;
  value: number | null;
  hint?: string;
  icon: IconName;
  href?: string;
  loading?: boolean;
}) {
  const body = (
    <>
      <span className="stat-card-head">
        <Icon name={icon} size={15} />
        {label}
      </span>
      {loading ? (
        <span className="skeleton" style={{ height: 30, width: 56 }} aria-hidden="true" />
      ) : value === null ? (
        <span className="stat-card-value unknown" title={hint}>
          —
        </span>
      ) : (
        <span className="stat-card-value">{value}</span>
      )}
      {hint ? <span className="stat-card-hint">{hint}</span> : null}
    </>
  );

  if (href) {
    return (
      <Link className="stat-card" href={href}>
        {body}
      </Link>
    );
  }
  return <div className="stat-card">{body}</div>;
}
