import { GuideLanding } from "./GuideLanding";

/** The guide's front door.
 *
 * Not an article. Somebody arriving at `/guide` has one of two errands —
 * *show me how to run this* or *where does it explain X* — and a long
 * page opening on the first article serves neither.
 */
export default function GuidePage() {
  return <GuideLanding />;
}
