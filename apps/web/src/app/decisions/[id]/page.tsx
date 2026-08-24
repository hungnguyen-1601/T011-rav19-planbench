import { shellParams } from "@/lib/routeShell";

import { DecisionDetail } from "./DecisionDetail";

/**
 * One exported file for every selection run there will ever be.
 *
 * A static export writes a file per route it can name, and it cannot
 * name these: the ids belong to runs the user has not created yet.
 * Returning the sentinel builds `decisions/_.html`, which the API serves
 * for any id (see `apps/api/planbench_api/static_site.py`); the page
 * reads the real id back out of the URL once it hydrates.
 *
 * This wrapper exists only because `generateStaticParams` runs on the
 * server and DecisionDetail is a client component. It renders nothing of
 * its own — no strings, so nothing here needs translating.
 */
export function generateStaticParams(): { id: string }[] {
  return shellParams();
}

export default function Page() {
  return <DecisionDetail />;
}
