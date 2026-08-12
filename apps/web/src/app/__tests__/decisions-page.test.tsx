/** The `/decisions` pages, and the one thing they must not do.
 *
 * **A gate table is a first-class screen, not a tab under the winner.**
 * Six feasibility gates run before anything is scored (HĐ-7), so a
 * candidate that failed one was never ranked at all. A page that led
 * with the recommendation and hid the gates would invert the contract on
 * screen — and, worse, would make the four runs out of five that produce
 * no card look like broken runs. That reading is what put pressure on
 * every run to be rankable, and that pressure is what produced a card
 * bounding a collision probability off a single episode.
 *
 * Source-level rather than rendered, matching the other page tests: both
 * pages sit behind an effect and a fetch, so a first paint would only
 * show a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { NAV_SECTIONS } from "../../lib/navigation";

const APP = join(process.cwd(), "src", "app");
const LIST = readFileSync(join(APP, "decisions", "page.tsx"), "utf8");
const DETAIL = readFileSync(join(APP, "decisions", "[id]", "page.tsx"), "utf8");

describe("the list shows every run, not only the ones that ranked", () => {
  it("defaults to no outcome filter at all", () => {
    /* Defaulting to "ranked" would present a platform where almost
       nothing happened, while hiding exactly the runs that eliminated
       candidates. */
    expect(LIST).toContain('useState<RankedFilter>("all")');
  });

  it("passes undefined rather than a boolean when the filter is off", () => {
    expect(LIST).toContain('rankedFilter === "all" ? undefined : rankedFilter === "ranked"');
  });

  it("says out loud that most runs produce no card", () => {
    /* Left to be inferred from a row count, "no card" reads as a bug in
       the platform rather than the expected outcome. */
    expect(LIST).toContain("decisions.filter.note");
  });

  it("never colours a cardless run as an error", () => {
    /* Red is the whole difference between "this is a result" and "this
       broke". The reason chips are warn or muted, never err. */
    const tones = LIST.slice(LIST.indexOf("REASON_TONE"), LIST.indexOf("export default"));
    expect(tones).not.toContain('"err"');
  });

  it("shows both episode counts when they differ", () => {
    /* "245" alone reads as a deliberate 245-episode run, which is a
       different claim from "the machine was taken back at 245". */
    expect(LIST).toContain("requested !== measured");
    expect(LIST).toContain("n_episodes_requested");
  });
});

describe("the detail page leads with the gate table", () => {
  it("renders the gate table above the outcome", () => {
    expect(DETAIL.indexOf("<GateTable")).toBeGreaterThan(-1);
    expect(DETAIL.indexOf("<GateTable")).toBeLessThan(DETAIL.indexOf("<Outcome"));
  });

  it("renders all six gates for every candidate, in contract order", () => {
    expect(DETAIL).toContain("GATES.map");
    expect(LIST + DETAIL).toContain("candidate.gates");
  });

  it("shows distinct episodes, not just the run count", () => {
    /* The pair is what a collision bound's denominator actually is: a
       hundred replays of one episode is one independent sample, and
       printing only the run count is how this project once published a
       3.0% upper bound off a single episode driven a hundred times. */
    expect(DETAIL).toContain("n_distinct_episodes");
    expect(DETAIL).toContain("decisions.gates.distinctNote");
  });

  it("carries each gate's evidence, not only its verdict", () => {
    /* "G3: fail" without the numbers cannot be argued with, and a
       verdict nobody can argue with is one people route around. The
       extraction itself is tested in `lib/__tests__/decisions.test.ts`;
       here we only check the page asks for it. */
    expect(DETAIL).toContain("gateEvidence(");
  });

  it("renders both wire shapes of a verdict as the same badge", () => {
    /* Some gates serialise as the bare string "pass", others as an
       object. Plain text beside coloured chips would say they were
       different kinds of judgement. */
    expect(DETAIL).toContain("gateResult(");
    expect(DETAIL).not.toContain("verdict.result");
  });

  it("marks a candidate that was retired before the others", () => {
    /* Its row rests on fewer episodes than the rest of the table, which
       qualifies every number in it. */
    expect(DETAIL).toContain("candidate.stopped_early");
    expect(DETAIL).toContain("decisions.gates.stoppedEarly");
  });
});

describe("a run with no card says which situation it is in", () => {
  it("distinguishes all three, because each asks for a different action", () => {
    for (const reason of ["interrupted", "gate_only", "no_survivors"]) {
      expect(en).toHaveProperty(`decisions.noCard.whatNext.${reason}`);
      expect(vi).toHaveProperty(`decisions.noCard.whatNext.${reason}`);
    }
  });

  it("tells the reader what to do next rather than only what happened", () => {
    expect(DETAIL).toContain("decisions.noCard.whatNext.");
  });

  it("never calls it a failure", () => {
    const heading = (en as Record<string, string>)["decisions.noCard.title"];
    expect(heading.toLowerCase()).not.toContain("fail");
    expect(heading.toLowerCase()).not.toContain("error");
  });

  it("keeps the report's own words available rather than only a summary", () => {
    expect(DETAIL).toContain("why_no_card");
    expect(DETAIL).toContain("gate_only_deployment");
  });

  it("refuses to suggest loosening the deployment", () => {
    /* The only legal exits are a better candidate or a different
       deployment. "Lower the threshold until it passes" is the drift the
       whole platform exists to stop, so the copy names it as forbidden. */
    const advice = (en as Record<string, string>)["decisions.noCard.whatNext.no_survivors"];
    expect(advice).toContain("Never a softer deployment");
  });
});

describe("a Decision Card is shown with its caveats attached", () => {
  it("renders 'not measured' rather than a blank for null sensitivity", () => {
    /* HĐ-12 defines null as "not measured". A blank reads as
       reassurance, so a card that measured nothing would look like one
       that measured everything. */
    expect(DETAIL).toContain("decisions.card.notMeasured");
    expect(DETAIL).toContain("weight_stability_margin === null");
    expect(DETAIL).toContain("anchor_stability === null");
    expect(DETAIL).toContain("robustness_margin === null");
  });

  it("states the scope the recommendation is limited to", () => {
    /* HĐ-1.4: a recommendation is scoped to one deployment, and
       dropping that scope is how it stops being true. */
    expect(DETAIL).toContain("decisions.card.scopeNote");
    expect((en as Record<string, string>)["decisions.card.scopeNote"]).toContain("{scope}");
  });

  it("shows the interval beside the point estimate", () => {
    expect(DETAIL).toContain("evidence.ci95");
    expect(DETAIL).toContain("delta_u_vs_second");
  });
});

describe("the conditions the measurement happened in travel with it", () => {
  it("shows the noise amplitudes", () => {
    /* `episode_context_id` does not hash them (HĐ-3.1): two runs at the
       same seeds under different sigma have identical context ids and
       are two different experiments. If this panel is wrong, nothing
       downstream can tell. */
    expect(DETAIL).toContain("sensor_noise");
  });

  it("surfaces the unpinned-machine warning instead of leaving it in a log", () => {
    expect(DETAIL).toContain("environment?.warning");
  });

  it("shows the trace checksum beside the run URI", () => {
    /* A URI alone cannot say the files behind it are still the ones this
       result came from — that is what the checksum is for (D15). */
    expect(DETAIL).toContain("run_uri");
    expect(DETAIL).toContain("run_checksum");
  });
});

describe("the audit trail", () => {
  it("shows both ends of every change", () => {
    /* "approved" alone does not say what it replaced. */
    expect(DETAIL).toContain("previous_state");
    expect(DETAIL).toContain("new_state");
  });

  it("orders by sequence, not by timestamp", () => {
    /* Two acts can share a clock reading, and "who decided first" is
       exactly what an audit trail is asked. The server orders by
       sequence; the page must not re-sort. */
    expect(DETAIL).not.toContain("sort(");
  });
});

describe("the page is reachable and translated", () => {
  it("has a sidebar entry", () => {
    const hrefs = NAV_SECTIONS.flatMap((section) => section.items).map((item) => item.href);
    expect(hrefs).toContain("/decisions");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set(
      [...LIST.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]),
    );
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});

describe("the two human acts sit below the evidence", () => {
  it("renders the action panel after the gate table and the outcome", () => {
    /* Both acts are claims about evidence the reader is supposed to have
       read. Buttons above the gate table invite the click before the
       reading. */
    expect(DETAIL.indexOf("<HumanActs")).toBeGreaterThan(DETAIL.indexOf("<GateTable"));
    expect(DETAIL.indexOf("<HumanActs")).toBeGreaterThan(DETAIL.indexOf("<Outcome"));
  });

  it("lets a cardless run be read but not approved", () => {
    /* The whole reason the two are separate columns: a run that
       eliminated everybody is still something somebody has to read. */
    expect(DETAIL).toContain('run.config_state !== "not_applicable"');
    expect(DETAIL).toContain("decisions.acts.whyNoConfig");
  });

  it("says why a disabled button is disabled", () => {
    /* A greyed-out control with no explanation reads as a broken page,
       and each of these three reasons asks for a different response. */
    for (const key of ["whyNoConfig", "whyDecided", "whyOwnRun"]) {
      expect(DETAIL).toContain(`decisions.acts.${key}`);
      expect(en).toHaveProperty(`decisions.acts.${key}`);
      expect(vi).toHaveProperty(`decisions.acts.${key}`);
    }
  });

  it("never re-implements a server rule as a client-side verdict", () => {
    /* The page disables the obvious cases so it is not lying about what
       will happen, but every refusal is the server's. A second copy of
       "who may approve" here would be free to drift from the enforced
       one — so the failure path shows the server's message verbatim. */
    expect(DETAIL).toContain("setFailed(caught instanceof Error ? caught.message : String(caught))");
  });

  it("treats a null creator as nobody, not as the current user", () => {
    /* Runs filed by the importer have `created_by: null`. A loose
       equality would make every reader look like the owner and hide the
       approve button from all of them. */
    expect(DETAIL).toContain("session?.user.id != null && session.user.id === run.created_by");
  });

  it("offers the config download only once it is approved", () => {
    expect(DETAIL).toContain('run.config_state === "approved"');
    expect(DETAIL).toContain("approvedConfigUrl(run.id)");
  });

  it("says the export is a file and not a deployment", () => {
    /* HĐ-14: the system is simulation-only and "deploying" is emitting
       a file. The button must not imply otherwise. */
    expect((en as Record<string, string>)["decisions.acts.configNote"]).toContain(
      "simulation-only",
    );
  });
});

describe("starting a sweep from the page", () => {
  it("queues rather than running inside the request", () => {
    /* The episode count comes from the deployment's declared collision
       risk (HĐ-7.1) — a warehouse at 1% is 300 episodes and hours of
       simulation. A button that held the browser open for that is not a
       design, it is an omission. */
    expect(LIST).toContain("queueDecision(");
    expect(LIST).not.toContain("runDecision(");
  });

  it("omits the episode count rather than inventing one", () => {
    /* Blank means "use N_min from the declared risk". Sending a number
       the user did not choose would quietly override the contract's own
       arithmetic. */
    expect(LIST).toContain("Number.isFinite(parsed) && parsed > 0 ? { episodes: parsed } : {}");
  });

  it("allows only one sweep at a time, and says why", () => {
    /* Not a capacity choice: two evaluation runs pin the same cores and
       each becomes the other's background load, so G4 would measure a
       machine that does not exist (HĐ-7.4). */
    expect(LIST).toContain("live.length > 0");
    const note = (en as Record<string, string>)["decisions.launch.oneAtATime"];
    expect(note).toContain("HĐ-7.4");
  });

  it("reports progress in episodes and never fakes a percentage", () => {
    /* `total` is 0 until the sweep reports its first episode, and "0/0"
       is honest where "0%" would be a claim about a denominator nobody
       has yet. */
    expect(LIST).toContain("job.total > 0 ?");
  });

  it("stops polling once nothing is live", () => {
    expect(LIST).toContain("if (!jobs.some(jobIsLive)) return;");
    expect(LIST).toContain("clearInterval(timer)");
  });

  it("links straight to the finished run instead of making the reader search", () => {
    /* The job carries the stored run's id. "The one that appeared
       recently" is not an identity. */
    expect(LIST).toContain("job.run_id");
    expect(LIST).toContain("decisions.job.open");
  });

  it("offers cancel only while a job is live", () => {
    expect(LIST).toContain("jobIsLive(job) ? (");
    expect(LIST).toContain("cancelDecisionJob");
  });
});
