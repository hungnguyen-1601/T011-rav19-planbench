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
import { comparisonRows } from "@/lib/candidateMetrics";
import vi from "../../lib/i18n/locales/vi.json";
import { NAV_SECTIONS } from "../../lib/navigation";

const APP = join(process.cwd(), "src", "app");
const LIST = readFileSync(join(APP, "decisions", "page.tsx"), "utf8");
const DETAIL = readFileSync(join(APP, "decisions", "[id]", "page.tsx"), "utf8");
/* The stylesheet, for the rules this page depends on being absent as
   much as present — a removed column tint leaves nothing to assert on
   in the markup. */
const CSS = readFileSync(join(APP, "globals.css"), "utf8");
/* The comparison table, extracted so tests can render it — a
   function declared inside a fetching page cannot be imported. */
const GRID = readFileSync(
  join(process.cwd(), "src", "components", "ComparisonGrid.tsx"),
  "utf8",
);

/* The modules the page delegates its decisions to. Asserting a key on
   the page would fail by design: the page renders `t(verdict.key)` and
   the key is chosen where the rule lives. */
const GATE_LIB = readFileSync(join(process.cwd(), "src", "lib", "gateSummary.ts"), "utf8");
/* Read here because of one assertion below: the map editor is where
   people go looking for the start and the goal, and it has to send them
   to the page that actually has them. */
const MAP_EDITOR = readFileSync(join(APP, "maps", "[id]", "page.tsx"), "utf8");
/* Placing a start and a goal, and painting cells, are shared components:
   the launch panel and the deployment form both need them, and two
   copies would be two answers to the same question. The assertions below
   follow the code into them — same claims, different file. */
const COMPONENTS = join(process.cwd(), "src", "components");
const PLACER = readFileSync(join(COMPONENTS, "MissionPlacer.tsx"), "utf8");
const PAINTER = readFileSync(join(COMPONENTS, "MapPainter.tsx"), "utf8");
const DEPLOYMENT_PREVIEW = readFileSync(join(COMPONENTS, "DecisionDeploymentPreview.tsx"), "utf8");

describe("the selected deployment preview", () => {
  it("sits after the candidate selectors and before the rank action", () => {
    expect(LIST.indexOf("<DecisionDeploymentPreview")).toBeGreaterThan(LIST.indexOf("comparison-setup-grid"));
    expect(LIST.indexOf("<DecisionDeploymentPreview")).toBeLessThan(LIST.indexOf("comparison-launch-actions"));
  });

  it("is read-only and does not reset either candidate", () => {
    expect(DEPLOYMENT_PREVIEW).toContain("<MapView");
    expect(DEPLOYMENT_PREVIEW).not.toMatch(/<(input|select|textarea|checkbox)\b/);
    expect(DEPLOYMENT_PREVIEW).not.toContain("setFirst(");
    expect(DEPLOYMENT_PREVIEW).not.toContain("setSecond(");
  });

  it("clears a stale map and isolates map loading failures", () => {
    expect(DEPLOYMENT_PREVIEW).toContain("setMap(null)");
    expect(DEPLOYMENT_PREVIEW).toContain("api.getMap");
    expect(DEPLOYMENT_PREVIEW).toContain("decision-deployment-map-error");
    expect(DEPLOYMENT_PREVIEW).toContain("decision-deployment-details");
  });

  it("keeps the map and compact read-only details in one responsive layout", () => {
    expect(DEPLOYMENT_PREVIEW).toContain("decision-deployment-content");
    expect(DEPLOYMENT_PREVIEW.indexOf("decision-deployment-map-column")).toBeLessThan(DEPLOYMENT_PREVIEW.indexOf("decision-deployment-details"));
    expect(DEPLOYMENT_PREVIEW).toContain("aria-expanded={showAdvanced}");
    expect(DEPLOYMENT_PREVIEW).toContain("decision-noise-details");
  });
});

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
    // There is no gate table any more. Every candidate has a card
    // carrying G1–G6 and its blocking list, and the comparison table
    // under the cards carries the numbers the table held — for all
    // of them, not the first two.
    expect(DETAIL).not.toContain("<GateTable");
    // The metrics are one table inside the comparison section: names
    // down a column, candidates across, so a comparison is a glance
    // along a row. The cards above carry no metric rows — that overlap
    // is what made an earlier version of this table redundant.
    // One grid: a neutral gutter of metric names, then one tinted
    // column per candidate carrying its identity, its values and its
    // gate verdicts. No metric appears twice.
    // Now a real `<table>`, not a flat grid. A `<tr>` is a row, so the
    // flags row emitting one cell fewer can no longer shift every cell
    // after it — the failure the old grid had exactly when a candidate
    // carried a finding.
    expect(GRID).toContain('<table className="comparison-table">');
    expect(GRID).toContain("comparison-gutter comparison-label");
    expect(GRID).toContain('<th scope="col"');
    expect(DETAIL).not.toContain("<MetricTable");
    expect(DETAIL).not.toContain("metric-comparison-row");
    expect(DETAIL.indexOf("<CandidateComparison")).toBeLessThan(DETAIL.indexOf("<Outcome"));
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
    // The gate table carried this in a tooltip; it is a row of the
    // comparison table now, with the same point spelled out in the
    // hint beside it rather than hidden on hover over a header.
    // Asserted against the module that defines the row, not the page:
    // the page interpolates `decisions.compare.${metric.key}`, so it
    // never spells any metric name and a source scan of it would pass
    // with the row deleted.
    expect(
      comparisonRows([]).map((row) => row.key),
    ).toContain("distinctEpisodes");
    expect(en).toHaveProperty("decisions.compare.distinctEpisodes");
    expect((en as Record<string, string>)["decisions.compare.why.distinctEpisodes"]).toContain("once per seed");
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
    expect(GRID).toContain("candidate.stopped_early");
    expect(GRID).toContain("decisions.gates.stoppedEarly");
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

describe("what the removed panels took with them", () => {
  /* An asked for three panels to go for now: the measurement
     environment, the ids for rebuilding a run, and the journal of who
     read it. Their tests go with them rather than being re-aimed at
     nothing — the assertions were about markup that is no longer
     rendered, and a test kept alive against a deleted feature is a test
     that will be "fixed" by somebody who does not know why it existed.

     Git holds the components. What follows is the one thing that could
     not leave with them. */

  it("keeps the unpinned-machine warning, above the number it qualifies", () => {
    /* G4 reads wall-clock latency, so an unpinned run measured a machine
       that was also doing something else — the same candidate came out
       at 59.30 ms unpinned and 16.10 ms pinned to two cores. The
       comparison grid shows pooled p99 against the deployment's limit,
       and a figure that may be several times too high is worse company
       for a limit than no figure would be. */
    expect(DETAIL).toContain("<HostWarning run={run} />");
    expect(DETAIL).toContain("run.report?.measurement_environment");
  });

  it("puts it with the other finding that qualifies the whole grid", () => {
    /* The host warning is no longer a banner over the table: G4 reads
       wall-clock latency, so it qualifies the p99 row and nothing else,
       and above the table it claimed more than the measurement supports.
       It is passed into the grid and rendered in that row's label. */
    expect(DETAIL).toContain("hostWarning={<HostWarning run={run} />}");
    expect(DETAIL.indexOf("<ObservationNotice")).toBeLessThan(
      DETAIL.indexOf("<ComparisonGrid"),
    );
    expect(GRID).toContain('metric.key === "p99" ? hostWarning : null');
  });

  it("never words the caveat itself, in either branch", () => {
    /* The old rule was that the platform's sentence is rendered
       verbatim, because a client that rewords a caveat can water it
       down. It was right about why and wrong about what: the *numbers*
       must survive untouched, the language need not, and freezing both
       put a Vietnamese paragraph on the English page.

       So there are exactly two paths, and neither is the page composing
       prose: a dictionary key whose text is reviewed like every other
       string, or the platform's own sentence passed through. The choice
       between them is `hostWarningView`, tested over all four payload
       shapes in `lib/__tests__/decisions.test.ts`. */
    expect(DETAIL).toContain("hostWarningView(");
    expect(DETAIL).toContain("view.translated ? t(view.key, view.vars) : view.text");
  });

  it("stops fetching the journal it no longer draws", () => {
    /* A request whose response nothing reads is a request that keeps
       working long after it stops meaning anything. */
    expect(DETAIL).not.toContain("listDecisionEvents");
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

describe("the list says what a run concluded, not which hash it picked", () => {
  it("names the winner by stack and controller", () => {
    /* `recommended_candidate_id` is the right identity for a trace path
       and the wrong thing in front of somebody scanning ten rows for the
       run that chose something. */
    expect(LIST).toContain("runOutcome(run)");
    expect(LIST).toContain("outcome.winner");
    expect(LIST).not.toContain("{run.recommended_candidate_id}");
  });

  it("shows how many candidates cleared the gates, ranked or not", () => {
    /* A recommendation out of two survivors and one out of five are
       different claims, and a run where nobody cleared is a result
       rather than a failure (HĐ-7). */
    expect(LIST).toContain("decisions.outcome.cleared");
    expect(en).toHaveProperty("decisions.outcome.cleared");
    expect(vi).toHaveProperty("decisions.outcome.cleared");
  });

  it("still keeps the three no-card reasons apart", () => {
    /* Adding a gate count must not collapse them: each asks for a
       different next action. */
    expect(LIST).toContain("decisions.reason.${reason}");
  });
});

describe("choosing a map for the sweep", () => {
  it("defaults to the deployment's own map", () => {
    /* Every existing flow has to keep working without a click, and a
       map picker that started empty would make "same as before" a
       decision somebody has to make each time. */
    expect(LIST).toContain("NO_CUSTOM_MAP");
    expect(LIST).toContain("decisions.map.sameAsDeployment");
  });

  it("files a NEW deployment rather than editing the chosen one", () => {
    /* A map is the world, and `episode_context_id` does not hash it
       (HĐ-3.1). Repointing an existing id would give two worlds'
       episodes identical context ids, and trace reuse would then serve
       episodes driven on walls that are gone. */
    expect(LIST).toContain("deriveTaskProfile(");
    expect(LIST).toContain("base_task_profile_id: profileId");
    expect(LIST).toContain("new_id: custom.newProfileId.trim()");
  });

  it("runs the sweep on the derived id, not on the base", () => {
    /* Deriving and then queueing on the original would measure the old
       map while the reader believes they chose another one. */
    expect(LIST).toContain("task_profile_id: target");
  });

  it("refuses to launch a half-filled custom map", () => {
    /* Silently falling back to the deployment's own map is the failure
       mode: the run would be valid and answer a different question. */
    expect(LIST).toContain('custom.mapId !== "" && !customReady');
  });

  it("requires a start and a goal before it will launch", () => {
    /* A start and goal that fit the reference hall are rarely on free
       floor in a map somebody drew. The server refuses the pair it
       cannot place, but a disabled button says so before the round
       trip. */
    expect(LIST).toContain("custom.start !== null");
    expect(LIST).toContain("custom.goal !== null");
  });

  it("draws the map at the deployment's robot radius", () => {
    /* A start that looks clear at one pixel per cell can be one the
       robot does not fit in, and that is invisible without the circle. */
    expect(LIST).toContain("readRobotRadius(base)");
    expect(LIST).toContain("robotRadius={robotRadius}");
  });

  it("clears the poses when the map changes", () => {
    /* A start kept from the previous map is a coordinate that means
       something else here — and it might still land on free floor, so
       nothing would catch it. */
    expect(LIST).toContain("...NO_CUSTOM_MAP, newProfileId: value.newProfileId");
  });

  it("says why the map picker is off rather than leaving it greyed", () => {
    /* Both reasons are one click from fixed — choose a deployment, or
       draw a map — so which one it is *is* the useful part. A disabled
       control with no explanation reads as a broken page, and this one
       sent a reader hunting for start/goal in the map editor, where they
       are not and cannot be. */
    expect(LIST).toContain("decisions.map.pickDeploymentFirst");
    expect(LIST).toContain("decisions.map.noMapsYet");
    for (const key of ["pickDeploymentFirst", "noMapsYet"]) {
      expect(en).toHaveProperty(`decisions.map.${key}`);
      expect(vi).toHaveProperty(`decisions.map.${key}`);
    }
  });

  it("sends the reader to the existing editor instead of growing a second one", () => {
    /* `/maps` already versions and checksums what it stores. Two
       editors would be two definitions of the same thing. */
    expect(LIST).toContain('href="/maps"');
    expect(LIST).toContain("decisions.map.drawOne");
  });

  it("says in words why a different map means a different deployment", () => {
    expect((en as Record<string, string>)["decisions.map.note"]).toContain("HĐ-3.1");
    expect((vi as Record<string, string>)["decisions.map.note"]).toContain("HĐ-3.1");
  });
});

describe("placing the start and the goal", () => {
  it("makes the placement mode explicit, with a caption", () => {
    /* The scenario editor's shape, and for its reason: the author has to
       see what the next click does. A hidden alternation makes nudging a
       start two pixels drop a goal instead. */
    expect(PLACER).toContain("decisions.map.place.${which}");
    /* The caption became its own component when the deployment form put
       the buttons in a tab panel and the map in another column — same
       key, same rule, one variable name further out. */
    expect(PLACER).toContain("decisions.map.mode.${mode}");
    /* Both branches of each templated key, since the coverage check
       above only sees literal ones. */
    for (const which of ["start", "goal"]) {
      expect(en).toHaveProperty(`decisions.map.place.${which}`);
      expect(vi).toHaveProperty(`decisions.map.place.${which}`);
    }
    for (const mode of ["none", "start", "goal"]) {
      expect(en).toHaveProperty(`decisions.map.mode.${mode}`);
      expect(vi).toHaveProperty(`decisions.map.mode.${mode}`);
    }
  });

  it("advances to the goal only while the goal is unset", () => {
    /* Convenience on the first pass, and no surprise afterwards:
       correcting a start must not drop a goal on top of it. */
    expect(PLACER).toContain('if (goal === null) setPlacing("goal")');
  });

  it("moves a pose by dragging as well as by clicking", () => {
    /* Dragging belongs to the poses and to nothing else. `MapCanvas`
       fires a press and then a move per pixel travelled, which is what
       makes nudging a start feel continuous — and what would make one
       careless gesture append a waypoint per pixel once the deployment
       form started placing traffic on this same canvas. So a drag
       reaches `place` only while a mission mode is the one holding the
       next click.

       **Two lifecycles, one rule.** This screen still uses the legacy
       props, where the drag handler is simply not attached outside a
       mission mode. The deployment form lifts the full pointer
       lifecycle to drag traffic handles, and there the same condition
       is a guard on the move. Both are checked, because a rule enforced
       on one path and forgotten on the other is the failure this test
       exists to catch. */
    expect(PLACER).toContain("missionMode");
    expect(PLACER).toMatch(/missionMode\s*\n?\s*\?\s*\{\s*onWorldDrag/);
    expect(PLACER).toContain("if (missionMode && info.event.buttons !== 0) place(point.x, point.y)");
  });

  it("lets a pose be typed as well as clicked", () => {
    /* A canvas cannot land on 2.00 exactly, and a deployment written to
       two decimals is the one somebody can repeat from the report. */
    expect(PLACER).toContain("<PoseFields");
    expect(PLACER).toContain('type="number"');
  });

  it("keeps the heading when the position moves", () => {
    /* Dragging a start must not silently spin the robot back to facing
       east — the heading is a separate choice the author already made. */
    expect(PLACER).toContain("theta: start?.theta ?? 0");
    expect(PLACER).toContain("theta: goal?.theta ?? 0");
  });

  it("edits the heading in degrees and stores radians", () => {
    /* The contract stores radians; nobody types 1.5708 for a quarter
       turn. */
    expect(PLACER).toContain("DEGREES(value.theta)");
    expect(PLACER).toContain("RADIANS(Number(event.target.value))");
  });

  it("sends the heading in the mission rather than zeroing it", () => {
    /* The simulator seeds `RobotState(pose=start_pose)`, so a robot
       pointed away from its goal spends its first second turning. A
       hardcoded 0 here would quietly discard the author's choice. */
    expect(LIST).toContain("custom.start!.theta");
    expect(LIST).toContain("custom.goal!.theta");
  });

  it("says the start heading is real and the goal heading is not", () => {
    /* This platform has no final-orientation controller, so every
       deployment must declare goal_tolerance_rad >= pi and arrival is
       decided on position alone (HĐ-6). An unlabelled dial that changes
       no verdict is the thing to avoid. */
    expect((en as Record<string, string>)["decisions.map.goalHeadingNote"]).toContain("HĐ-6");
    expect((vi as Record<string, string>)["decisions.map.goalHeadingNote"]).toContain("HĐ-6");
    expect((en as Record<string, string>)["decisions.map.startHeadingNote"]).toContain("t = 0");
  });

  it("paints cells through one component, not two", () => {
    /* The map editor has painted cells since Phase 1 and the deployment
       form needs the same thing inline. Two editors would be two
       definitions of what painting a map means, free to drift — the
       argument that already kept the launch panel from growing its own.
       So the editor page owns loading and saving, and nothing else. */
    expect(MAP_EDITOR).toContain("<MapPainter");
    expect(MAP_EDITOR).not.toContain("worldToCell");
    expect(MAP_EDITOR).not.toContain("BRUSH_VALUE");
    expect(PAINTER).toContain("worldToCell(map, x, y)");
  });

  it("leaves saving to whoever owns the map", () => {
    /* `/maps/[id]` PUTs a new version by id; the deployment form holds
       an unsaved grid until the profile is filed. A painter that knew
       about `api.updateMap` could only ever serve the first. */
    expect(PAINTER).not.toContain('from "@/lib/api"');
    expect(MAP_EDITOR).toContain("api.updateMap");
  });

  it("tells the map editor where the poses actually live", () => {
    /* A map is walls, and `MapData` has no pose fields — the same
       warehouse serves many missions, so the pair belongs to the
       deployment rather than to the map. That is a good reason and a
       poor excuse for silence: the editor is the first place somebody
       looks, so it has to point at the page that has them. */
    expect(MAP_EDITOR).toContain("maps.whereArePoses");
    expect(MAP_EDITOR).toContain('href="/decisions"');
    expect(en).toHaveProperty("maps.whereArePoses");
    expect(vi).toHaveProperty("maps.whereArePoses");
  });

  it("keeps the pose in one place, which is what makes it two-way", () => {
    /* Dragging updates the numbers and typing moves the marker because
       there is exactly one `Pose2D` and both halves read and write it.
       A local `useState` here "so the input feels snappier" would give
       the canvas and the fields their own copies, and one of them would
       start winning silently.

       The placer may hold the *mode* — that is a tool selection, not
       data — and nothing else. */
    const states = [...PLACER.matchAll(/useState<([^>]*)>/g)].map((match) => match[1]);
    expect(states).toEqual(["PlacementMode"]);
    expect(PLACER).not.toContain("useState<Pose2D");
  });

  it("draws the goal circle at the deployment's own tolerance", () => {
    /* An episode ends the moment the robot is inside it, so a goal
       placed a tolerance-width from a shelf is a different mission from
       one placed a metre out. */
    expect(LIST).toContain("readGoalTolerance(base)");
    expect(LIST).toContain("goalTolerance={goalTolerance}");
  });
});

describe("which episodes failed, and how", () => {
  it("puts the outcome table above the trace viewer it feeds", () => {
    /* The gate table says how much went wrong, this says which part,
       and the viewer draws one of them. Below the viewer instead, the
       table would be a caption for a picture already chosen. */
    expect(DETAIL.indexOf("<EpisodeOutcomes")).toBeGreaterThan(-1);
    expect(DETAIL.indexOf("<EpisodeOutcomes")).toBeLessThan(DETAIL.indexOf("<TraceViewer"));
  });

  it("distinguishes all four failure reasons", () => {
    /* Thirty collisions and thirty timeouts give the same success rate
       and ask for completely different work (HĐ-6). */
    for (const reason of ["collision", "timeout", "stuck", "no_path"]) {
      expect(en).toHaveProperty(`decisions.episodes.reason.${reason}`);
      expect(vi).toHaveProperty(`decisions.episodes.reason.${reason}`);
    }
  });

  it("reads a missing table as 'not recorded', never as 'all passed'", () => {
    /* Runs stored before the field existed carry no episode rows, and a
       clean table for them would report a measurement nobody made. */
    expect(DETAIL).toContain("hasEpisodeOutcomes(run)");
    expect(DETAIL).toContain("decisions.episodes.notRecorded");
  });

  it("pairs candidates by episode id, not by array position", () => {
    /* Early stopping retires one candidate mid-sweep, so row seven of
       one array and row seven of the other can be different episodes. */
    expect(DETAIL).toContain("outcomesByEpisode(");
  });

  it("marks episodes a retired candidate never ran", () => {
    /* Not the same claim as driven and passed, and it is what explains
       the smaller denominator on that candidate's row. */
    expect(DETAIL).toContain("decisions.episodes.notRun");
    expect(en).toHaveProperty("decisions.episodes.notRunNote");
  });

  it("opens a whole episode row without asking for a candidate", () => {
    /* Finding the episode that collided and then copying its id into a
       dropdown is most of the work of looking at it. */
    expect(DETAIL).toContain("onClick={() => onPick(episode)}");
    expect(DETAIL).toContain('aria-selected={episode === selectedEpisode}');
    expect(DETAIL).toContain('event.key === "Enter" || event.key === " "');
  });

  it("drives every episode picker from one piece of state", () => {
    // The dropdown is gone — it listed ids and nothing else, so picking
    // from it was picking blind. What remains are the table rows, the
    // exemplar chips and the pager, and they must all read and write
    // the same selection or the canvases will show a different episode
    // than the table highlights.
    expect(DETAIL).toContain("const [episodeId, setEpisodeId]");
    expect(DETAIL).toContain("selectedEpisode={episodeId}");
    expect(DETAIL).toContain("void loadPair(episodeId)");
    expect(DETAIL).not.toContain("const [candidateId, setCandidateId]");
  });

  it("no longer offers an id-only dropdown", () => {
    const toolbar = DETAIL.slice(DETAIL.indexOf('className="episode-toolbar"'));
    expect(toolbar.slice(0, 600)).not.toContain("<select");
  });

  it("pages the episode table instead of listing every row", () => {
    // Three hundred episodes would otherwise make the table the page.
    expect(DETAIL).toContain("<EpisodePager");
    expect(DETAIL).toContain("pageSlice(shown, current)");
    expect(DETAIL).toContain("clampPage(page, shown.length)");
  });

  it("follows the selection onto its page", () => {
    // Exemplar chips move the episode from outside the table; leaving
    // the strip where it was highlights nothing and reads as the pick
    // not registering.
    expect(DETAIL).toContain("setPage(pageOf(index))");
  });

  it("keeps candidate A left, candidate B right and tolerates one missing trace", () => {
    // The pair colours still only cover two; past that the column is
    // neutral rather than reusing candidate A's blue for candidate C.
    expect(DETAIL).toContain('candidate-${SIDES[index] ?? "n"}');
    expect(DETAIL).toContain('const SIDES = ["a", "b"] as const');
    expect(DETAIL).toContain('{ state: "missing" }');
    expect(DETAIL).toContain('slot.state === "ready"');
    expect(DETAIL).toContain('trace.missing');
  });

  it("offers the preregistered four, and both extremes among them", () => {
    // Which pair loads first is a choice that looks like evidence, so a
    // recipe makes it. Showing the winner's best without the
    // runner-up's is the cherry-pick that recipe exists to prevent.
    expect(DETAIL).toContain("getExemplars(run.id)");
    expect(DETAIL).toContain("trace.exemplar.");
    expect(DETAIL).toContain("item.tie_break_over.length > 0");
  });

  it("falls back to the plain episode list when no recipe answer exists", () => {
    // A run scored before per-episode utility was stored has no ΔU, so
    // three of the four roles cannot be filled. An empty set is the
    // honest state — not a set chosen another way under the label.
    expect(DETAIL).toContain("setExemplars([])");
    expect(DETAIL).toContain("exemplars.length > 0");
  });

  it("keeps the alignment toggle apart from the draw mode", () => {
    // `mode` is flat/raised — how the map is *drawn*. Reusing that name
    // for time/progress would read, to the next person, as if the page
    // already had two sync modes.
    expect(DETAIL).toContain('const [syncMode, setSyncMode]');
    expect(DETAIL).toContain('"time" | "progress"');
    expect(DETAIL).toContain('t("trace.sync.mode")');
  });

  it("says what this run may be explained with before showing any of it", () => {
    // The caveats render above the evidence: a qualifier below the fold
    // qualifies nothing. And three of the five outcomes have no paired
    // comparison, so the page reads the plan rather than deciding.
    expect(DETAIL).toContain("<ExplanationHeader");
    expect(DETAIL).toContain('panelPlan(run)');
    expect(DETAIL).toContain("plan.caveatKeys.map");
    expect(DETAIL).toContain("if (!plan.showTraceEvidence) return null;");
    // Exemplars are gated separately: a run with no ranked pair still
    // has traces worth opening.
    expect(DETAIL).toContain("plan.showExemplars && exemplars.length > 0");
  });

  it("hands the panel work to a component a test can render", () => {
    // These used to be four source-string assertions on this file. They
    // moved with the code they describe: the caveat, the ruler and the
    // divergence chips are now asserted against rendered HTML in
    // `progress-sync.test.tsx`, and the pairing in
    // `lib/__tests__/replay-sync.test.ts` — both of which can fail for
    // the right reason, which a string search cannot.
    expect(DETAIL).toContain("<ProgressSync");
    expect(DETAIL).toContain('from "@/components/ProgressSync"');
    expect(DETAIL).toContain("panelCandidates(run,");
  });

  it("shares top/raised mode and playback across both candidates", () => {
    expect(DETAIL).toContain('const [mode, setMode]');
    expect(DETAIL).toContain('mode={mode}');
    expect(DETAIL).toContain('playbackTime={at}');
    expect(DETAIL).toContain('syncMode === "progress" ? sideTime(view, scan.time, side) : playback.time');
    expect(DETAIL).toContain('[0.25, 0.5, 1, 2, 4, 8]');
  });

  it("can narrow to the failures, and says how many it is hiding", () => {
    /* A warehouse sweep is three hundred rows and most of them are two
       greens. Filtering is the point; a silent cap would not be — a
       table showing the first fifty rows reads as a complete one. */
    expect(DETAIL).toContain("decisions.episodes.failuresOnly");
    expect(DETAIL).toContain("decisions.episodes.showing");
    expect(en).toHaveProperty("decisions.episodes.showing");
    expect(vi).toHaveProperty("decisions.episodes.showing");
  });

  it("numbers episodes by their place in the run, not in the filtered table", () => {
    /* Otherwise "#7 collided" means a different episode with the filter
       on than off, and the number stops being a reference. */
    expect(DETAIL).toContain("episodes.indexOf(episode) + 1");
  });

  it("has every key the detail page asks for, in both locales", () => {
    const keys = new Set([...DETAIL.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});

describe("the list is a catalogue, not a leaderboard", () => {
  it("counts what has been measured without ranking it", () => {
    /* The overview `/leaderboard` provided, rebuilt on the one thing it
       may rest on. "Seven comparisons across three deployments" is a
       fact about the work; a ranking of candidates across deployments is
       a claim HĐ-1.4 forbids. */
    expect(LIST).toContain("function summarise(");
    expect(LIST).toContain("decisions.tally.deployments");
    expect((en as Record<string, string>)["decisions.tally.note"]).toContain("not a ranking");
  });

  it("shows decision utility only once the list is one deployment", () => {
    /* `decision_utility` is comparable **within** a deployment and
       meaningless across them. A sortable column of it over a mixed list
       would rebuild the cross-scenario ranking under a different name —
       the single trap this page has to avoid. */
    expect(LIST).toContain('const oneDeployment = profileId !== ""');
    expect(LIST).toContain("{oneDeployment ? <th>");
    expect((en as Record<string, string>)["decisions.tally.note"]).toContain("HĐ-1.4");
  });

  it("never sorts the rows itself", () => {
    /* The server returns them in one order. A client-side sort by any
       score column is how a catalogue becomes a ranking by accident. */
    expect(LIST).not.toContain(".sort(");
  });

  it("filters by what a human has done with a run", () => {
    /* Read, not read, approved — the three states somebody scanning for
       their own next action actually wants. */
    for (const key of ["unreviewed", "reviewed", "approved"]) {
      expect(en).toHaveProperty(`decisions.filter.${key}`);
      expect(vi).toHaveProperty(`decisions.filter.${key}`);
    }
    expect(LIST).toContain("reviewFilter");
  });
});

describe("the sample line replaced the row of figures", () => {
  it("no longer draws three cards that read the same number", () => {
    /* `30 measured`, `30 requested`, `30 N_min` — one number three
       times, at the largest type on the page. A figure earns a card when
       it is abnormal; when it is fine it earns a clause. */
    expect(DETAIL).not.toContain("decisions.sample.measured");
    expect(DETAIL).not.toContain("decisions.sample.requested");
    expect(DETAIL).not.toContain("decisions.sample.nMin");
    expect(DETAIL).not.toContain("SampleBanner");
  });

  it("puts the line in the page head and the notice above the panels", () => {
    /* Order is the argument: a notice saying the sample is too small
       qualifies every number under it, so it cannot sit below them. */
    expect(DETAIL).toContain("<SampleLine run={run} />");
    expect(DETAIL).toContain("<SampleNotice run={run} />");
    expect(DETAIL.indexOf("<SampleNotice run={run} />")).toBeLessThan(
      DETAIL.indexOf("<CandidateComparison run={run} />"),
    );
  });

  it("decides nothing inside the component", () => {
    /* No jsdom in this repo, so a rule written in JSX is a rule no test
       can reach. Both components read their answer from `lib/sample`. */
    expect(DETAIL).toContain('from "@/lib/sample"');
    expect(DETAIL).toContain("sampleLineFor(run)");
    expect(DETAIL).toContain("noticeKey(sampleNotice(sample))");
  });

  it("carries both N_min wordings, in both languages", () => {
    for (const key of [
      "decisions.sample.line.measured",
      "decisions.sample.line.meetsNMin",
      "decisions.sample.line.belowNMin",
      "decisions.sample.line.full",
      "decisions.sample.line.coverage",
      "decisions.sample.belowNMinInterrupted",
    ]) {
      expect(en, key).toHaveProperty(key);
      expect(vi, key).toHaveProperty(key);
    }
  });

  it("prints both numbers in the below-N_min wording", () => {
    /* `N_min required: 30` alone does not say how short the run fell. */
    for (const dict of [en, vi] as Record<string, string>[]) {
      const below = dict["decisions.sample.line.belowNMin"];
      expect(below).toContain("{n}");
      expect(below).toContain("{min}");
    }
  });

  it("keeps HTML out of the dictionary", () => {
    /* `translate` returns a plain string and React escapes it, so a
       `<b>` in a locale file renders as four visible characters. The
       emphasis lives in the markup instead. */
    for (const dict of [en, vi] as Record<string, string>[]) {
      expect(dict["decisions.sample.line.measured"]).not.toContain("<");
    }
    expect(DETAIL).toContain("<b>{line.params.n}</b>");
  });
});

describe("the column head names what actually differs", () => {
  it("does not hard-code either field", () => {
    /* Both hard-codings produce the same bug — two heads reading the
       same words. `stack_label` gives `astar+dwa` twice on a
       local-controller comparison; `local_controller_config` gives
       `dwa_coarse` twice on a global-planner one, which is the commoner
       run. The choice is made from the data. */
    expect(DETAIL).toContain("headingField(candidates)");
    expect(GRID).toContain("candidateNames(candidate, heading)");
    expect(GRID).not.toContain("<h4>{candidate.stack_label}</h4>");
    expect(DETAIL).not.toContain("<h4>{candidate.stack_label}</h4>");
  });

  it("chooses per panel, never per column", () => {
    /* Two columns cannot disagree about what this comparison varied, so
       the choice is made above the `.map` and passed down. The trace
       panel makes it again — from the *whole* report, not from its own
       reordered subset — so the two panels cannot name one candidate two
       different things. */
    expect(DETAIL).toContain("const heading = headingField(candidates);");
    expect(DETAIL).toContain("const heading = headingField(run.report?.candidates ?? []);");
    for (const call of DETAIL.match(/headingField\([^)]*\)/g) ?? []) {
      expect(call).not.toContain("candidate.");
    }
  });

  it("names the replay cards by the same field as the grid", () => {
    /* Otherwise a local-controller run reads `dwa_coarse` / `dwa_balanced`
       at the top of the page and `astar+dwa` twice further down. */
    expect(DETAIL).toContain("heading={heading}");
    expect(GRID).toContain("<h4>{names.heading}</h4>");
  });

  it("disambiguates the two final-results buttons by that field too", () => {
    /* The accessible name used the stack, which is identical on both
       sides of a local-controller comparison — so a screen reader heard
       the same label twice. */
    expect(DETAIL).toContain("} — ${names.heading}`}");
    expect(DETAIL).not.toContain("} — ${candidate.stack_label}`}");
  });

  it("drops the icon that was the same glyph on both candidates", () => {
    expect(DETAIL).not.toContain("candidate-result-icon");
    expect(CSS).not.toContain(".candidate-result-icon");
  });

  it("keeps the observation finding after moving the class to the sub-line", () => {
    /* The class itself is now under the heading. What stays in the flags
       row is the case where nobody declared one — an empty cell there
       would read as "same as the rest". */
    expect(DETAIL).toContain("decisions.gates.observationUnknown");
    expect(DETAIL).not.toContain('<span className="badge muted-badge">{candidate.local_observation_class}</span>');
  });

  it("does not draw a flags row when there is nothing to flag", () => {
    /* A row of empty bordered cells is not a finding. */
    expect(GRID).toContain("const hasFlags = candidates.some(");
    expect(GRID).toContain("{hasFlags ?");
  });
});

describe("the comparison grid stopped tinting whole columns", () => {
  it("caps the head instead of washing the column", () => {
    /* A wash down the column swallows the numbers it sits behind, on a
       table whose entire job is the figures. */
    expect(CSS).not.toContain(".comparison-cell.candidate-a {");
    expect(CSS).not.toContain(".comparison-cell.candidate-b {");
    expect(CSS).toContain(".comparison-grid-head.candidate-a { border-top-color: var(--candidate-a); }");
  });

  it("leaves no column tinted, including a third candidate", () => {
    /* `candidate-n` is the fallback past B. Keeping its grey wash after
       A and B lost theirs would tint exactly the column with no colour
       of its own. */
    expect(CSS).not.toContain(".comparison-cell.candidate-n");
  });

  it("colours the heading with a selector that reaches no further", () => {
    /* The class sits on the head cell itself, so a descendant form would
       reach into any `.candidate-a` container that later grows an h4. */
    expect(CSS).not.toContain(".candidate-a .comparison-grid-head h4");
    expect(CSS).toContain(".comparison-grid-head.candidate-a h4");
  });
});

describe("the gate verdict moved to the column head", () => {
  it("puts pass or fail beside the candidate's name", () => {
    /* Six gates run before anything is scored (HĐ-7), so a candidate
       that failed one was never ranked at all. Reading that eleven
       metric rows down inverts the contract on screen. */
    expect(GRID).toContain("gateVerdictBadge(candidate)");
    expect(GATE_LIB).toContain("decisions.gates.badge.cleared");
    expect(GATE_LIB).toContain("decisions.gates.badge.blocked");
    for (const key of ["decisions.gates.badge.cleared", "decisions.gates.badge.blocked"]) {
      expect(en, key).toHaveProperty(key);
      expect(vi, key).toHaveProperty(key);
    }
  });

  it("uses the badge classes the stylesheet actually has", () => {
    /* `.badge.ok` / `.badge.err` exist; `.badge--ok` does not, and
       writing it would leave an unstyled badge for the whole gap
       between this plan and the one that renames them. */
    expect(CSS).toContain(".badge.ok");
    expect(CSS).toContain(".badge.err");
    expect(DETAIL).not.toContain("badge--");
    expect(GRID).not.toContain("badge--");
  });

  it("collapses the six cells below the metric grid", () => {
    expect(DETAIL).toContain('<details className="comparison-gate-detail">');
    expect(GRID).not.toContain("comparison-grid-foot");
    expect(CSS).not.toMatch(/^\.comparison-grid-foot\s*\{/m);
  });

  it("summarises the field as a ratio, never as one side's verdict", () => {
    /* The badge sits on the control that decides whether the detail is
       opened, so `cleared` over a field where somebody was eliminated is
       wrong at the point of maximum cost. Three states, not two. */
    for (const key of ["allCleared", "someBlocked", "allBlocked"]) {
      expect(en, key).toHaveProperty(`decisions.gates.summary.${key}`);
      expect(vi, key).toHaveProperty(`decisions.gates.summary.${key}`);
    }
    expect(DETAIL).toContain("gateSummary(candidates)");
  });

  it("counts in the summary wording rather than asserting a state", () => {
    const dicts = [en, vi] as Record<string, string>[];
    for (const dict of dicts) {
      expect(dict["decisions.gates.summary.someBlocked"]).toContain("{blocked}");
      expect(dict["decisions.gates.summary.someBlocked"]).toContain("{total}");
      /* And the partial case must not use the word the all-clear case
         uses — that was the original mistake. */
      expect(dict["decisions.gates.summary.someBlocked"]).not.toBe(
        dict["decisions.gates.summary.allCleared"],
      );
    }
  });

  it("names each candidate in the detail the way the head did", () => {
    expect(DETAIL).toContain("candidateNames(candidate, heading).heading");
  });
});

describe("the value cell aligns its decimals", () => {
  it("does not centre the numbers", () => {
    /* `text-align: center` was declared in the same rule as
       `font-variant-numeric: tabular-nums` and cancelled it: tabular
       figures give every digit the same width, and centring then throws
       that away by moving the whole string. `7.85 ms` and `17.89 ms`
       ended up a character apart. */
    const rule = CSS.slice(
      CSS.indexOf(".comparison-value {"),
      CSS.indexOf("}", CSS.indexOf(".comparison-value {")),
    );
    expect(rule).not.toContain("text-align: center");
    expect(rule).toContain("font-variant-numeric: tabular-nums");
    expect(rule).toContain("grid-template-columns");
  });

  it("gives the unit its own lane, in the sans face", () => {
    /* Right-aligning the whole string is not enough — `ms` is wider than
       `m` is wider than `MB`, so the unit pushes each number a different
       distance from the edge. And the unit must not be mono: it would
       then join the tabular grid the digits are keeping. */
    expect(CSS).toContain(".comparison-value .num { text-align: right; }");
    const unit = CSS.slice(
      CSS.indexOf(".comparison-value .unit {"),
      CSS.indexOf("}", CSS.indexOf(".comparison-value .unit {")),
    );
    expect(unit).toContain("font-family: var(--font-sans)");
    expect(unit).not.toContain("--font-mono");
  });

  it("reads the split fields rather than the joined string", () => {
    /* `metric.text` already contains the unit; rendering it into `.num`
       and then adding `.unit` prints the unit twice. */
    expect(GRID).toContain('<span className="num">{digits}</span>');
    expect(GRID).toContain('<span className="unit">{metric.unit ?? ""}</span>');
    expect(GRID).not.toContain("metric.text");
  });
});

describe("leading a metric stopped borrowing the gate colour", () => {
  const bestRule = () => {
    const at = CSS.indexOf(".comparison-value.is-best {");
    return CSS.slice(at, CSS.indexOf("}", at));
  };

  it("marks the leader with a background, not with green text", () => {
    /* `color: var(--ok)` is the green `.badge.ok` uses for "cleared
       every gate". After the gate verdict moved to the column head the
       two sat inches apart in one table: a green badge above a column of
       green numbers, where the badge means a candidate is admissible and
       the numbers mean it is 0.1 s quicker. */
    expect(bestRule()).not.toContain("color:");
    expect(bestRule()).toContain("background: var(--accent-soft)");
  });

  it("keeps a signal that survives greyscale", () => {
    /* A tint alone is a colour-only cue. The weight carries the same
       claim without it, and the screen reader gets it in words. */
    expect(bestRule()).toContain("font-weight: 700");
    expect(GRID).toContain('<span className="sr-only"> ({t("running.leads")})</span>');
  });

  it("leaves green meaning exactly one thing", () => {
    /* The gate badge keeps it — that is the meaning worth a state
       colour, because a gate verdict is pass or fail rather than a
       comparison whose margin may be a rounding error. */
    const badge = CSS.slice(CSS.indexOf(".badge.ok {"), CSS.indexOf("}", CSS.indexOf(".badge.ok {")));
    expect(badge).toContain("color: var(--ok)");
  });

  it("does not carry a literal fallback for a token that exists", () => {
    /* `var(--ok, #3f9a5a)` is the shape of the three bugs `tokens.test`
       was written for: a fallback makes a missing token quieter, not
       more correct. */
    expect(bestRule()).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });
});

describe("the host caveat stopped being a banner", () => {
  it("is a line, not a notice box", () => {
    /* A bordered, filled box across the top of a table of plain numbers
       outweighed the thing it warned about, and its shape claimed every
       row underneath. */
    expect(DETAIL).not.toContain('className="notice warn comparison-host-warning"');
    expect(DETAIL).toContain('<span className="comparison-host-warning">');
    const rule = CSS.slice(
      CSS.indexOf(".comparison-host-warning {"),
      CSS.indexOf("}", CSS.indexOf(".comparison-host-warning {")),
    );
    expect(rule).toContain("color: var(--warn)");
    expect(rule).not.toContain("border");
    expect(rule).not.toContain("background");
  });

  it("is handed to the grid rather than placed above it", () => {
    expect(DETAIL).toContain("hostWarning={<HostWarning run={run} />}");
    /* And exactly once — the duplicate that appeared while the grid was
       being extracted rendered the same caveat twice. */
    expect(DETAIL.match(/<HostWarning run=\{run\} \/>/g)).toHaveLength(1);
  });
});
