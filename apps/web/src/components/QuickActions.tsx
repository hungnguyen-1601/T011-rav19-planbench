"use client";

/** The five things people actually come here to start.
 *
 * Signed out, the account-scoped ones still appear but point at
 * `/login`. Hiding them would leave a visitor unable to discover that
 * the feature exists; sending them to a dead end would be worse. Sign-in
 * is the honest next step.
 */

import Link from "next/link";

import { Icon, type IconName } from "./Icon";
import { useTranslation } from "@/lib/i18n";

interface Action {
  href: string;
  labelKey: string;
  icon: IconName;
  primary?: boolean;
  session?: boolean;
}

const ACTIONS: readonly Action[] = [
  {
    href: "/benchmarks",
    labelKey: "dashboard.action.createBenchmark",
    icon: "plus",
    primary: true,
    session: true,
  },
  { href: "/agent", labelKey: "dashboard.action.openAgent", icon: "sparkles" },
  { href: "/simulate", labelKey: "dashboard.action.startSimulation", icon: "play" },
  { href: "/maps", labelKey: "dashboard.action.createMap", icon: "map" },
  { href: "/reviews", labelKey: "dashboard.action.reviewInbox", icon: "inbox", session: true },
];

export function QuickActions({ signedIn }: { signedIn: boolean }) {
  const { t } = useTranslation();

  return (
    <>
      <h3>{t("dashboard.quickActions")}</h3>
      <div className="quick-actions">
        {ACTIONS.map((action) => (
          <Link
            key={action.href + action.labelKey}
            className={`quick-action${action.primary ? " primary" : ""}`}
            href={action.session && !signedIn ? "/login" : action.href}
          >
            <Icon name={action.icon} size={15} />
            {t(action.labelKey)}
          </Link>
        ))}
      </div>
    </>
  );
}
