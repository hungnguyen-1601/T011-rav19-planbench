/** One guide article.
 *
 * A server component, because `generateStaticParams` has to be one: the
 * desktop build is a static export and needs the list of pages while it
 * builds. Everything below the slug check is client — see `GuideArticle`
 * for why the language cannot be decided here.
 */

import { notFound } from "next/navigation";

import { GuideArticle } from "./GuideArticle";
import { articleBySlug, GUIDE_SLUGS } from "../../../../content/guide/manifest";

/** Every article, named from the manifest.
 *
 * A slug the manifest does not list is a page the export never writes,
 * and on the desktop build that is a 404 no amount of client routing can
 * rescue — so the manifest is the one list, and a test pins this against
 * it.
 */
export function generateStaticParams() {
  return GUIDE_SLUGS.map((slug) => ({ slug }));
}

export const dynamicParams = false;

export default async function GuideArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (!articleBySlug(slug)) notFound();
  return <GuideArticle slug={slug} />;
}
