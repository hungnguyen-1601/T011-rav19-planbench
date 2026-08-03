/** The top bar, rendered — signed in and signed out.
 *
 * The switchers and the account menu are client components, rendered
 * here inside the locale provider with the router mocked. What is
 * asserted is what a first paint shows: the page title, the breadcrumb,
 * the review badge, and whether the account area is a menu or a plain
 * sign-in link.
 */

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { LocaleContext, DICTIONARIES, translate, type Locale } from "@/lib/i18n";
import { NotificationButton } from "@/components/NotificationButton";
import { SystemStatus } from "@/components/SystemStatus";
import { TopBar } from "@/components/TopBar";
import type { SessionUser } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/",
}));

function translator(locale: Locale = "en") {
  return (key: string, vars?: Record<string, string | number>) =>
    translate(DICTIONARIES[locale], DICTIONARIES.en, key, vars);
}

const ALICE: SessionUser = {
  id: "u1",
  nickname: "alice",
  email: "alice@example.com",
  display_name: "Alice Example",
  avatar_url: "",
  is_admin: false,
  needs_nickname: false,
  providers: ["google"],
};

/** Render inside the locale provider. */
function render(node: React.ReactNode, locale: Locale = "en"): string {
  return renderToStaticMarkup(
    <LocaleContext.Provider value={locale}>{node}</LocaleContext.Provider>,
  );
}

function topbar(
  overrides: Partial<Parameters<typeof TopBar>[0]> = {},
  locale: Locale = "en",
): string {
  return render(
    <TopBar
      pathname="/"
      t={translator(locale)}
      user={null}
      pendingReviews={0}
      onOpenSidebar={() => {}}
      {...overrides}
    />,
    locale,
  );
}

// No `window` stub on purpose. Defining a fake `window` makes
// react-dom/server take a browser code path, which made this file fail
// roughly one run in three. None of these components touch `window`
// during a server render: `useSyncExternalStore` uses its
// server-snapshot, and the router is mocked above.

describe("TopBar — where you are", () => {
  it("names the current page", () => {
    expect(topbar({ pathname: "/benchmarks" })).toContain("Benchmarks");
  });

  it("shows a breadcrumb on a detail page, with the id verbatim", () => {
    const html = topbar({ pathname: "/benchmarks/ab12cd" });
    expect(html).toContain("ab12cd");
    expect(html).toContain('aria-label="Breadcrumb"');
  });

  it("shows no breadcrumb on a section page", () => {
    expect(topbar({ pathname: "/benchmarks" })).not.toContain('aria-label="Breadcrumb"');
  });

  it("names the page in Vietnamese", () => {
    expect(topbar({ pathname: "/benchmarks" }, "vi")).toContain("Benchmark");
    expect(topbar({ pathname: "/leaderboard" }, "vi")).toContain("Bảng xếp hạng");
  });
});

describe("TopBar — the mobile menu button", () => {
  it("is present, labelled, and points at the sidebar", () => {
    const html = topbar();
    expect(html).toContain('aria-label="Open navigation"');
    expect(html).toContain('aria-controls="app-sidebar"');
    // Shown only below 900px; CSS decides, not JS.
    expect(html).toContain("mobile-only");
  });
});

describe("TopBar — signed out", () => {
  it("offers a sign-in link", () => {
    const html = topbar();
    expect(html).toContain('href="/login"');
    expect(html).toContain("Sign in");
  });

  it("shows no account menu", () => {
    expect(topbar()).not.toContain('aria-label="Account menu"');
  });

  it("shows no review badge, because there is no inbox to have", () => {
    expect(topbar({ pendingReviews: 3 })).not.toContain("badge-count");
  });

  it("still offers the language and theme switchers", () => {
    // These are for everybody, including a visitor who cannot sign in.
    const html = topbar();
    expect(html).toContain('aria-label="Language"');
    expect(html).toContain('aria-label="Theme"');
  });
});

describe("TopBar — signed in", () => {
  it("shows the account menu with the nickname", () => {
    const html = topbar({ user: ALICE });
    expect(html).toContain('aria-label="Account menu"');
    expect(html).toContain("alice");
  });

  it("shows the review inbox", () => {
    expect(topbar({ user: ALICE })).toContain('href="/reviews"');
  });

  it("shows the pending count on the badge", () => {
    const html = topbar({ user: ALICE, pendingReviews: 3 });
    expect(html).toContain("badge-count");
    expect(html).toContain(">3<");
  });

  it("shows no badge when nothing is waiting", () => {
    expect(topbar({ user: ALICE, pendingReviews: 0 })).not.toContain("badge-count");
  });
});

describe("NotificationButton", () => {
  it("puts the count in the accessible name, not only in the red circle", () => {
    // A screen reader that only hears "Review inbox" has been told
    // nothing at all.
    const html = render(<NotificationButton pending={3} />);
    expect(html).toContain("3 review request(s) waiting for you");
  });

  it("says so when nothing is waiting", () => {
    expect(render(<NotificationButton pending={0} />)).toContain("Nothing waiting for you");
  });

  it("caps a large count so it fits the badge", () => {
    expect(render(<NotificationButton pending={250} />)).toContain("99+");
  });

  it("hides the visual count from assistive tech, which already has it", () => {
    expect(render(<NotificationButton pending={3} />)).toContain(
      '<span class="badge-count" aria-hidden="true">3</span>',
    );
  });
});

describe("SystemStatus", () => {
  it("says online in words, not only in a green dot", () => {
    const html = render(<SystemStatus status="online" />);
    expect(html).toContain("System online");
    expect(html).toContain("status-dot online");
  });

  it("says unavailable, and offers a retry", () => {
    const html = render(<SystemStatus status="offline" onRetry={() => {}} />);
    expect(html).toContain("System unavailable");
    expect(html).toContain('aria-label="Retry"');
  });

  it("does not offer retry while it is still checking", () => {
    const html = render(<SystemStatus status="checking" onRetry={() => {}} />);
    expect(html).toContain("Checking");
    expect(html).not.toContain('aria-label="Retry"');
  });

  it("announces changes politely", () => {
    expect(render(<SystemStatus status="online" />)).toContain('role="status"');
  });

  it("translates", () => {
    expect(render(<SystemStatus status="online" />, "vi")).toContain("Hệ thống hoạt động");
  });
});
