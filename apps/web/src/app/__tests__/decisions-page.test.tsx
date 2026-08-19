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

  it("uses the same episode state for the table, dropdown, and pair load", () => {
    expect(DETAIL).toContain('const [episodeId, setEpisodeId]');
    expect(DETAIL).toContain('selectedEpisode={episodeId}');
    expect(DETAIL).toContain('value={episodeId}');
    expect(DETAIL).toContain('void loadPair(episodeId)');
    expect(DETAIL).not.toContain('const [candidateId, setCandidateId]');
  });

  it("keeps candidate A left, candidate B right and tolerates one missing trace", () => {
    expect(DETAIL).toContain('side={index === 0 ? "a" : "b"}');
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
