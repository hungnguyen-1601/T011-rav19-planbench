/** The four screens the three packages needed, and what each must not do.
 *
 * No jsdom here, so the pages are asserted the way the rest of this
 * suite asserts pages: the rules that matter are either pure functions
 * (`bundleStates`) or facts about the source that a render cannot hide —
 * which capability gates a control, which endpoint a panel calls, and
 * whether every key it names exists in both dictionaries.
 *
 * The last one is not pedantry. A missing key renders as
 * `algorithms.why.superseded` on screen, which reads as a crash to
 * anybody who is not the person who wrote it.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { bundleStates, type PluginBundleSummary } from "@/lib/plugins";
import { NAV_SECTIONS } from "@/lib/navigation";
import en from "../../lib/i18n/locales/en.json";
import viLocale from "../../lib/i18n/locales/vi.json";

const SRC = join(process.cwd(), "src");
const read = (...parts: string[]) => readFileSync(join(SRC, ...parts), "utf8");

const ALGORITHMS = read("app", "algorithms", "page.tsx");
const ALGORITHM_DETAIL = read("components", "AlgorithmDetail.tsx");
const QUEUE = read("components", "ReviewQueuePanel.tsx");
const ALGORITHM_QUEUE = read("components", "AlgorithmQueuePanel.tsx");
const USERS = read("app", "admin", "users", "page.tsx");
const AUDIT = read("app", "admin", "audit", "page.tsx");
const ACTIONS = read("components", "QuickActions.tsx");

const dictionaries = en as Record<string, string>;
const vietnamese = viLocale as Record<string, string>;

/** Every literal key a source file passes to `t`.
 *
 * Template keys — `t(`algorithms.state.${state}`)` — cannot be read this
 * way, so the tests that care about those enumerate the variants
 * themselves. That is the honest split: a key built at runtime is only
 * as safe as the set of values that can reach it, and the set is what
 * needs asserting.
 */
function keysIn(source: string): string[] {
  // The lookbehind matters: without it, `act("unpublish")` matches on
  // the `t(` at the end of `act(` and the test then demands a
  // translation for a function argument.
  return [...new Set([...source.matchAll(/(?<![\w.])t\("([\w.]+)"/g)].map((match) => match[1]))];
}

function bundle(overrides: Partial<PluginBundleSummary> = {}): PluginBundleSummary {
  return {
    id: "b1",
    name: "VFH+",
    version: "1",
    description: "",
    plugin_id: "org.vinai.vfh-plus",
    plugin_version: "0.1.0",
    revision: 1,
    role: "local",
    requirements: [],
    robot_profile_id: "p1",
    original_filename: "vfh.zip",
    file_size: 2048,
    checksum: "abc",
    status: "active",
    validation_status: "loaded",
    validation_message: "",
    owned: true,
    created_at: "2026-08-28T00:00:00Z",
    updated_at: "2026-08-28T00:00:00Z",
    ...overrides,
  };
}

describe("the algorithms page", () => {
  it("asks for the published set once rather than per row", () => {
    /* The alternative is a detail request per bundle to learn one bit
       each. The route exists precisely so a list does not have to. */
    expect(ALGORITHMS).toContain("publishedBundleIds()");
    expect(ALGORITHMS).not.toContain("bundles.map((bundle) => getPlugin");
  });

  it("survives governance being off instead of showing an error", () => {
    /* The acts 404 while the flag is off; reading the set answers 200
       with an empty list. A page that treated either as a failure would
       put a red box on an ordinary deployment. */
    expect(ALGORITHMS).toContain("publishedBundleIds().catch(");
  });

  it("lists what is not published rather than hiding it", () => {
    // The whole point of the page: a bundle missing from the picker has
    // a reason, and the reason is only visible if the bundle is.
    expect(ALGORITHMS).not.toContain('.filter((bundle) => bundle.status === "active")');
    expect(ALGORITHMS).toContain("algorithms.why.");
  });

  it("names every state it can draw, in both languages", () => {
    const states = [
      "published",
      "superseded",
      "awaiting",
      "checking",
      "held",
      "broken",
      "disabled",
    ];
    for (const state of states) {
      for (const prefix of ["algorithms.state.", "algorithms.why."]) {
        expect(dictionaries[`${prefix}${state}`], `${prefix}${state}`).toBeTruthy();
        expect(vietnamese[`${prefix}${state}`], `vi ${prefix}${state}`).toBeTruthy();
      }
    }
  });

  it("has every literal key its two files name, in both languages", () => {
    for (const key of [...keysIn(ALGORITHMS), ...keysIn(ALGORITHM_DETAIL)]) {
      expect(dictionaries[key], `en ${key}`).toBeTruthy();
      expect(vietnamese[key], `vi ${key}`).toBeTruthy();
    }
  });
});

describe("what a reviewer may do to an algorithm", () => {
  it("shows the code half only to somebody holding algorithm.inspect", () => {
    expect(ALGORITHM_DETAIL).toContain("CAPABILITIES.algorithmInspect");
    expect(ALGORITHM_DETAIL).toContain("{inspects ? (");
  });

  it("gates the governed acts on algorithm.publish, not on being an admin", () => {
    /* The packages do not nest: publishing carries a reviewer's
       signature, and an administrator who is not also a reviewer has no
       business vouching for code. */
    expect(ALGORITHM_DETAIL).toContain("CAPABILITIES.algorithmPublish");
    expect(ALGORITHM_DETAIL).not.toContain("is_admin");
  });

  it("requires a reason for every act that takes something away", () => {
    // Publishing is the one act that says nothing is wrong, so it is the
    // one that may go without.
    const withReason = ALGORITHM_DETAIL.match(/disabled=\{busy \|\| needsReason[^}]*\}/g) ?? [];
    expect(withReason.length).toBe(3);
    expect(ALGORITHM_DETAIL).toContain('disabled={busy || bundle.validation_status !== "loaded"}');
  });

  it("will not offer to publish a bundle that never loaded", () => {
    /* `structural` means nobody ran the conformance suite. Publishing
       there would put a candidate in front of everybody on the strength
       of its archive being readable. */
    expect(ALGORITHM_DETAIL).toContain('bundle.validation_status !== "loaded"');
  });
});

describe("labelling a bundle for a reader", () => {
  it("separates a replaced revision from one nobody published", () => {
    const old = bundle({ id: "b1", revision: 1 });
    const fresh = bundle({ id: "b2", revision: 2 });
    expect(bundleStates([old, fresh], ["b2"]).get("b1")).toBe("superseded");
    expect(bundleStates([old, fresh], []).get("b1")).toBe("awaiting");
  });

  it("lets a reviewer's decision outrank the conformance verdict", () => {
    expect(bundleStates([bundle({ status: "held" })], ["b1"]).get("b1")).toBe("held");
  });
});

describe("the review queue", () => {
  it("takes the four piles from the server rather than filtering one list", () => {
    /* Which pile a request lands in depends on who asked, and that rule
       lives on the server. A client re-deriving it is a second copy free
       to disagree. */
    expect(QUEUE).toContain("fetchReviewQueue()");
    expect(QUEUE).toContain("queue.mine");
    expect(QUEUE).toContain("queue.directed");
    expect(QUEUE).toContain("queue.pool");
    expect(QUEUE).toContain("queue.sent");
  });

  it("says whether the holder has actually read it", () => {
    // "Bob has it" reads as "Bob is dealing with it" while Bob has opened
    // nothing.
    expect(QUEUE).toContain("item.acknowledged");
    expect(dictionaries["queue.unread"]).toBeTruthy();
  });

  it("offers claiming here and signing nowhere near here", () => {
    /* Taking work is one click that risks nothing — a claim can be
       released. Saying you read the evidence, and signing off on it, are
       acts about a run's contents and belong where the evidence is. */
    expect(QUEUE).toContain("claimReview");
    expect(QUEUE).toContain("releaseReview");
    expect(QUEUE).not.toContain("decideConfig");
    expect(QUEUE).not.toContain("reviewRun");
  });

  it("gives the owner nothing to press except withdrawing their own request", () => {
    expect(QUEUE).toContain("cancelSubmission");
    expect(QUEUE).toContain('item.submission === "submitted"');
  });

  it("has every literal key both panels name, in both languages", () => {
    for (const key of [...keysIn(QUEUE), ...keysIn(ALGORITHM_QUEUE)]) {
      expect(dictionaries[key], `en ${key}`).toBeTruthy();
      expect(vietnamese[key], `vi ${key}`).toBeTruthy();
    }
    for (const state of ["none", "submitted", "claimed", "closed"]) {
      expect(dictionaries[`queue.state.${state}`], `queue.state.${state}`).toBeTruthy();
      expect(vietnamese[`queue.state.${state}`], `vi queue.state.${state}`).toBeTruthy();
    }
  });
});

describe("users and access", () => {
  it("offers three independent packages, not one ladder", () => {
    /* A reviewer is not a senior engineer and an administrator is not a
       senior reviewer, so the control is three checkboxes rather than a
       dropdown of levels. */
    expect(USERS).toContain("GRANTABLE_ROLES.map");
    expect(USERS).toContain('type="checkbox"');
    expect(USERS).not.toContain("<select");
  });

  it("never offers demo_owner, and still shows it where somebody holds it", () => {
    /* It is a deployment profile's concession rather than a job anybody
       does. Offering it in a dropdown would turn a one-machine exception
       into something anybody could spread; hiding it entirely would
       leave the one account that has it looking ordinary. */
    const admin = readFileSync(join(SRC, "lib", "admin.ts"), "utf8");
    expect(admin).toContain('export const GRANTABLE_ROLES = ["engineer", "reviewer", "admin"]');
    expect(admin).not.toContain('"demo_owner"]');
    expect(USERS).toContain('account.roles.includes("demo_owner")');
  });

  it("will not let a change be made without a reason", () => {
    // This is the table an auditor opens first.
    expect(USERS).toContain("const needsReason = !reason.trim()");
    expect(USERS).toContain("disabled={!manages || needsReason");
  });

  it("does not offer an administrator the button that locks them out", () => {
    expect(USERS).toContain("const self = account.id === session?.user.id");
    expect(USERS).toContain("{manages && !self ? (");
  });

  it("has every literal key its two pages name, in both languages", () => {
    for (const key of [...keysIn(USERS), ...keysIn(AUDIT)]) {
      expect(dictionaries[key], `en ${key}`).toBeTruthy();
      expect(vietnamese[key], `vi ${key}`).toBeTruthy();
    }
    for (const action of ["role_granted", "role_revoked", "disabled", "enabled"]) {
      expect(dictionaries[`admin.audit.action.${action}`], action).toBeTruthy();
      expect(vietnamese[`admin.audit.action.${action}`], `vi ${action}`).toBeTruthy();
    }
    for (const role of ["engineer", "reviewer", "admin", "demo_owner"]) {
      expect(dictionaries[`topbar.role.${role}`], role).toBeTruthy();
      expect(vietnamese[`topbar.role.${role}`], `vi ${role}`).toBeTruthy();
    }
  });
});

describe("the access trail", () => {
  it("orders by sequence rather than by clock", () => {
    /* Two acts can share a timestamp, and "who did it first" is exactly
       what an audit trail is asked. The API returns them in order and
       the page must not re-sort. */
    expect(AUDIT).not.toContain(".sort(");
    expect(AUDIT).toContain("event.sequence");
  });

  it("gives break-glass acts a column of their own", () => {
    expect(AUDIT).toContain("event.override");
    expect(AUDIT).toContain("overridesOnly");
  });

  it("keeps what the actor held at the time, not what they hold now", () => {
    expect(AUDIT).toContain("event.actor_roles");
    expect(AUDIT).toContain("event.authorized_capability");
  });
});

describe("the dashboard's quick actions", () => {
  it("offers each action only to somebody who could take it", () => {
    /* One fixed list was wrong for everybody once the packages stopped
       nesting: a reviewer holding no engineer package cannot start a
       run, and an engineer offered "publish an algorithm" is offered a
       403. */
    expect(ACTIONS).toContain("CAPABILITIES.runCreate");
    expect(ACTIONS).toContain("CAPABILITIES.runReview");
    expect(ACTIONS).toContain("CAPABILITIES.algorithmPublish");
    expect(ACTIONS).toContain("CAPABILITIES.userManage");
  });

  it("still shows them signed out, pointing at the sign-in page", () => {
    // A visitor has no capabilities at all; filtering on that would
    // leave an empty panel where the product is.
    expect(ACTIONS).toContain("!signedIn || !action.capability");
    expect(ACTIONS).toContain('action.session && !signedIn ? "/login" : action.href');
  });
});

describe("the rail", () => {
  it("gathers the administration pages under their own heading", () => {
    const admin = NAV_SECTIONS.find(
      (section) => section.titleKey === "nav.section.administration",
    );
    expect(admin?.items.map((item) => item.href)).toEqual([
      "/admin/users",
      "/admin/audit",
      "/settings",
    ]);
  });

  it("points at /algorithms, which now exists", () => {
    /* It was added to the rail before the route was written, and a link
       in the rail to a route that is not there is a 404 the reader has
       no way to predict. */
    const everywhere = NAV_SECTIONS.flatMap((section) => section.items);
    const entry = everywhere.find((item) => item.href === "/algorithms");
    expect(entry?.capability).toBe("algorithm.catalogue");
    expect(ALGORITHMS.startsWith('"use client"')).toBe(true);
  });

  it("names every rail label and description in both languages", () => {
    for (const item of NAV_SECTIONS.flatMap((section) => section.items)) {
      expect(dictionaries[item.labelKey], `en ${item.labelKey}`).toBeTruthy();
      expect(vietnamese[item.labelKey], `vi ${item.labelKey}`).toBeTruthy();
      if (item.descriptionKey) {
        expect(dictionaries[item.descriptionKey], `en ${item.descriptionKey}`).toBeTruthy();
        expect(vietnamese[item.descriptionKey], `vi ${item.descriptionKey}`).toBeTruthy();
      }
    }
    for (const section of NAV_SECTIONS) {
      expect(dictionaries[section.titleKey], `en ${section.titleKey}`).toBeTruthy();
      expect(vietnamese[section.titleKey], `vi ${section.titleKey}`).toBeTruthy();
    }
  });
});
