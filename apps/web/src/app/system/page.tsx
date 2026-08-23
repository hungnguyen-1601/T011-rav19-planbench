"use client";

/** System information — where the backend URL and versions went.
 *
 * They were on the dashboard, in a card larger than anything a user
 * could act on. Here they are one table, on a page nobody lands on by
 * accident.
 *
 * The API base URL is shown **in development only**. In production it
 * tells a stranger which host to point a scanner at, and tells the
 * operator nothing they did not configure themselves. Everything else
 * here is deliberately dull: no keys, no tokens, no stack traces.
 */

import { useCallback, useEffect, useState } from "react";

import { Icon } from "@/components/Icon";
import { SystemStatus, type StatusValue } from "@/components/SystemStatus";
import { API_BASE, api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

/** Kept in step with apps/web/package.json. */
const FRONTEND_VERSION = "0.1.0";

const IS_DEVELOPMENT = process.env.NODE_ENV !== "production";

export default function SystemPage() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<{ status: string; version: string } | null>(null);
  const [status, setStatus] = useState<StatusValue>("checking");

  const check = useCallback(() => {
    setStatus("checking");
    api
      .health()
      .then((result) => {
        setHealth(result);
        setStatus("online");
      })
      .catch(() => {
        setHealth(null);
        setStatus("offline");
      });
  }, []);

  useEffect(check, [check]);

  const rows: { label: string; value: React.ReactNode }[] = [
    { label: t("system.frontendVersion"), value: <code>{FRONTEND_VERSION}</code> },
    {
      label: t("system.backendVersion"),
      value: health ? <code>{health.version}</code> : <span className="muted">—</span>,
    },
    {
      label: t("system.apiStatus"),
      value: <SystemStatus status={status} onRetry={check} />,
    },
    {
      label: t("system.apiBase"),
      value: IS_DEVELOPMENT ? (
        <code>{API_BASE}</code>
      ) : (
        <span className="muted">{t("system.hiddenInProduction")}</span>
      ),
    },
    {
      label: t("system.environment"),
      value: <code>{IS_DEVELOPMENT ? "development" : "production"}</code>,
    },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("system.title")}</h2>
          <p>{t("system.subtitle")}</p>
          {/* What the tagline used to say from the top of the rail, on
              every page, forever. It is a sentence about the product —
              read once — so it belongs on the page a reader opens when
              they want to know what the product is. */}
          <p className="muted">{t("app.tagline")}</p>
        </div>
        <button type="button" className="icon-button" onClick={check} aria-label={t("common.refresh")} data-tooltip={t("common.refresh")}>
          <Icon name="refresh" />
        </button>
      </div>

      <div className="panel" style={{ maxWidth: 620 }}>
        <table>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td className="muted" style={{ width: "45%" }}>
                  {row.label}
                </td>
                <td>{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted" style={{ fontSize: 12, marginBottom: 0, marginTop: 12 }}>
          {t("system.note")}
        </p>
      </div>
    </>
  );
}
