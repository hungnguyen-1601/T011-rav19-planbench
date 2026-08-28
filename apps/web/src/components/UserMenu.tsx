"use client";

/** Who is signed in, and the way out.
 *
 * Signed out it is a plain "Sign in" link rather than a disabled avatar:
 * an empty account menu is a dead end, and the brief was explicit that
 * an account card must not be faked for a visitor who has none.
 */

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { clearSession, type SessionUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { useDismiss } from "@/lib/useDismiss";

/** Which badges to show, in a stable order.
 *
 * `demo_owner` replaces the rest rather than joining them: it *is* every
 * capability, so listing it beside three business packages would read as
 * four jobs when it is one exception.
 */
function roleBadges(user: SessionUser): string[] {
  const roles = user.roles ?? [];
  if (roles.includes("demo_owner")) return ["demo_owner"];
  return ["engineer", "reviewer", "admin"].filter((role) => roles.includes(role));
}

export function UserMenu({ user }: { user: SessionUser | null }) {
  const { t } = useTranslation();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    trigger.current?.focus();
  }, []);
  useDismiss(open, close, wrap);

  if (!user) {
    return (
      <Link className="quick-action primary" href="/login">
        <Icon name="user" size={15} />
        {t("topbar.signIn")}
      </Link>
    );
  }

  const name = user.nickname || user.display_name || user.email;

  return (
    <div className="menu-wrap" ref={wrap}>
      <button
        ref={trigger}
        type="button"
        className="icon-button"
        aria-label={t("topbar.account")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <Avatar user={user} size={24} />
        <span className="icon-button-label">{name}</span>
        <Icon name="chevronDown" size={14} />
      </button>

      {open ? (
        <div className="menu" role="menu" aria-label={t("topbar.account")}>
          <div className="menu-heading">
            <div className="muted" style={{ fontSize: 11 }}>
              {t("topbar.signedInAs")}
            </div>
            <div style={{ fontWeight: 600 }}>
              {name}
              {/* Every package, not only the administrator one. Somebody
                  holding two roles is doing two jobs, and a badge that
                  showed one of them would make the other invisible —
                  including to them, when they wonder why a button is
                  there. A demo owner shows that name alone: it is not a
                  third role beside the others, it is the whole set. */}
              {roleBadges(user).map((role) => (
                <span
                  key={role}
                  className={`badge ${role === "demo_owner" ? "warn" : ""}`}
                  style={{ marginLeft: 6 }}
                >
                  {t(`topbar.role.${role}`)}
                </span>
              ))}
            </div>
            {user.email ? (
              <div className="muted session-email" style={{ fontSize: 11, maxWidth: "22ch" }}>
                {user.email}
              </div>
            ) : null}
          </div>

          <Link className="menu-item" role="menuitem" href="/reviews" onClick={close}>
            <Icon name="inbox" size={15} />
            {t("nav.reviews")}
          </Link>
          <Link className="menu-item" role="menuitem" href="/system" onClick={close}>
            <Icon name="info" size={15} />
            {t("nav.system")}
          </Link>
          <button
            type="button"
            role="menuitem"
            className="menu-item"
            onClick={() => {
              clearSession();
              setOpen(false);
              router.push("/login");
            }}
          >
            <Icon name="logout" size={15} />
            {t("topbar.signOut")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
