"use client";

/** The things people come here to start — theirs, not everyone's — and one to read.
 *
 * Signed out, the account-scoped ones still appear but point at
 * `/login`. Hiding them would leave a visitor unable to discover that
 * the feature exists; sending them to a dead end would be worse. Sign-in
 * is the honest next step.
 *
 * The guide is the odd one and is here anyway. It is not a thing you
 * start — it is the thing somebody opening this app for the first time
 * needs before any of the other five mean anything, and the rail alone
 * puts it below the fold of a reader's attention on the one screen where
 * they have not yet decided what to do.
 * **Signed in, the list is the caller's own.** Once the three packages
 * stopped nesting, one fixed list was wrong for everybody: a reviewer
 * who holds no engineer package cannot start a run, and an engineer
 * offered "publish an algorithm" is offered a 403. So each action names
 * the capability it needs, and the ones a caller does not hold are not
 * drawn — an unheld action is not a locked door worth showing, it is a
 * job somebody else does.
 *
 * The two that name no capability are open to any account and stay
 * unconditional.
 */

import Link from "next/link";

import { Icon, type IconName } from "./Icon";
import { CAPABILITIES, can, useSession, type CapabilityName } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

interface Action {
  href: string;
  labelKey: string;
  icon: IconName;
  primary?: boolean;
  session?: boolean;
  /** What the caller must hold for this to be worth offering.
   *
   * Cosmetic, exactly like the sidebar's: the API refuses regardless,
   * and this only keeps the dashboard from advertising work the reader
   * cannot do. */
  capability?: CapabilityName;
}

const ACTIONS: readonly Action[] = [
  {
    href: "/decisions",
    labelKey: "dashboard.action.createBenchmark",
    icon: "plus",
    primary: true,
    session: true,
    capability: CAPABILITIES.runCreate,
  },
  { href: "/agent", labelKey: "dashboard.action.openAgent", icon: "sparkles" },
  {
    href: "/simulate",
    labelKey: "dashboard.action.startSimulation",
    icon: "play",
    capability: CAPABILITIES.simulationRun,
  },
  { href: "/maps", labelKey: "dashboard.action.createMap", icon: "map" },
  { href: "/guide", labelKey: "dashboard.guide.title", icon: "book" },
  {
    href: "/reviews",
    labelKey: "dashboard.action.reviewQueue",
    icon: "inbox",
    session: true,
    capability: CAPABILITIES.runReview,
  },
  {
    href: "/algorithms",
    labelKey: "dashboard.action.publishAlgorithm",
    icon: "sparkles",
    session: true,
    capability: CAPABILITIES.algorithmPublish,
  },
  {
    href: "/admin/users",
    labelKey: "dashboard.action.manageAccess",
    icon: "user",
    session: true,
    capability: CAPABILITIES.userManage,
  },
];

export function QuickActions({ signedIn }: { signedIn: boolean }) {
  const { t } = useTranslation();
  const session = useSession();

  // Signed out, the capability-gated ones are still drawn and still
  // point at `/login`: a visitor has no capabilities at all, and
  // filtering on that would leave an empty panel where the product is.
  const shown = ACTIONS.filter(
    (action) => !signedIn || !action.capability || can(session?.user, action.capability),
  );

  return (
    <section className="dashboard-actions" aria-labelledby="dashboard-quick-actions-title">
      <div className="dashboard-section-heading">
        <span className="dashboard-section-icon" aria-hidden="true">
          <Icon name="sparkles" size={17} />
        </span>
        <h3 id="dashboard-quick-actions-title">{t("dashboard.quickActions")}</h3>
      </div>
      <div className="quick-actions dashboard-quick-actions">
        {shown.map((action) => (
          <Link
            key={action.href + action.labelKey}
            className={`quick-action${action.primary ? " primary" : ""}`}
            href={action.session && !signedIn ? "/login" : action.href}
          >
            <span className="quick-action-icon" aria-hidden="true">
              <Icon name={action.icon} size={17} />
            </span>
            <span>{t(action.labelKey)}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
