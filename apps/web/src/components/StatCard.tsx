/** One number, with what it counts and where to go to see it.
 *
 * `null` renders as an em dash, not as zero. "We could not load this"
 * and "there are none" look identical on a stat card and mean opposite
 * things — a dashboard that quietly shows 0 for a failed request is
 * worse than one that admits it does not know.
 */

import Link from "next/link";

import { Icon, type IconName } from "./Icon";

export type StatCardVariant =
  | "comparison"
  | "ranked"
  | "accepted"
  | "pending"
  | "scenario"
  | "candidate"
  | "simulation";

export function StatCard({
  label,
  value,
  hint,
  icon,
  href,
  loading = false,
  variant = "comparison",
}: {
  label: string;
  value: number | null;
  hint?: string;
  icon: IconName;
  href?: string;
  loading?: boolean;
  variant?: StatCardVariant;
}) {
  const valueState = value === 0 ? "is-zero" : value === null ? "is-unknown" : "has-value";
  const attention = variant === "pending" && value !== null && value > 0;
  const className = `stat-card stat-card--${variant} ${valueState}${attention ? " needs-attention" : ""}`;
  const body = (
    <>
      <span className="stat-card-head">
        <span className="stat-card-icon" aria-hidden="true">
          <Icon name={icon} size={18} />
        </span>
        <span className="stat-card-label">{label}</span>
        {attention ? <span className="stat-card-alert-dot" aria-hidden="true" /> : null}
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
      <Link className={className} href={href}>
        {body}
      </Link>
    );
  }
  return <div className={className}>{body}</div>;
}
