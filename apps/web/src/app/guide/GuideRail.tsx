"use client";

/** The rail, told which article is open by the URL.
 *
 * Split from the layout because a layout is a server component and
 * `usePathname` is not — and because this is the only part of the frame
 * that has to know where the reader is standing.
 */

import { usePathname } from "next/navigation";

import { GuideSidebar } from "@/components/guide/GuideSidebar";

export function GuideRail() {
  const pathname = usePathname();
  const match = /^\/guide\/([^/]+)/.exec(pathname);
  return <GuideSidebar slug={match ? match[1] : null} />;
}
