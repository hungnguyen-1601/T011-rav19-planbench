"use client";

/** Who changed whose access, when, and why.
 *
 * Append-only and ordered by sequence rather than by timestamp. Two acts
 * can share a clock reading, and "who did it first" is exactly the
 * question an audit trail is asked — sorting by a string that ties would
 * make the answer depend on how the rows happened to come back.
 *
 * The **override** column has its own place rather than being left to be
 * spotted in the prose: it marks a break-glass act, one the ordinary
 * rules would have refused, and that is the first thing anybody reading
 * this filters on. Which capability authorised each act is recorded
 * beside it, because roles change and the trail has to keep saying what
 * the actor held at the time rather than what they hold now.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { useTranslation } from "@/lib/i18n";
import { fetchAccountAudit, listAccounts, type Account, type AccountEvent } from "@/lib/admin";

function when(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function AdminAuditPage() {
  const { t } = useTranslation();
  const [events, setEvents] = useState<AccountEvent[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [overridesOnly, setOverridesOnly] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const [trail, people] = await Promise.all([
        fetchAccountAudit(),
        // Only to turn ids into names. A trail that reads
        // "u_8f3a granted a role to u_11c2" is technically complete and
        // practically unreadable.
        listAccounts().catch(() => [] as Account[]),
      ]);
      setEvents(trail);
      setAccounts(people);
      setFailed(null);
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const nameOf = useMemo(() => {
    const byId = new Map(accounts.map((account) => [account.id, account.nickname]));
    // Falls back to the id rather than to "unknown": an account deleted
    // since the act still leaves a trail, and the id is the only handle
    // anybody has on it.
    return (id: string | null) => (id ? (byId.get(id) ?? id) : t("admin.audit.system"));
  }, [accounts, t]);

  if (loading) return <p className="muted">{t("common.loading")}</p>;

  const shown = overridesOnly ? events.filter((event) => event.override) : events;

  return (
    <section>
      <header className="page-head">
        <h1>{t("admin.audit.title")}</h1>
        <p className="muted">{t("admin.audit.subtitle")}</p>
      </header>

      {failed ? <div className="error-box">{failed}</div> : null}

      <div className="toolbar">
        <label>
          <input
            type="checkbox"
            checked={overridesOnly}
            onChange={(event) => setOverridesOnly(event.target.checked)}
          />{" "}
          {t("admin.audit.overridesOnly")}
        </label>
      </div>

      {shown.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon="inbox"
            title={t("admin.audit.empty.title")}
            body={t(overridesOnly ? "admin.audit.empty.overrides" : "admin.audit.empty.body")}
          />
        </div>
      ) : (
        <div className="panel">
          <div className="table-scroll wide">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t("admin.audit.col.when")}</th>
                  <th>{t("admin.audit.col.actor")}</th>
                  <th>{t("admin.audit.col.subject")}</th>
                  <th>{t("admin.audit.col.change")}</th>
                  <th>{t("admin.audit.col.reason")}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((event) => (
                  <tr key={event.sequence}>
                    <td className="muted small">{event.sequence}</td>
                    <td className="muted small">{when(event.created_at)}</td>
                    <td>
                      {nameOf(event.actor_user_id)}
                      {/* What they held at the time, not what they hold
                          now. Roles change; the trail must not. */}
                      <div className="muted small">
                        {event.actor_roles || "—"} · <code>{event.authorized_capability}</code>
                      </div>
                    </td>
                    <td>{nameOf(event.user_id)}</td>
                    <td>
                      <strong>{t(`admin.audit.action.${event.action}`)}</strong>
                      {event.previous || event.new ? (
                        <div className="muted small">
                          {event.previous || "—"} → {event.new || "—"}
                        </div>
                      ) : null}
                      {event.override ? (
                        <span className="badge warn">{t("admin.audit.override")}</span>
                      ) : null}
                    </td>
                    <td className="muted small">{event.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
