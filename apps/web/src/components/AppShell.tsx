"use client";

/** The frame every page renders inside.
 *
 * One place owns the sidebar, the top bar and the review count. Pages
 * render their content and nothing else — before this, a page that
 * forgot the shell simply had no navigation, and there was no way to
 * add a control to every page without editing every page.
 *
 * `/login`, `/welcome` and `/auth/callback` are deliberately outside it:
 * a navigation rail full of links that all bounce to sign-in is worse
 * than no rail, and the callback is a redirect that should not paint
 * furniture on its way past.
 */

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { fetchInbox } from "@/lib/reviews";
import { sidebarStore, toggleSidebar, useSidebarState } from "@/lib/sidebar";
import { useDismiss } from "@/lib/useDismiss";

/** Routes that render on their own, without the shell. */
const BARE_ROUTES = ["/login", "/welcome", "/auth/callback"];

function isBare(pathname: string): boolean {
  return BARE_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

/** How often the review badge re-checks. */
const BADGE_INTERVAL_MS = 30_000;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const session = useSession();
  const { t } = useTranslation();
  const collapsed = useSidebarState() === "collapsed";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pending, setPending] = useState(0);

  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  useDismiss(drawerOpen, closeDrawer);

  // Navigating must close the drawer, or the new page arrives behind it.
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  // The body must not scroll behind an open drawer.
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [drawerOpen]);

  // Reflect the remembered collapse onto <html> once on mount. The
  // blocking script already did this for the first paint; this covers a
  // tab that never ran it, e.g. after a client-side navigation from a
  // cached document.
  useEffect(() => {
    sidebarStore.set(sidebarStore.get());
  }, []);

  const userId = session?.user.id ?? "";
  useEffect(() => {
    if (!userId) {
      setPending(0);
      return;
    }
    let cancelled = false;
    const load = () =>
      fetchInbox()
        .then((inbox) => {
          if (!cancelled) setPending(inbox.pending);
        })
        // A failed badge poll is not worth an error message: the
        // Reviews page reports properly if something is really wrong.
        .catch(() => {});
    load();
    const timer = setInterval(load, BADGE_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [userId]);

  if (isBare(pathname)) {
    return <main className="content bare-page">{children}</main>;
  }

  return (
    <div className="layout">
      <a className="skip-link" href="#main-content">
        {t("sidebar.skip")}
      </a>

      <Sidebar
        pathname={pathname}
        collapsed={collapsed}
        mobileOpen={drawerOpen}
        t={t}
        user={session?.user ?? null}
        onToggleCollapse={toggleSidebar}
        onNavigate={closeDrawer}
      />

      {drawerOpen ? (
        <div
          className="drawer-backdrop"
          onClick={closeDrawer}
          // The Escape key and the sidebar's own links are the real
          // affordances; this is a mouse convenience, so it is hidden
          // from assistive tech rather than announced as a button.
          aria-hidden="true"
        />
      ) : null}

      <div className="content-column">
        <TopBar
          pathname={pathname}
          t={t}
          user={session?.user ?? null}
          pendingReviews={pending}
          onOpenSidebar={() => setDrawerOpen(true)}
        />
        <main className="content" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
