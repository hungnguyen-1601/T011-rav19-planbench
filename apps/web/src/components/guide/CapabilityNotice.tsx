"use client";

/** What this reader may do, said by the app rather than by an article.
 *
 * The prose states the rule — *importing an algorithm needs
 * `plugin.import`* — and this states the fact about the person reading
 * it. Keeping them apart is what stops an article from carrying a
 * sentence like "administrators only", which is true today, will be
 * false when capability packages land, and would then be wrong in two
 * languages at once.
 *
 * Renders nothing while the answer is still being fetched, and nothing
 * when nobody is signed in beyond the invitation to sign in: a grey chip
 * saying "no" to a signed-out visitor reads as a refusal rather than as
 * a question that has not been asked yet.
 */

import Link from "next/link";

import { useGuideContext } from "@/lib/guideContext";
import { useTranslation } from "@/lib/i18n";

export function CapabilityNotice() {
  const { t } = useTranslation();
  const { canImportPlugin, signedIn, loading } = useGuideContext();

  if (loading) return null;
  if (!signedIn) {
    return (
      <p className="guide-capability muted">
        <Link href="/login">{t("guide.signInToSee")}</Link>
      </p>
    );
  }
  return (
    <p className="guide-capability" data-allowed={canImportPlugin ? "true" : "false"}>
      {canImportPlugin ? t("guide.capability.canImport") : t("guide.capability.cannotImport")}
    </p>
  );
}
