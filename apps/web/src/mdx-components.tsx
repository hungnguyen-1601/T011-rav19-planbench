/** The components MDX reaches for, and the ones it is handed.
 *
 * Required by `@next/mdx` in the App Router: without this file the loader
 * has no component map and every article renders as bare HTML tags.
 *
 * The three are provided here rather than imported by each article so the
 * body of an `.mdx` file stays prose — twenty-two files each opening
 * with the same three import lines is twenty-two places to forget one. Everything else falls through to
 * the element the markdown produced, styled by `globals.css` — the guide
 * has no reason to re-skin paragraphs.
 */

import type { MDXComponents } from "mdx/types";

import { AppLink } from "@/components/guide/AppLink";
import { Callout } from "@/components/guide/Callout";
import { Section } from "@/components/guide/Section";

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return { AppLink, Callout, Section, ...components };
}
