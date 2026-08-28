/** The `/deployments` page's two tabs, and the state they must not lose.
 *
 * Same two registers as `decisions-list-tabs.test.tsx`, for the same
 * reason — this repo has no jsdom (see `vitest.config.ts`):
 *
 * - **Rendered**, through `renderToStaticMarkup`, for `DecisionTabs`
 *   itself with stand-in panels.
 * - **Source-level**, for the page: `DeploymentsPage` sits behind an
 *   effect and a fetch, so a first paint shows a loading state.
 *
 * The stake here is higher than on the other two tabbed pages.
 * `DeploymentForm` is two and a half thousand lines holding a start and
 * a goal pose drawn by hand, a loaded map, an undo/redo history, its own
 * open sub-tab, a playing traffic preview and a set of field errors —
 * none of it persisted anywhere. Unmounting it to look at the table
 * would hand back only `draft`, which lives on the page. So "hidden, not
 * unmounted" is not a preference on this page; it is the difference
 * between a tab switch and losing ten minutes of work.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { DecisionTabs } from "@/components/DecisionTabs";
import { DEPLOYMENTS_TAB_IDS } from "@/lib/deploymentsTabs";

const APP = join(process.cwd(), "src", "app");
const PAGE = readFileSync(join(APP, "deployments", "page.tsx"), "utf8");
const STORE = readFileSync(
  join(process.cwd(), "src", "lib", "deploymentsTabs.ts"),
  "utf8",
);
const DECISIONS_STORE = readFileSync(
  join(process.cwd(), "src", "lib", "decisionsListTabs.ts"),
  "utf8",
);

const TAB_LABELS = ["deployments.tabs.create", "deployments.tabs.list"];

function render(active: string): string {
  return renderToStaticMarkup(
    <DecisionTabs
      labelKey="deployments.tabs.label"
      active={active}
      onSelect={() => {}}
      tabs={DEPLOYMENTS_TAB_IDS.map((id, index) => ({
        id,
        labelKey: TAB_LABELS[index],
        content: <p>{`panel-body-${id}`}</p>,
      }))}
    />,
  );
}

describe("filing is the default, and reading is the second tab", () => {
  it("opens on the form, the opposite of the /decisions list", () => {
    /* Arriving at the list page is arriving to see what happened;
       arriving here is arriving to file something. That is why the form
       already sat above the table, and why the head grew a count badge
       so "how many are on file" did not need the list to be first. */
    expect(DEPLOYMENTS_TAB_IDS).toEqual(["create", "list"]);
    expect(STORE).toContain('fallback: "create"');
  });

  it("puts the filing panel in the first tab and the table in the second", () => {
    const create = PAGE.slice(PAGE.indexOf('id: "create"'), PAGE.indexOf('id: "list"'));
    expect(create).toContain('id="deployment-file-panel"');
    expect(create).toContain("<DeploymentForm");
    expect(create).toContain("deployment-mode-bar");
    const list = PAGE.slice(PAGE.indexOf('id: "list"'));
    expect(list).toContain("deployment-list-panel");
    expect(list).toContain("<DeploymentRow");
  });

  it("names both tabs and the strip in both languages", () => {
    for (const key of [...TAB_LABELS, "deployments.tabs.label", "deployments.pager.label"]) {
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    }
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });

  it("reuses the strip the other two pages use rather than growing a third", () => {
    expect(PAGE).toContain('from "@/components/DecisionTabs"');
    expect(PAGE).toContain("<DecisionTabs");
  });
});

describe("the form is hidden on a switch, never unmounted", () => {
  it("keeps both panels in the tree", () => {
    /* A ternary here would throw away a hand-drawn start pose, a loaded
       map and an undo history every time somebody checked an id in the
       table. */
    const html = render("create");
    for (const id of DEPLOYMENTS_TAB_IDS) {
      expect(html).toContain(`panel-body-${id}`);
    }
    expect([...html.matchAll(/role="tabpanel"[^>]*hidden/g)]).toHaveLength(1);
  });

  it("moves the visible panel when the active tab changes", () => {
    expect(render("create")).toMatch(/id="decision-tabpanel-list"[^>]*hidden/);
    expect(render("list")).toMatch(/id="decision-tabpanel-create"[^>]*hidden/);
  });

  it("never reaches for a ternary on the page itself", () => {
    /* The mode bar inside the form panel still switches on `mode`, and
       that one *is* a ternary — but it swaps a textarea for a form, not
       a mounted editor for a table. What must not appear is the whole
       filing panel behind a condition. */
    expect(PAGE).not.toMatch(/tab === "create" \?/);
  });
});

describe("the page remembers which tab, in a slot of its own", () => {
  it("is stored the way the theme and the sidebar are", () => {
    expect(STORE).toContain("createPersistedStore");
    expect(STORE).toContain('backend: "local"');
  });

  it("does not share a key with either decisions store", () => {
    /* One slot holding two different sets of ids means each page's
       remembered choice silently resets the other's: `allowed` falls an
       unknown id back to the default. */
    expect(STORE).toContain('"planbench.deployments-tab"');
    expect(STORE).not.toContain('"planbench.decision-tab"');
    expect(STORE).not.toContain('"planbench.decisions-list-tab"');
    expect(DECISIONS_STORE).not.toContain('"planbench.deployments-tab"');
  });
});

describe("what stays above the strip", () => {
  it("keeps the head, the count, the refusal and the load error out of both tabs", () => {
    /* The error from the list fetch is the only thing that says the page
       failed to load, and the notice naming the profile just filed is
       the only receipt for the click. Filed under one tab, either would
       be invisible from the other. */
    const strip = PAGE.indexOf("<DecisionTabs");
    expect(PAGE.indexOf("deployment-page-head")).toBeLessThan(strip);
    expect(PAGE.indexOf("deployment-count-badge")).toBeLessThan(strip);
    expect(PAGE.indexOf('{error ? <div className="error-box">{error}</div> : null}')).toBeLessThan(
      strip,
    );
    expect(PAGE.indexOf('<div className="notice">{t("deployments.filed"')).toBeLessThan(strip);
  });

  it("no longer sends the empty banner to an anchor inside a hidden panel", () => {
    /* `href="#deployment-file-panel"` scrolled to the form when both
       were on one column. The form now carries `hidden` while the table
       is open, and an in-page link to a hidden element goes nowhere —
       a button that looks broken. */
    expect(PAGE).not.toContain('href="#deployment-file-panel"');
    expect(PAGE).toContain('onClick={() => deploymentsTabStore.set("create")}');
  });
});

describe("the deployments table is paged with the same control", () => {
  it("cuts at ten and draws the shared pager", () => {
    expect(PAGE).toContain('from "@/components/Pager"');
    /* Paged over the sorted list rather than the raw one. Paging
       `profiles` while rendering a sorted copy would cut the wrong ten
       — the first page would hold the ten oldest, ordered newest-first
       among themselves, which looks like the sort simply not working. */
    expect(PAGE).toContain("usePagination(newestFirst)");
    expect(PAGE).toContain("paged.visible.map((profile) => (");
    expect(PAGE).toContain('labelKey="deployments.pager.label"');
  });

  it("counts the whole list in the head badge, not the page", () => {
    /* The badge answers "how many are on file". Scoped to the page it
       would read "10" forever. */
    expect(PAGE).toContain('{loading ? "—" : profiles.length}');
  });

  it("raises the empty banner on an empty list, not on an empty page", () => {
    expect(PAGE).toContain("profiles.length === 0 ? (");
  });
});
