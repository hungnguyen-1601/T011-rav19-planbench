/** The `/decisions` list page's two tabs.
 *
 * Same two registers as `decision-tabs.test.tsx`, for the same reason —
 * this repo has no jsdom (see `vitest.config.ts`):
 *
 * - **Rendered**, through `renderToStaticMarkup`. `DecisionTabs` takes
 *   its panels as props, so it can be rendered here with stand-ins;
 *   rendering it twice with a different `active` is what "switching tabs
 *   changes the panel" means without a click.
 * - **Source-level**, for the page itself: `DecisionsPage` sits behind
 *   an effect and a fetch, so a first paint would show a loading state
 *   and nothing else.
 *
 * The arrow-key rule is shared with the detail page and is unit-tested
 * there; what is asserted here is that this strip uses it rather than a
 * second copy.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { DecisionTabs } from "@/components/DecisionTabs";
import { DECISIONS_LIST_TAB_IDS } from "@/lib/decisionsListTabs";

const APP = join(process.cwd(), "src", "app");
const LIST = readFileSync(join(APP, "decisions", "page.tsx"), "utf8");
const CSS = readFileSync(join(APP, "globals.css"), "utf8");
const STORE = readFileSync(
  join(process.cwd(), "src", "lib", "decisionsListTabs.ts"),
  "utf8",
);

const TAB_LABELS = ["decisions.list.tabs.overview", "decisions.list.tabs.launch"];

function render(active: string): string {
  return renderToStaticMarkup(
    <DecisionTabs
      labelKey="decisions.list.tabs.label"
      active={active}
      onSelect={() => {}}
      tabs={DECISIONS_LIST_TAB_IDS.map((id, index) => ({
        id,
        labelKey: TAB_LABELS[index],
        content: <p>{`panel-body-${id}`}</p>,
      }))}
    />,
  );
}

describe("the list page offers exactly two tabs", () => {
  it("names one per half, reading before launching", () => {
    expect(DECISIONS_LIST_TAB_IDS).toEqual(["overview", "launch"]);
    const html = render("overview");
    expect([...html.matchAll(/role="tab"/g)]).toHaveLength(2);
    expect([...html.matchAll(/role="tabpanel"/g)]).toHaveLength(2);
  });

  it("has a label for every tab in both languages", () => {
    /* The strip's own accessible name counts: a tab list with no name
       is announced as an unlabelled pair of buttons. */
    for (const key of [...TAB_LABELS, "decisions.list.tabs.label"]) {
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    }
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });

  it("reuses the detail page's strip rather than growing a second one", () => {
    expect(LIST).toContain('from "@/components/DecisionTabs"');
    expect(LIST).toContain("<DecisionTabs");
  });
});

describe("switching tabs changes which panel is shown", () => {
  it("marks exactly one tab selected and shows exactly one panel", () => {
    const html = render("overview");
    expect([...html.matchAll(/aria-selected="true"/g)]).toHaveLength(1);
    /* One of the two panels carries `hidden`; the other does not.
       Counting is the assertion — "the active one is visible" is only
       half of it, and the half a broken build still satisfies. */
    expect([...html.matchAll(/role="tabpanel"[^>]*hidden/g)]).toHaveLength(1);
  });

  it("moves the visible panel when the active tab changes", () => {
    const first = render("overview");
    const second = render("launch");
    expect(first).not.toEqual(second);
    /* `hidden` sits after `role="tabpanel"` in the markup, so this
       matches the panel element itself rather than anything inside it. */
    expect(first).toMatch(/id="decision-tabpanel-launch"[^>]*hidden/);
    expect(first).not.toMatch(/id="decision-tabpanel-overview"[^>]*hidden/);
    expect(second).toMatch(/id="decision-tabpanel-overview"[^>]*hidden/);
    expect(second).not.toMatch(/id="decision-tabpanel-launch"[^>]*hidden/);
  });

  it("keeps both panels in the tree, so nothing is unmounted on a switch", () => {
    /* The reason the inactive panel is hidden rather than dropped: the
       launch form holds a half-filled candidate pair, a scope override,
       an episode count and a drawn start/goal pose, and the overview
       holds three filter selections and a fetched list. A ternary would
       throw one of those away on every switch. */
    const html = render("overview");
    for (const id of DECISIONS_LIST_TAB_IDS) {
      expect(html).toContain(`panel-body-${id}`);
    }
  });

  it("never gives the panels an author `display`, which would beat `hidden`", () => {
    /* `[hidden] { display: none }` is a UA rule, and any author
       `display` on the same element wins it — both panels would render
       at once, which on this page means the launch form back on top of
       the table it was moved out from under. */
    const panel = CSS.slice(CSS.indexOf(".decision-tabpanel"));
    expect(panel).toContain(".decision-tabpanel[hidden] { display: none; }");
    expect(CSS).not.toMatch(/\.decision-tabpanel \{[^}]*display:/);
  });
});

describe("which half sits in which tab", () => {
  it("opens on what has already been measured, not on the form", () => {
    /* Arriving at `/decisions` is arriving to see what happened. The
       old column had this the other way round, and reading the table
       meant scrolling past the whole launch form first. */
    expect(LIST).toContain("active={tab}");
    expect(STORE).toContain('fallback: "overview"');
  });

  it("groups the tallies, the filters and the table together", () => {
    const tab = LIST.slice(
      LIST.indexOf('id: "overview"'),
      LIST.indexOf('id: "launch"'),
    );
    expect(tab).toContain("decision-tally-panel");
    expect(tab).toContain("decision-filter-bar");
    expect(tab).toContain("<DecisionRow");
  });

  it("puts the launch flow in the second tab, and the queue it starts under the first", () => {
    /* The queue used to hang off the bottom of the launch panel, which
       reads well for the ten seconds after a click and badly for the two
       hours after it: a sweep outlives the form, so "is it still going"
       is a question about the runs and belongs with them. */
    const launch = LIST.slice(LIST.indexOf('id: "launch"'));
    expect(launch).toContain("<LaunchPanel profiles={profiles}");
    expect(launch).not.toContain("<JobList");
    const overview = LIST.slice(
      LIST.indexOf('id: "overview"'),
      LIST.indexOf('id: "launch"'),
    );
    expect(overview).toContain("<JobList jobs={jobs} onCancel={cancelJob} />");
  });

  it("renders each half exactly once", () => {
    /* A panel duplicated across two tabs is two copies of one fetch. */
    for (const panel of ["<LaunchPanel", "decision-filter-bar", "decision-tally-panel"]) {
      expect([...LIST.matchAll(new RegExp(panel, "g"))]).toHaveLength(1);
    }
  });

  it("leaves the head and the load error above both tabs", () => {
    /* A failed list fetch is the only thing that says the page did not
       load; filed under one tab it would be invisible from the other. */
    const strip = LIST.indexOf("<DecisionTabs");
    expect(LIST.indexOf("decision-page-head")).toBeLessThan(strip);
    expect(LIST.indexOf('{error ? <div className="error-box">{error}</div> : null}')).toBeLessThan(
      strip,
    );
  });
});

describe("the open tab survives a reload", () => {
  it("remembers it the way the theme and the sidebar are remembered", () => {
    expect(STORE).toContain("createPersistedStore");
    expect(STORE).toContain('backend: "local"');
    /* Its own key. Sharing `planbench.decision-tab` with the detail
       page would mean two different sets of ids in one slot, so each
       page's choice would silently reset the other's. */
    expect(STORE).toContain('"planbench.decisions-list-tab"');
    expect(STORE).not.toContain('"planbench.decision-tab"');
  });
});

describe("the list is paged, and the counting is not", () => {
  it("cuts the table at ten rows and draws the shared pager under it", () => {
    /* Ten is `DEFAULT_PER_PAGE`, checked in `lib/pagination`'s own
       tests; what matters here is that the table body reads the *page*
       and not the whole filtered list. */
    expect(LIST).toContain("{paged.visible.map((run) => (");
    expect(LIST).toContain('from "@/components/Pager"');
    expect(LIST).toContain('labelKey="decisions.list.pager.label"');
  });

  it("filters first and pages the result, never the other way round", () => {
    /* Paging the raw list and filtering the page would give a "ten per
       page" table showing three rows. `usePagination` is handed `shown`
       — what survived the three filters. */
    expect(LIST).toContain("usePagination(shown, {");
  });

  it("returns to the first page when any filter changes", () => {
    /* Page 4 of a forty-run list, then "one deployment" leaves six: the
       reader would be looking at a blank table that reads as "no runs
       for this deployment". All three filters are in the key, because
       any of them can shrink the list. */
    const key = LIST.slice(LIST.indexOf("resetKey:"));
    expect(key.slice(0, key.indexOf("\n"))).toContain(
      "`${profileId}|${rankedFilter}|${reviewFilter}`",
    );
  });

  it("counts every run that passed the filters, not the ten on screen", () => {
    /* "N results" answers "how much is there". Scoped to the page it
       would answer "how much is on screen", which the reader can
       already see — and would read as the filter having matched ten. */
    expect(LIST).toContain("{shown.length} {t(\"decisions.filter.results\")}");
    expect(LIST).not.toContain("{paged.visible.length} {t(\"decisions.filter.results\")}");
  });

  it("tallies the whole filtered list, so paging cannot move the five figures", () => {
    /* Five counts that changed as the reader turned pages would be five
       counts nobody could quote. */
    expect(LIST).toContain("summarise(shown)");
    expect(LIST).not.toContain("summarise(paged");
  });

  it("empties on the filtered list rather than on an empty page", () => {
    /* `paged.visible.length === 0` would raise the empty state on a
       page past the end instead of on a list with nothing in it. */
    expect(LIST).toContain("shown.length === 0 ? (");
  });
});

describe("the overview holds two views, and the queue is one of them", () => {
  it("splits it into what has finished and what is running", () => {
    const overview = LIST.slice(
      LIST.indexOf('id: "overview"'),
      LIST.indexOf('id: "launch"'),
    );
    expect(overview).toContain('labelKey="decisions.list.runs.tabs.label"');
    expect(overview).toContain('id: "results"');
    expect(overview).toContain('id: "jobs"');
  });

  it("names both sub-tabs and their strip in both languages", () => {
    for (const key of [
      "decisions.list.runs.tabs.label",
      "decisions.list.runs.tabs.results",
      "decisions.list.runs.tabs.jobs",
      "decisions.job.empty.title",
      "decisions.job.empty.body",
    ]) {
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    }
  });

  it("keeps the finished and failed jobs, not only the live ones", () => {
    /* The table moved whole. A queue that dropped its finished rows
       would answer "is anything running" and lose "did the one I
       started an hour ago fail" — and the failed row is the one
       carrying the error message. */
    expect(LIST).toContain("{jobs.map((job) => (");
    expect(LIST).toContain("jobIsLive(job) ? (");
    /* Every state gets a row and a badge, `failed` and `cancelled`
       included — the row is drawn from `job.state`, not from a filter
       for the live ones. */
    expect(LIST).toContain("job.state === \"failed\"");
    expect(LIST).toContain("t(`decisions.job.${job.state}`)");
  });

  it("polls once, at the page, rather than once per panel", () => {
    /* The pitfall the move creates: the queue is *started* in the
       launch tab and *read* in the overview. Every panel of a
       `DecisionTabs` strip stays mounted, so an interval left in the
       launch panel would keep running — but the array it produced would
       be trapped in the panel that is not the one drawing the table.
       Two intervals would be two requests every two seconds for one
       answer, free to disagree by a tick. */
    expect(LIST).toContain("const [jobs, setJobs] = useState<DecisionJob[]>([]);");
    expect([...LIST.matchAll(/setInterval\(/g)]).toHaveLength(1);
    expect([...LIST.matchAll(/const \[jobs, setJobs\]/g)]).toHaveLength(1);
    /* And the page's own list refresh still hangs off the last job
       finishing, which is why the timer had to come up here with it. */
    expect(LIST).toContain("if (wasLive && !fetched.some(jobIsLive)) await refresh();");
  });

  it("hands the launch panel the queue instead of letting it keep one", () => {
    const panel = LIST.slice(LIST.indexOf("function LaunchPanel("));
    expect(panel).not.toContain("useState<DecisionJob[]>");
    expect(panel).toContain("onJobsChange(await listDecisionJobs());");
    /* Still refuses a second sweep while one is live — HĐ-7.4 — and now
       reads that from the page's copy. */
    expect(panel).toContain("const live = jobs.filter(jobIsLive);");
  });
});
