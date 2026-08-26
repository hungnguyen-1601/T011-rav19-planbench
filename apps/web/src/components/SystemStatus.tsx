"use client";

/** "System online", small.
 *
 * What replaced the BACKEND card. A version number and a base URL told
 * an ordinary user nothing they could act on and told a stranger where
 * the API lives; both now live on /system, and this says the one thing
 * everybody actually wants to know.
 *
 * The state is never colour alone — the words change too, because a red
 * dot and a green dot are the same dot in greyscale.
 */

import { Icon } from "./Icon";
import { useTranslation } from "@/lib/i18n";

export type StatusValue = "online" | "offline" | "checking";

export function SystemStatus({
  status,
  onRetry,
}: {
  status: StatusValue;
  onRetry?: () => void;
}) {
  const { t } = useTranslation();
  const label =
    status === "online"
      ? t("status.online")
      : status === "offline"
        ? t("status.offline")
        : t("status.checking");

  return (
    <span className="system-status">
      <span
        className={`status-dot ${status === "checking" ? "" : status}`}
        aria-hidden="true"
      />
      <span role="status">{label}</span>
      {status === "offline" && onRetry ? (
        <button
          type="button"
          className="icon-button"
          style={{ minWidth: 26, height: 26 }}
          onClick={onRetry}
          aria-label={t("status.retry")}
          data-tooltip={t("status.retry")}
        >
          <Icon name="refresh" size={14} />
        </button>
      ) : null}
    </span>
  );
}
