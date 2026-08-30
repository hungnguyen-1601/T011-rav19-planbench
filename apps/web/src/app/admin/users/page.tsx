"use client";

/** Who has which package, and who gave it to them.
 *
 * **Three packages that do not nest.** Engineer, reviewer and admin are
 * three sets of capabilities, not three rungs of a ladder: a reviewer is
 * not a senior engineer and an administrator is not a senior reviewer.
 * So the control is three independent checkboxes rather than one
 * dropdown, and somebody can hold all three, or exactly one, or — for a
 * dormant account — none.
 *
 * **Every change takes a reason, and the server insists.** This is the
 * table an auditor opens first, and "who gave this person the reviewer
 * package, and why" is a single question. Half of it is not an answer,
 * so the reason box gates the checkboxes rather than sitting beside
 * them.
 *
 * `demo_owner` is shown where somebody holds it and can never be granted
 * from here: it is a deployment profile's concession rather than a job
 * anybody does, and removing it is a runbook.
 */

import { useCallback, useEffect, useState } from "react";

import { CAPABILITIES, can, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  GRANTABLE_ROLES,
  disableAccount,
  enableAccount,
  grantRole,
  listAccounts,
  revokeRole,
  type Account,
} from "@/lib/admin";

function when(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function AdminUsersPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setAccounts(await listAccounts());
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

  const act = async (id: string, work: () => Promise<unknown>) => {
    setBusy(id);
    setFailed(null);
    try {
      await work();
      setReason("");
      await reload();
    } catch (caught) {
      // Includes the refusals that matter most here: revoking the last
      // account able to manage accounts, and granting a role that does
      // not exist. Both are shown verbatim — the server's sentence says
      // which account and which role, and a rewritten one would not.
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  };

  const manages = can(session?.user, CAPABILITIES.userManage);
  const needsReason = !reason.trim();

  if (loading) return <p className="muted">{t("common.loading")}</p>;

  return (
    <section>
      <header className="page-head">
        <h1>{t("admin.users.title")}</h1>
        <p className="muted">{t("admin.users.subtitle")}</p>
      </header>

      {failed ? <div className="error-box">{failed}</div> : null}

      {manages ? (
        <div className="panel">
          <label className="field">
            <span>{t("admin.reason")}</span>
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={t("admin.reasonHint")}
            />
          </label>
          <p className="muted small">{t("admin.reasonNote")}</p>
        </div>
      ) : null}

      <div className="panel">
        <div className="table-scroll wide">
          <table>
            <thead>
              <tr>
                <th>{t("admin.col.account")}</th>
                {GRANTABLE_ROLES.map((role) => (
                  <th key={role}>{t(`topbar.role.${role}`)}</th>
                ))}
                <th>{t("admin.col.signedIn")}</th>
                <th>{t("admin.col.state")}</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => {
                const self = account.id === session?.user.id;
                return (
                  <tr key={account.id} className={account.disabled ? "is-unusable" : undefined}>
                    <td>
                      <strong>{account.nickname}</strong>
                      {account.display_name ? (
                        <div className="muted small">{account.display_name}</div>
                      ) : null}
                      {account.email ? <div className="muted small">{account.email}</div> : null}
                      {/* Shown, never offered. See the module note. */}
                      {account.roles.includes("demo_owner") ? (
                        <div className="badge warn">{t("topbar.role.demo_owner")}</div>
                      ) : null}
                    </td>
                    {GRANTABLE_ROLES.map((role) => {
                      const held = account.roles.includes(role);
                      return (
                        <td key={role}>
                          <input
                            type="checkbox"
                            checked={held}
                            aria-label={`${account.nickname} · ${t(`topbar.role.${role}`)}`}
                            disabled={!manages || needsReason || busy === account.id}
                            onChange={() =>
                              act(account.id, () =>
                                held
                                  ? revokeRole(account.id, role, reason)
                                  : grantRole(account.id, role, reason),
                              )
                            }
                          />
                        </td>
                      );
                    })}
                    <td className="muted small">{when(account.last_sign_in_at)}</td>
                    <td>
                      {account.disabled ? (
                        <span className="badge warn">{t("admin.state.disabled")}</span>
                      ) : (
                        <span className="badge ok">{t("admin.state.active")}</span>
                      )}
                      {manages && !self ? (
                        <div>
                          <button
                            type="button"
                            disabled={needsReason || busy === account.id}
                            onClick={() =>
                              act(account.id, () =>
                                account.disabled
                                  ? enableAccount(account.id, reason)
                                  : disableAccount(account.id, reason),
                              )
                            }
                          >
                            {t(account.disabled ? "admin.enable" : "admin.disable")}
                          </button>
                        </div>
                      ) : null}
                      {/* Disabling yourself is refused rather than
                          offered-and-refused: the button is the only
                          thing standing between an administrator and
                          locking themselves out of their own machine. */}
                      {self ? <div className="muted small">{t("admin.thatIsYou")}</div> : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="muted small">{t("admin.disabledMeaning")}</p>
    </section>
  );
}
