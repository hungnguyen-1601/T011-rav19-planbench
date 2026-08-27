"use client";

/** Search, then what is running, then everything there is to read.
 *
 * The cards are built from the manifest rather than written here, so an
 * article cannot exist without being reachable and cannot be listed
 * before it exists. That second half matters more than it sounds: a
 * landing page that names articles somebody has not written yet is a
 * page full of dead links, and this one grows exactly as the guide does.
 */

import Link from "next/link";

import { GUIDE, type GuideGroup } from "../../../content/guide/manifest";
import { CapabilityNotice } from "@/components/guide/CapabilityNotice";
import { GuideSearch } from "@/components/guide/GuideSearch";
import { useGuideContext } from "@/lib/guideContext";
import { useTranslation } from "@/lib/i18n";

const GROUPS: readonly GuideGroup[] = ["overview", "operating", "results", "advanced", "reference"];

/** Version, provider, and nothing that needs a second sentence.
 *
 * Every line disappears when its fact is unavailable rather than
 * printing "unknown": the guide is readable with the API down, and a
 * row of question marks is worse than a row that is not there.
 */
function LiveStatus() {
  const { t } = useTranslation();
  const { version, aiReady, aiModel, loading } = useGuideContext();
  if (loading) return null;
  return (
    <p className="guide-status muted">
      {version ? <span>{t("guide.version", { version })}</span> : null}
      <span>{aiReady ? t("guide.ai.on", { model: aiModel }) : t("guide.ai.offline")}</span>
    </p>
  );
}

export function GuideLanding() {
  const { locale, t } = useTranslation();
  return (
    <div className="guide-landing">
      <header>
        <h1>{t("guide.title")}</h1>
        <p className="muted">{t("guide.subtitle")}</p>
      </header>

      <GuideSearch />
      <LiveStatus />
      <CapabilityNotice />

      <div className="guide-cards">
        {GROUPS.map((group) => {
          const articles = GUIDE.filter((article) => article.group === group).sort(
            (a, b) => a.order - b.order,
          );
          if (articles.length === 0) return null;
          return (
            <section key={group} className="guide-card">
              <h2>{t(`guide.group.${group}`)}</h2>
              <ul>
                {articles.map((article) => (
                  <li key={article.slug}>
                    <Link href={`/guide/${article.slug}`}>{article.title[locale]}</Link>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
