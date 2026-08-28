"use client";

/** Tabs inside an article, addressable by the URL.
 *
 * Wraps `DecisionTabs` rather than repeating it: that component already
 * carries the keyboard contract — roving `tabIndex`, arrows, Home/End,
 * selection following focus — and a second tab strip is a second set of
 * those rules to drift.
 *
 * **A tab is only ever used where the tab itself is the anchor.** The
 * inactive panels are `hidden`, which takes them out of find-in-page and
 * out of the accessibility tree, so a heading inside a closed tab is a
 * heading nothing can reach. That rules tabs out for a reference article
 * other pages link into, and rules them in here: `#g2` names the tab, so
 * opening the tab *is* answering the link.
 *
 * What this adds to `DecisionTabs` is the address:
 *
 * - **The hash chooses the tab and never takes focus.** A deep link or a
 *   reload is somebody arriving, not somebody asking to be moved.
 * - **A hash naming no tab falls to the first**, rather than to a blank
 *   panel: a stale link should still show the article.
 * - **`pushState`, not `replaceState`**, so Back walks the tabs actually
 *   opened.
 *
 * Titles arrive as text rather than translation keys — they live in the
 * manifest in both languages, which is what the `label` half of
 * `DecisionTabs` exists for.
 */

import { useEffect, useState, type ReactNode } from "react";

import { DecisionTabs } from "@/components/DecisionTabs";
import { articleBySlug } from "../../../content/guide/manifest";
import { useTranslation } from "@/lib/i18n";

export function GuideTabs({
  slug,
  children,
}: {
  /** The article these belong to; its manifest entry names the tabs. */
  slug: string;
  /** One child per tab, in the manifest's order. */
  children: ReactNode[];
}) {
  const { locale, t } = useTranslation();
  const article = articleBySlug(slug);
  const tabs = article?.tabs ?? [];
  const [active, setActive] = useState(tabs[0]?.id ?? "");

  useEffect(() => {
    const fromHash = () => {
      const id = window.location.hash.slice(1);
      if (tabs.some((tab) => tab.id === id)) setActive(id);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
    // `tabs` comes from a module-level constant keyed by `slug`, so
    // listing it would resubscribe on every render for no change.
  }, [slug]); // eslint-disable-line react-hooks/exhaustive-deps

  if (tabs.length === 0) return null;

  return (
    <DecisionTabs
      tabs={tabs.map((tab, index) => ({
        id: tab.id,
        label: tab.title[locale],
        content: children[index] ?? null,
      }))}
      active={active}
      onSelect={(id) => {
        setActive(id);
        window.history.pushState(null, "", `#${id}`);
      }}
      label={t("guide.tabs", { article: article?.title[locale] ?? "" })}
    />
  );
}
