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
              {user.is_admin ? (
                <span className="badge warn" style={{ marginLeft: 6 }}>
                  {t("topbar.admin")}
                </span>
              ) : null}
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
