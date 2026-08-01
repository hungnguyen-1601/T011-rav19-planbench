"use client";

/** The review inbox, with a count of what is waiting.
 *
 * The number is in the accessible name, not only in the red circle:
 * "Review inbox, 3 requests waiting" is the whole point of the badge,
 * and a screen reader that only hears "Review inbox" has been told
 * nothing.
 */

import Link from "next/link";

import { Icon } from "./Icon";
import { useTranslation } from "@/lib/i18n";

export function NotificationButton({ pending }: { pending: number }) {
  const { t } = useTranslation();
  const label =
    pending > 0 ? t("topbar.reviewsPending", { count: pending }) : t("topbar.reviewsNone");

  return (
    <Link
      href="/reviews"
      className="icon-button badge-dot"
      aria-label={`${t("topbar.reviews")} — ${label}`}
      data-tooltip={label}
    >
      <Icon name="inbox" />
      {pending > 0 ? (
        <span className="badge-count" aria-hidden="true">
          {pending > 99 ? "99+" : pending}
        </span>
      ) : null}
    </Link>
  );
}
