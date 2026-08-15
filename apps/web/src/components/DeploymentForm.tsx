"use client";

/** File a deployment by filling fields instead of by pasting a document.
 *
 * **The form decides nothing.** `TaskProfile` on the server is the single
 * statement of HĐ-2, and it is what refuses a heading requirement the
 * platform cannot evaluate, traffic that shifts by less than one period,
 * or a RAM budget that does not add up. Every refusal shown here came
 * back from it; a second opinion in the browser would be free to
 * disagree with the one that actually decides.
 *
 * **The form and the paste box produce the same artifact.** The YAML
 * preview below is exactly what the paste box would accept, and both go
 * to `POST /task-profiles`. Without that, "a deployment" would have two
 * definitions and the second would drift.
 *
 * **Where a number has a consequence, the consequence is next to it.**
 * The accepted collision risk decides the episode count (HĐ-7.1); the
 * success threshold decides whether the deployment can rank at all
 * (HĐ-8.4). Those live in comments in the YAML files, where they are
 * read after the choice rather than during it.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { MapPainter } from "@/components/MapPainter";
import { MissionPlacer, type PlacementMode } from "@/components/MissionPlacer";
import { TrafficEditor, type TrafficSelection, placementNote } from "@/components/TrafficEditor";
import { api } from "@/lib/api";
import { authFetch, fieldErrorsOf } from "@/lib/auth";
import { createSequencer } from "@/lib/sequencer";
import { placeOnMotion, previewRequestOf, snapshotsOf, trafficOf } from "@/lib/traffic";
import {
  DEFAULT_LIBRARY_SCENARIO,
  at,
  getProfileTemplate,
  importLibraryScenario,
  listScenarioLibrary,
  materialiseMap,
  nMinFor,
  posesFor,
  ramLeftOver,
  withValue,
  type ProfileDraft,
} from "@/lib/deployments";
import { emptyBorderedMap } from "@/lib/demoMap";
import { useTranslation } from "@/lib/i18n";
import { listRobotProfiles, type RobotProfile } from "@/lib/models";
import type { LibraryEntry } from "@/lib/platformTypes";
import type { MapData, MapSummary, Pose2D, ScenarioPreview } from "@/lib/types";
import { safetyEnvelope } from "@/lib/keepOut";

/** Where the map under this deployment comes from. */
type MapSource = "library" | "stored" | "drawn";

/** What a new deployment declares about its robot's imperfections.
 *
 * **On by default, at amplitudes a real AMR actually has.** A simulator
 * with no noise is more optimistic than reality, and this project has
 * already paid for that optimism once: a Decision Card bounded a
 * collision probability from a single episode replayed a hundred times,
 * because nothing in the world varied between seeds. Starting a new
 * deployment at zero makes that the easy path again.
 *
 * **This is a form default and deliberately not a schema default.**
 * ``SensorNoise`` still defaults every field to zero, and it has to: the
 * shipped profiles do not declare these fields, so a non-zero schema
 * default would change the world underneath `open_hall_v2` and
 * `warehouse_a_v2` *without changing their `task_profile_id`* — and
 * every stored trace, gate verdict and Decision Card would silently
 * describe a world that no longer exists (HĐ-3.1, HĐ-13). Defaulting
 * here touches only deployments nobody has measured yet.
 */
/** The one contract path this file writes that is not a noise amplitude.
 *
 * A constant rather than a literal at each of its four uses, because the
 * schema drift guard reads this file looking for the dotted path and one
 * typo among four copies is a control wired to a field the deployment
 * does not have. */
const V_OBSTACLE_MAX = "environment.v_obstacle_max";

const NOISE_DEFAULTS: Record<string, { value: number; step: number }> = {
  //: Keyed by the **full dotted path**, not the leaf name. The schema
  //: drift guard reads this file for every contract field it expects a
  //: control for, and a path assembled from a template variable is a
  //: path it cannot see — so the names stay literal here.
  //
  //: A 2 cm range error is what the topic document's noise table names.
  "environment.sensor_noise.lidar_range_sigma_m": { value: 0.02, step: 0.005 },
  "environment.sensor_noise.wheel_slip_fraction": { value: 0.02, step: 0.005 },
  //: 10 cm between where an AMR is and where it thinks it is — ordinary
  //: for a mapped indoor site, and enough to matter beside a 0.26 m robot.
  "environment.sensor_noise.localization_drift_m": { value: 0.1, step: 0.01 },
  //: Two per cent of relocalisation windows produce a fix that stays
  //: wrong: uncommon enough to be a bad day, common enough to appear in
  //: a 300-episode set.
  "environment.sensor_noise.localization_jump_probability": { value: 0.02, step: 0.005 },
  //: Two rays in a hundred come back with nothing. Real scanners do far
  //: worse against glass; this is the quiet-warehouse figure.
  "environment.sensor_noise.lidar_dropout_probability": { value: 0.02, step: 0.005 },
  //: One per cent of systematic error — a wheel a little smaller than
  //: its partner. Small, and it accumulates, which is the point.
  "environment.sensor_noise.odometry_bias_fraction": { value: 0.01, step: 0.005 },
  //: Two control steps. At a 20 Hz loop that is 100 ms between deciding
  //: and moving, which is an ordinary ROS pipeline.
  "environment.sensor_noise.command_latency_steps": { value: 2, step: 1 },
};

/** Fill in the noise a fresh template leaves at zero.
 *
 * Only zeroes are replaced. A template that already declares an
 * amplitude has one for a reason — the shipped hall's 2 cm sigma is the
 * measured figure — and overwriting it would be this form deciding what
 * a deployment measured.
 */
function withNoiseDefaults(template: ProfileDraft): ProfileDraft {
  let filled = template;
  for (const [path, { value }] of Object.entries(NOISE_DEFAULTS)) {
    if (!Number(at(filled, path) ?? 0)) filled = withValue(filled, path, value);
  }
  return filled;
}

export interface DeploymentFormProps {
  /** Called with the finished profile; the page owns the request so the
   *  YAML tab and this one submit through one code path. */
  onSubmit: (profile: ProfileDraft) => Promise<void>;
  busy: boolean;
  /** Server refusals, addressed by field path (`robot.radius`). Rendered
   *  beside the input rather than as a banner — a banner is what made a
   *  thirty-field form unusable in the first place. */
  fieldErrors: { path: string; message: string }[];
  /** The draft, lifted so the YAML tab can show what this tab built. */
  draft: ProfileDraft | null;
  onDraftChange: (draft: ProfileDraft) => void;
}

export function DeploymentForm({
  onSubmit,
  busy,
  fieldErrors,
  draft,
  onDraftChange,
}: DeploymentFormProps) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<MapSource>("library");
  const [library, setLibrary] = useState<LibraryEntry[]>([]);
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [libraryName, setLibraryName] = useState(DEFAULT_LIBRARY_SCENARIO);
  const [storedMapId, setStoredMapId] = useState("");
  const [mapData, setMapData] = useState<MapData | null>(null);
  /** The last non-zero amplitude of each noise source, so unticking and
   *  re-ticking returns what was typed rather than the shipped default.
   *  Losing an edited amplitude to a stray click is the kind of small
   *  thing that costs a re-measurement to notice. */
  const [remembered, setRemembered] = useState<Partial<Record<string, number>>>({});
  const [start, setStart] = useState<Pose2D | null>(null);
  const [goal, setGoal] = useState<Pose2D | null>(null);
  const [showHardware, setShowHardware] = useState(false);
  /** The vehicle register. Empty is not an error — it is a fresh
   *  install, and typing the limits by hand still works. */
  const [vehicles, setVehicles] = useState<RobotProfile[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  /** The map the canvas is showing, whichever way it was chosen.
   *
   * Distinct from `storedMapId`, which is only the picker's selection: a
   * drawn map is created before it is adopted and has an id just as real
   * as a stored one, and the preview endpoint takes an id rather than a
   * grid. Keeping one field for "the picker" and another for "what is on
   * screen" is what lets all three sources preview. */
  const [activeMapId, setActiveMapId] = useState("");
  /** One placement mode for the whole page. The traffic editor and the
   *  mission placer share a canvas, so they cannot each hold their own. */
  const [placing, setPlacing] = useState<PlacementMode>("start");
  const [trafficSelection, setTrafficSelection] = useState<TrafficSelection | null>(null);
  /** Refusals from the check this form asked for, as opposed to the ones
   *  the page got back from filing.
   *
   * Owned here because this form is what asked. The page still owns the
   * refusal from `POST /task-profiles`, and the two are merged for
   * display rather than one overwriting the other. */
  const [dryRunErrors, setDryRunErrors] = useState<{ path: string; message: string }[]>([]);
  const [checking, setChecking] = useState(false);
  const [checkedClean, setCheckedClean] = useState(false);
  const [preview, setPreview] = useState<ScenarioPreview | null>(null);
  const [previewTime, setPreviewTime] = useState(0);
  const [previewSeed, setPreviewSeed] = useState(0);

  /** Everything the server has been asked about this document is now
   *  about a previous document.
   *
   * **One function because there is one rule**, and the first version
   * did not have it: the clearing lived inside `set`, so a field edit
   * invalidated the verdict while moving the start pose, adopting a map
   * or applying a vehicle did not. A green "the server accepts this"
   * beside a document that has changed since is worse than showing
   * nothing, because it is read as current — and so is traffic drawn on
   * the canvas from a request about the old one.
   *
   * The revision is what makes it safe against a reply that is already
   * in flight: a check or a preview that started before this bump
   * belongs to a document that no longer exists, and its answer is
   * dropped rather than rendered.
   */
  const revision = useRef(0);
  /** Preview replies can overtake each other, so only the newest may
   *  draw. Separate from `revision` because a scrub to another instant
   *  supersedes a preview without invalidating a verdict. */
  const previewSeq = useRef(createSequencer()).current;
  /** Map adoption, which reads a grid and writes a document either side
   *  of an await.
   *
   * **The token is claimed by the handler, before the fetch it starts,
   * not by `adopt` when the fetch comes back.** Claiming late made the
   * sequence describe the order answers *arrived* rather than the order
   * the author *chose*: pick map A, pick map B, B answers first and
   * takes token 1, A answers second and takes token 2 — and A, the map
   * nobody selected, wins. */
  const adoption = useRef(createSequencer()).current;
  const [adopting, setAdopting] = useState(false);
  /** The draft as it is *now*, for the handlers that resume after an
   *  await. A `draft` captured in a closure is the document as it was
   *  when the handler started, and writing it back undoes whatever was
   *  typed in between. */
  const draftRef = useRef(draft);
  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);
  const invalidateCheck = useCallback(() => {
    revision.current += 1;
    // The preview sequence moves too. Clearing the picture is not enough
    // on its own: a request that left before this edit still matched the
    // sequence when it landed, so it drew the old document back over the
    // cleared canvas — the stale preview returning by the one door the
    // first fix left open.
    previewSeq.supersede();
    setDryRunErrors([]);
    setCheckedClean(false);
    setPreview(null);
  }, [previewSeq]);

  const set = useCallback(
    (path: string, value: unknown) => {
      if (draft) onDraftChange(withValue(draft, path, value));
      invalidateCheck();
    },
    [draft, onDraftChange, invalidateCheck],
  );

  // The defaults, from the shipped profile rather than a copy in here.
  useEffect(() => {
    if (draft) return;
    let cancelled = false;
    void (async () => {
      try {
        const [template, entries, stored, fleet] = await Promise.all([
          getProfileTemplate(),
          listScenarioLibrary().catch(() => [] as LibraryEntry[]),
          api.listMaps().catch(() => [] as MapSummary[]),
          listRobotProfiles().catch(() => [] as RobotProfile[]),
        ]);
        if (cancelled) return;
        onDraftChange(withNoiseDefaults(template));
        setLibrary(entries);
        setMaps(stored);
        setVehicles(fleet);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [draft, onDraftChange]);

  /** Adopt a map: draw it, write it out, and reset the poses onto it.
   *
   * The poses reset because a coordinate means something else on another
   * map — and it might still land on free floor, so nothing downstream
   * would catch it. Where the replacement pair comes from is the whole
   * subject of `posesFor`: a library scenario brings its own, and
   * anything else gets the map's corners.
   *
   * **The traffic moves with the map, and used to be dropped.** The
   * picker advertises `sudden_stop · 1 traffic`, so somebody chooses it
   * *because* of the cart; the form then wrote only the map paths, and
   * the deployment ran on an empty lane. The robot drove straight
   * through, which looks like a planner that ignores obstacles rather
   * than a form that forgot them. `Scenario.dynamic_obstacles` and
   * `TaskEnvironment.dynamic_obstacles` are the same type, so carrying
   * them is a copy — and the server still validates them (unique names,
   * a periodic obstacle that shifts by at least one period), so a
   * scenario that cannot be a deployment is refused rather than filed.
   *
   * A map with no scenario behind it — drawn here, or picked out of the
   * store — clears the traffic instead of keeping it. A cart at
   * `sudden_stop`'s coordinates means nothing on somebody else's walls,
   * and leaving it would put an obstacle in a place nobody chose.
   */
  const adopt = useCallback(
    async (
      data: MapData,
      mapId: string,
      scenario: Parameters<typeof posesFor>[1],
      token: number,
    ) => {
      if (!adoption.isCurrent(token)) return;
      setAdopting(true);
      try {
        // **The fallible half first, the commit second.** The other way
        // round left the form in a state no deployment describes: the
        // canvas showing the new map and the mission placed on it, while
        // the draft still named the old map's files and carried its
        // traffic. Nothing rolled that back, and nothing said so —
        // filing it would have measured one world through another's
        // walls.
        const paths = await materialiseMap(mapId);
        // Somebody may have chosen another map, or typed in a field. The
        // newest choice wins, and the draft being edited is the one on
        // screen now rather than the one captured before the await.
        if (!adoption.isCurrent(token)) return;
        const current = draftRef.current;
        if (!current) return;
        let next = withValue(current, "environment.map", paths.map);
        next = withValue(next, "environment.map_yaml", paths.map_yaml);
        next = withValue(next, "environment.dynamic_obstacles", scenario?.dynamic_obstacles ?? []);
        const poses = posesFor(data, scenario);
        setMapData(data);
        setActiveMapId(mapId);
        setTrafficSelection(null);
        setStart(poses.start);
        setGoal(poses.goal);
        onDraftChange(next);
        invalidateCheck();
      } catch (caught) {
        // Nothing was committed, so there is nothing to undo — the form
        // still describes the map it described a moment ago.
        if (adoption.isCurrent(token)) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      } finally {
        if (adoption.isCurrent(token)) setAdopting(false);
      }
    },
    [adoption, onDraftChange, invalidateCheck],
  );

  /** Choosing a map out of the store, from the click through to the commit.
   *
   * **The whole lifecycle in one function, and the claim is its first
   * statement.** Splitting it — the fetch at the call site, the ordering
   * inside `adopt` — is what let the token drift away from the choice
   * twice: first it was taken when the answer came back, and then, once
   * that was fixed, it was still taken *after* the branch that adopts
   * nothing.
   *
   * That branch is the subtle one. Picking the blank option is a choice
   * and not the absence of one: it says "not that map". Returning early
   * without claiming left an adoption already fetching, and it went on
   * to commit a map the picker no longer shows. So the claim happens
   * before anything, including before deciding there is nothing to
   * fetch — an unused token still supersedes what is in flight.
   */
  const adoptStoredMap = useCallback(
    (id: string) => {
      const token = adoption.claim();
      setStoredMapId(id);
      if (!id) return;
      void (async () => {
        try {
          const resource = await api.getMap(id);
          await adopt(resource.map_data, id, null, token);
        } catch (caught) {
          if (adoption.isCurrent(token)) {
            setError(caught instanceof Error ? caught.message : String(caught));
          }
        }
      })();
    },
    [adoption, adopt],
  );

  // Open on the default library scenario, so the form has a real map and
  // a drivable pair of poses before anybody touches it.
  useEffect(() => {
    if (!draft || mapData || source !== "library") return;
    let cancelled = false;
    const token = adoption.claim();
    void (async () => {
      try {
        const imported = await importLibraryScenario(libraryName);
        if (cancelled) return;
        const resource = await api.getMap(imported.map_id);
        if (cancelled) return;
        setStoredMapId(imported.map_id);
        await adopt(resource.map_data, imported.map_id, imported.scenario, token);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft !== null, libraryName, source]);

  /** Refusals from checking and from filing, in one list.
   *
   * The check runs the same code path filing does, so the two cannot
   * disagree about a document; they can only be about *different*
   * documents. The checked ones come first because they are the ones
   * this form asked for and clears on every edit — a filing refusal
   * belongs to the page and can outlive the document it was about, so it
   * must not win a `find` against a fresher answer. */
  const shownErrors = useMemo(
    () => [...dryRunErrors, ...fieldErrors],
    [dryRunErrors, fieldErrors],
  );

  const errorFor = useCallback(
    (path: string) => shownErrors.find((entry) => entry.path === path)?.message,
    [shownErrors],
  );

  const complete = useMemo(() => {
    const id = at(draft ?? {}, "id");
    return (
      typeof id === "string" && id.trim() !== "" && start !== null && goal !== null && !!mapData
    );
  }, [draft, start, goal, mapData]);

  if (!draft) return <p className="muted">{t("common.loading")}</p>;

  /** Nothing may be edited while a check is in flight.
   *
   * Not cosmetic: the answer coming back is about the document that was
   * sent, and an author who keeps typing turns it into an answer about a
   * document that no longer exists. The revision guard already refuses
   * to render such an answer, so this is the half that stops the author
   * wondering why their check did nothing. */
  const frozen = busy || checking || adopting;

  /** The draft as the document that would be filed.
   *
   * The mission is assembled here rather than kept in the draft, so the
   * two poses have exactly one home while they are being edited — the
   * same reason the placer holds none of its own. Checking and filing
   * both go through it, because a check of a *different* document to the
   * one that gets filed is worse than no check.
   */
  const documentOf = (): ProfileDraft | null => {
    if (!start || !goal) return null;
    return withValue(draft, "missions", [
      {
        id: "custom_route",
        start: [start.x, start.y, start.theta],
        goal: [goal.x, goal.y, goal.theta],
        probability: 1.0,
      },
    ]);
  };

  /** Ask the server whether this document is legal, without filing it.
   *
   * **Not a second opinion.** `POST /task-profiles/validate` runs the
   * same `TaskProfile` check filing runs and refuses with the same
   * per-field addresses, which is why the answer can be trusted to
   * predict the refusal — and why nothing in this browser tries to work
   * it out. Returns whether the document passed, so submit can use it as
   * a gate rather than repeating the call's result in state.
   *
   * What it cannot see: the check reads the document only, so an id
   * already on file with different content passes here and is refused by
   * filing (HĐ-3.1). The note beside the button says so.
   */
  const check = async (): Promise<boolean> => {
    // One at a time. Two checks in flight share one `checking` flag, so
    // whichever finishes first unfreezes the form while the other is
    // still running — and the author edits into the gap.
    if (checking) return false;
    const document = documentOf();
    if (!document) return false;
    const asked = revision.current;
    setChecking(true);
    try {
      await authFetch("/task-profiles/validate", {
        method: "POST",
        body: JSON.stringify(document),
      });
      // The document may have moved on while this was in flight. An
      // answer about the previous one is not a weaker answer, it is an
      // answer to a different question — and rendering it as a verdict
      // on what is on screen is exactly the stale green tick.
      if (revision.current !== asked) return false;
      setDryRunErrors([]);
      setCheckedClean(true);
      return true;
    } catch (caught) {
      if (revision.current !== asked) return false;
      const addressed = fieldErrorsOf(caught);
      setDryRunErrors(addressed);
      setCheckedClean(false);
      if (addressed.length === 0) {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
      return false;
    } finally {
      setChecking(false);
    }
  };

  const submit = async () => {
    const document = documentOf();
    if (!document) return;
    const asked = revision.current;
    // Checked first so a refusal lands on the fields it is about before
    // the page has to render a failed filing.
    if (!(await check())) return;
    // `document` was built before the await. Filing it after an edit
    // would store a deployment nobody is looking at — the form would be
    // showing one world and the server keeping another.
    if (revision.current !== asked) return;
    await onSubmit(document);
  };

  /** Moving to another instant or another seed retires the picture.
   *
   * Not an edit — the document is unchanged and a verdict about it is
   * still good — but the canvas is now labelled with numbers it was not
   * drawn from. Leaving it up is how a reader ends up believing the
   * traffic is at t = 40 while looking at t = 0. */
  const scrubPreview = () => {
    previewSeq.supersede();
    setPreview(null);
  };

  /** The request this draft can currently support, or nothing.
   *
   * Computed here rather than inside the handler so the button can be
   * disabled on the same answer that would have made the click do
   * nothing. A control that looks available and silently ignores you is
   * worse than one that is visibly unavailable: the first reads as a
   * broken preview, the second as a deployment that is not finished. */
  const previewRequest =
    start && goal && activeMapId
      ? previewRequestOf({
          draft,
          start,
          goal,
          mapId: activeMapId,
          time: previewTime,
          seed: previewSeed,
        })
      : null;

  /** Where the traffic is at `previewTime`, computed by the backend.
   *
   * The browser never evaluates a motion law: a second implementation
   * would drift from the simulator's, and a preview that disagrees with
   * the episode is worse than no preview — the author would place a
   * start clear of an obstacle that is somewhere else when the run
   * happens. */
  const refreshPreview = async () => {
    if (!previewRequest) return;
    const request = previewRequest;
    // Cleared before asking, not after answering. A picture of where the
    // traffic was under the previous numbers, sitting on screen while a
    // new request is in flight, is read as where it is now.
    setPreview(null);
    const asked = previewSeq.claim();
    try {
      const answer = await authFetch<ScenarioPreview>("/scenarios/preview", {
        method: "POST",
        body: JSON.stringify(request),
      });
      // Replies can overtake each other; only the newest request may
      // draw. Without this a slow answer about t = 0 lands after a quick
      // one about t = 40 and the canvas shows the older instant.
      if (previewSeq.isCurrent(asked)) setPreview(answer);
    } catch (caught) {
      if (!previewSeq.isCurrent(asked)) return;
      setPreview(null);
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  const field = (path: string, label: string, step?: number, note?: string) => (
    <Field
      key={path}
      label={label}
      note={note}
      error={errorFor(path)}
      value={at(draft, path)}
      step={step}
      disabled={frozen}
      onChange={(value) => set(path, value)}
    />
  );

  /** A noise amplitude with a switch beside it.
   *
   * **The switch adds no field.** It writes zero to turn the source off
   * and the shipped amplitude to turn it back on, so the *data* still
   * has exactly one way to say "off" — a stored `enabled: false` beside
   * a declared sigma would be a deployment nobody could classify at a
   * glance, and the two halves would be free to disagree.
   *
   * The last non-zero value is remembered in component state so
   * unticking and re-ticking gives back what was typed rather than the
   * shipped default. Losing an edited amplitude to a stray click is a
   * small thing that costs a re-measurement to notice.
   */
  const noiseField = (path: string, label: string, note?: string) => {
    /* A missing entry means the caller passed a leaf name where a full
       dotted path belongs — which is not only a crash but a control
       wired to nowhere: `at` would read undefined and `set` would write
       a top-level key the server does not accept. Named here because
       "Cannot read properties of undefined (reading 'step')" sent the
       last reader to the wrong line entirely. The condition itself is
       caught before it ships by the call-site scan in
       `deployments-page.test.tsx`. */
    const defaults = NOISE_DEFAULTS[path];
    if (!defaults) {
      throw new Error(
        `noise control path "${path}" has no NOISE_DEFAULTS entry. Pass the full dotted ` +
          `path (environment.sensor_noise.<field>), not the leaf name — the control writes ` +
          `to that path, so a leaf name would edit a field the deployment does not have.`,
      );
    }
    const current = Number(at(draft, path) ?? 0);
    const on = current > 0;
    return (
      <div key={path} className="field">
        <label className="row" style={{ alignItems: "center", gap: 6, marginBottom: 4 }}>
          <input
            type="checkbox"
            checked={on}
            disabled={frozen}
            onChange={(event) => {
              if (event.target.checked) {
                set(path, remembered[path] ?? defaults.value);
              } else {
                if (current > 0) setRemembered((was) => ({ ...was, [path]: current }));
                set(path, 0);
              }
            }}
          />
          <span>{label}</span>
        </label>
        <Field
          label=""
          note={note}
          error={errorFor(path)}
          value={at(draft, path)}
          step={defaults.step}
          disabled={frozen || !on}
          onChange={(value) => set(path, value)}
        />
      </div>
    );
  };

  /** Copy a vehicle's limits into the draft. Fills, never locks.
   *
   * **`control_period` is deliberately not among them**, and this is the
   * one line of the whole picker worth reading twice. It is T_cycle —
   * the wall-clock budget one control step has on the target board, and
   * therefore gate G4's threshold. The same robot in a hall and in a
   * warehouse aisle can be held to two different cycles, so it is a
   * property of *this deployment*, not of the vehicle. A picker that
   * filled it would let one vehicle's setting move a gate at every site
   * using that robot.
   *
   * An undeclared acceleration leaves the field alone rather than
   * writing a zero. Null on a profile means "nobody said", and a zero
   * here would say the robot cannot change speed — a claim the form
   * would then submit as though somebody had made it.
   */
  const adoptVehicle = (id: string) => {
    setVehicleId(id);
    const vehicle = vehicles.find((entry) => entry.id === id);
    if (!draft || !vehicle) return;
    let next = draft;
    next = withValue(next, "robot.radius", vehicle.radius);
    next = withValue(next, "robot.max_linear_velocity", vehicle.max_linear_velocity);
    next = withValue(next, "robot.max_angular_velocity", vehicle.max_angular_velocity);
    if (vehicle.max_linear_acceleration !== null) {
      next = withValue(next, "robot.max_linear_acceleration", vehicle.max_linear_acceleration);
    }
    if (vehicle.max_angular_acceleration !== null) {
      next = withValue(next, "robot.max_angular_acceleration", vehicle.max_angular_acceleration);
    }
    onDraftChange(next);
    invalidateCheck();
  };

  const chosenVehicle = vehicles.find((entry) => entry.id === vehicleId);
  const undeclaredAccelerations =
    chosenVehicle !== undefined &&
    (chosenVehicle.max_linear_acceleration === null ||
      chosenVehicle.max_angular_acceleration === null);

  /** How much moving traffic this deployment now declares.
   *
   * Read off the draft rather than off the picked library entry, because
   * the draft is what will be measured — and it is also the only source
   * that covers a stored or drawn map, where there is no library entry
   * to ask.
   */
  const traffic = (at(draft, "environment.dynamic_obstacles") as unknown[] | undefined)?.length ?? 0;

  /** Whether this deployment carries a braking guarantee against moving
   * traffic at all. Null and absent both mean "no claim"; zero does not,
   * so the test is for a number rather than for truthiness. */
  const obstacleSpeedDeclared = numberAt(draft, V_OBSTACLE_MAX) !== undefined;

  const risk = at(draft, "constraints.collision_probability_max");
  const nMin = nMinFor(risk);
  const leftOver = ramLeftOver(draft);

  return (
    <>
      {error ? <div className="error-box">{error}</div> : null}

      <h4>{t("deployments.form.identity")}</h4>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        {field("id", t("deployments.form.id"), undefined, t("deployments.form.idNote"))}
        <Choice
          label={t("deployments.form.claimLevel")}
          value={at(draft, "claim_level")}
          options={["mission", "deployment", "robust_deployment"]}
          disabled={frozen}
          onChange={(value) => set("claim_level", value)}
          error={errorFor("claim_level")}
        />
        <Choice
          label={t("deployments.form.role")}
          value={at(draft, "deployment_role")}
          options={["acceptance", "customer", "instrument"]}
          disabled={frozen}
          onChange={(value) => set("deployment_role", value)}
          error={errorFor("deployment_role")}
        />
      </div>

      <h4>{t("deployments.form.robot")}</h4>
      {/* The vehicle register is the source of truth for what the robot
          *is* — but it fills the form rather than being referenced from
          it. HĐ-13 asks somebody else to rebuild a run from the profile
          alone; a profile pointing at an editable database row would
          change meaning the day somebody edits that row, and every trace
          already stored would quietly describe a different robot. So the
          numbers are copied in, at the moment an author chooses them,
          and the deployment stays self-contained. */}
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        <label className="field">
          <span>{t("deployments.form.vehicle")}</span>
          <select
            value={vehicleId}
            disabled={frozen || vehicles.length === 0}
            onChange={(event) => adoptVehicle(event.target.value)}
          >
            <option value="">{t("deployments.form.vehicleNone")}</option>
            {vehicles.map((vehicle) => (
              <option key={vehicle.id} value={vehicle.id}>
                {vehicle.name} v{vehicle.version}
              </option>
            ))}
          </select>
        </label>
        <p className="muted" style={{ flex: "1 1 260px", margin: 0 }}>
          {undeclaredAccelerations
            ? t("deployments.form.vehicleUndeclared")
            : t("deployments.form.vehicleNote")}
        </p>
      </div>
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        {field("robot.radius", t("deployments.form.radius"), 0.01)}
        {field("robot.max_linear_velocity", t("deployments.form.vMax"), 0.1)}
        {field("robot.max_angular_velocity", t("deployments.form.wMax"), 0.1)}
        {field("robot.max_linear_acceleration", t("deployments.form.aMax"), 0.1)}
        {field("robot.max_angular_acceleration", t("deployments.form.alphaMax"), 0.1)}
        {field(
          "robot.control_period",
          t("deployments.form.controlPeriod"),
          0.01,
          t("deployments.form.controlPeriodNote"),
        )}
      </div>

      <h4>{t("deployments.form.constraints")}</h4>
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        {field(
          "constraints.success_rate_min",
          t("deployments.form.successMin"),
          0.01,
          t("deployments.form.successMinNote"),
        )}
        {field(
          "constraints.collision_probability_max",
          t("deployments.form.risk"),
          0.01,
          nMin === null ? undefined : t("deployments.form.riskNote", { n: String(nMin) }),
        )}
        {field("constraints.no_path_rate_max", t("deployments.form.noPathMax"), 0.01)}
        {field("constraints.goal_tolerance_m", t("deployments.form.goalToleranceM"), 0.05)}
        {field(
          "constraints.goal_tolerance_rad",
          t("deployments.form.goalToleranceRad"),
          0.01,
          t("deployments.form.goalToleranceRadNote"),
        )}
        {field("constraints.episode_timeout_s", t("deployments.form.timeout"), 5)}
        {field("constraints.stuck_threshold_s", t("deployments.form.stuck"), 1)}
        {field("constraints.clearance_warning_m", t("deployments.form.clearanceWarning"), 0.05)}
        {/* The one number in the clearance model that nobody can derive.
            The safety envelope comes from the declared noise and the hard
            boundary comes from the robot; this says how much a metre
            spent hugging that boundary is *worth*, and only a person can
            answer that. Declared here so it is one number for every
            candidate in the comparison — a candidate-owned version would
            let one stack buy a shorter route by caring less. */}
        {field(
          "clearance_preference",
          t("deployments.form.clearancePreference"),
          0.5,
          t("deployments.form.clearancePreferenceNote"),
        )}
      </div>

      <h4>{t("deployments.form.noise")}</h4>
      {/* Every source has a switch, and the switch writes an amplitude
          rather than a flag — see `noiseField`. Unticking one is how a
          deployment says "this site does not have that problem". */}
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        {noiseField("environment.sensor_noise.lidar_range_sigma_m", t("deployments.form.lidarSigma"))}
        {noiseField("environment.sensor_noise.wheel_slip_fraction", t("deployments.form.wheelSlip"))}
        {noiseField(
          "environment.sensor_noise.localization_drift_m",
          t("deployments.form.localizationDrift"),
          t("deployments.form.localizationDriftNote"),
        )}
      </div>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        {noiseField("environment.sensor_noise.localization_jump_probability", t("deployments.form.localizationJump"))}
        {noiseField(
          "environment.sensor_noise.lidar_dropout_probability",
          t("deployments.form.lidarDropout"),
          t("deployments.form.lidarDropoutNote"),
        )}
        {noiseField(
          "environment.sensor_noise.odometry_bias_fraction",
          t("deployments.form.odometryBias"),
          t("deployments.form.odometryBiasNote"),
        )}
        {noiseField("environment.sensor_noise.command_latency_steps", t("deployments.form.commandLatency"))}
      </div>
      {/* The consequence of leaving both quiet. With no traffic *and* no
          noise, a deterministic planner replays one episode per seed and
          G2's bound rests on a sample of one. Traffic is authored below,
          under the map it is placed on. */}
      <p className="muted">{t("deployments.form.noiseNote")}</p>

      <h4>{t("deployments.form.obstacleSpeed")}</h4>
      {/* Not a `noiseField`, and the difference is the whole point of the
          control. A noise switch writes 0 for "off"; here 0 is a *claim*
          — "nothing at this site moves" — which the loader rejects the
          moment any traffic is declared. "Off" has to be null: not
          declared, no braking guarantee, and the manifest says so. Two
          different meanings cannot share one value. */}
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        <div className="field">
          <label className="row" style={{ alignItems: "center", gap: 6, marginBottom: 4 }}>
            <input
              type="checkbox"
              checked={obstacleSpeedDeclared}
              disabled={frozen}
              onChange={(event) => {
                if (event.target.checked) {
                  set("environment.v_obstacle_max", remembered[V_OBSTACLE_MAX] ?? 1.0);
                } else {
                  const current = numberAt(draft, V_OBSTACLE_MAX);
                  if (current !== undefined) {
                    setRemembered((was) => ({ ...was, [V_OBSTACLE_MAX]: current }));
                  }
                  set(V_OBSTACLE_MAX, null);
                }
              }}
            />
            <strong>{t("deployments.form.obstacleSpeedEnabled")}</strong>
          </label>
        </div>
        {obstacleSpeedDeclared
          ? field(V_OBSTACLE_MAX, t("deployments.form.obstacleSpeedValue"), 0.1)
          : null}
      </div>
      <p className="muted">
        {obstacleSpeedDeclared
          ? t("deployments.form.obstacleSpeedNote")
          : t("deployments.form.obstacleSpeedOffNote")}
      </p>

      <h4>
        <button
          type="button"
          className={showHardware ? "active" : undefined}
          onClick={() => setShowHardware(!showHardware)}
        >
          {showHardware ? "▾" : "▸"} {t("deployments.form.hardware")}
        </button>
      </h4>
      {showHardware ? (
        <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
          {field("hardware.target_device", t("deployments.form.targetDevice"))}
          {field("hardware.total_ram_mb", t("deployments.form.totalRam"), 64)}
          {field("hardware.ram_budget_breakdown.os_and_middleware_mb", t("deployments.form.ramOs"), 64)}
          {field("hardware.ram_budget_breakdown.perception_stack_mb", t("deployments.form.ramPerception"), 64)}
          {field(
            "hardware.ram_budget_breakdown.localization_mapping_mb",
            t("deployments.form.ramLocalisation"),
            64,
          )}
          {field("hardware.ram_budget_breakdown.logging_and_reserve_mb", t("deployments.form.ramLogging"), 64)}
          {field(
            "hardware.available_ram_mb",
            t("deployments.form.availableRam"),
            64,
            leftOver === null ? undefined : t("deployments.form.availableRamNote", { left: String(leftOver) }),
          )}
        </div>
      ) : null}

      <h4>{t("deployments.form.map")}</h4>
      <div className="toolbar">
        {(["library", "stored", "drawn"] as MapSource[]).map((option) => (
          <button
            key={option}
            type="button"
            disabled={frozen}
            className={source === option ? "active" : undefined}
            aria-pressed={source === option}
            onClick={() => {
              // An adoption started from the source being left is no
              // longer wanted, however fast it answers.
              adoption.supersede();
              setSource(option);
            }}
          >
            {t(`deployments.form.source.${option}`)}
          </button>
        ))}
        <Link href="/maps">{t("decisions.map.drawOne")}</Link>
      </div>

      {source === "library" ? (
        <label className="field">
          <span>{t("deployments.form.scenario")}</span>
          <select
            value={libraryName}
            disabled={frozen}
            onChange={(event) => {
              setMapData(null);
              setLibraryName(event.target.value);
            }}
          >
            {library.map((entry) => (
              <option key={entry.name} value={entry.name}>
                {entry.name} · {entry.map_size_m[0]}×{entry.map_size_m[1]} m
                {entry.dynamic_obstacles > 0 ? ` · ${entry.dynamic_obstacles} traffic` : ""}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {source === "stored" ? (
        <label className="field">
          <span>{t("decisions.map.label")}</span>
          <select
            value={storedMapId}
            disabled={frozen}
            onChange={(event) => adoptStoredMap(event.target.value)}
          >
            <option value="">{t("decisions.map.pickDeploymentFirst")}</option>
            {maps.map((map) => (
              <option key={map.id} value={map.id}>
                {map.name} · {map.width}×{map.height} · v{map.version}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {source === "drawn" ? (
        <DrawNewMap
          disabled={frozen}
          /* The claim is taken as the saved grid arrives rather than
             before the save: `DrawNewMap` owns that request and disables
             its own button while it runs, so there is never a second one
             to be overtaken by. */
          onSaved={(data, id) => void adopt(data, id, null, adoption.claim())}
          onError={setError}
        />
      ) : null}

      {/* **Directly under whichever map picker was used, not up with the
          other conditions.** It began beside the constraints, which is
          where it belongs by category and the wrong place by use: the map
          is chosen at the bottom of the form, and deciding whether the
          robot may replan is a thought you have *while looking at the
          traffic you just picked* — so the control was a scroll away from
          the moment it occurs to anybody.

          It is highlighted rather than ticked when the chosen scenario
          has moving obstacles. Ticking it would be the form deciding an
          evaluation condition on the author's behalf, and the whole
          reason this field exists on the deployment is that such
          decisions are declared rather than inferred. Highlighting says
          "this is the choice you are about to skip"; ticking would say
          "we made it for you". */}
      <div className={traffic > 0 ? "notice warn" : ""} style={{ marginTop: 8 }}>
        <label className="row" style={{ alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={Boolean(at(draft, "replanning.enabled"))}
            disabled={frozen}
            onChange={(event) => set("replanning.enabled", event.target.checked)}
          />
          <strong>{t("deployments.form.replanningEnabled")}</strong>
        </label>
        {traffic > 0 && !at(draft, "replanning.enabled") ? (
          <p className="muted">{t("deployments.form.replanningTraffic", { n: String(traffic) })}</p>
        ) : (
          <p className="muted">{t("deployments.form.replanningNote")}</p>
        )}
      </div>

      {/* Recovery sits directly under replanning because it is the same
          decision one rung further: what the robot may do when replanning
          finds nothing. Declared on the deployment, not on the candidate
          — a stack allowed to back up while its rival is not would be
          compared on its recovery rather than on the layer this run is
          about. */}
      <div style={{ marginTop: 8 }}>
        <label className="row" style={{ alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={Boolean(at(draft, "recovery.enabled"))}
            disabled={frozen}
            onChange={(event) => set("recovery.enabled", event.target.checked)}
          />
          <strong>{t("deployments.form.recoveryEnabled")}</strong>
        </label>
        <p className="muted">{t("deployments.form.recoveryNote")}</p>
        {at(draft, "recovery.enabled") ? (
          <div className="grid">
            {field(
              "recovery.max_escalation",
              t("deployments.form.recoveryEscalation"),
              1,
              t("deployments.form.recoveryEscalationNote"),
            )}
            {/* Its own budget because it spends something other than
                time: this rung erases evidence rather than changing the
                world, and a stack free to repeat it is free to forget an
                obstacle it just saw. */}
            {field(
              "recovery.max_forgets",
              t("deployments.form.recoveryForgets"),
              1,
              t("deployments.form.recoveryForgetsNote"),
            )}
          </div>
        ) : null}
      </div>

      {mapData ? (
        <MissionPlacer
          map={mapData}
          start={start}
          goal={goal}
          onChange={(poses) => {
            setStart(poses.start);
            setGoal(poses.goal);
            // The mission is part of the document being checked, so
            // moving it is as much an edit as typing in a field.
            invalidateCheck();
          }}
          robotRadius={numberAt(draft, "robot.radius")}
          positionUncertainty={safetyEnvelope({
            localization_drift_m: numberAt(draft, "environment.sensor_noise.localization_drift_m"),
            localization_jump_probability: numberAt(
              draft,
              "environment.sensor_noise.localization_jump_probability",
            ),
          })}
          goalTolerance={numberAt(draft, "constraints.goal_tolerance_m")}
          disabled={frozen}
          startNote={t("decisions.map.startHeadingNote")}
          goalNote={t("decisions.map.goalHeadingNote")}
          mode={placing}
          onModeChange={(next) => {
            setPlacing(next);
            // Switching to a mission mode ends the traffic selection, or
            // the editor would keep a button lit for clicks it no longer
            // receives.
            if (next === "start" || next === "goal" || next === "none") setTrafficSelection(null);
          }}
          onPlace={(x, y) => {
            if (!trafficSelection) return;
            const obstacles = trafficOf(draft);
            const chosen = obstacles[trafficSelection.index];
            if (!chosen) return;
            set(
              "environment.dynamic_obstacles",
              obstacles.map((obstacle, at) =>
                at === trafficSelection.index
                  ? {
                      ...obstacle,
                      motion: placeOnMotion(obstacle.motion, trafficSelection.mode, { x, y }),
                    }
                  : obstacle,
              ),
            );
          }}
          modeNote={placementNote(trafficSelection, trafficOf(draft), t)}
          dynamicObstacles={(preview?.dynamic_obstacles ?? []).map((obstacle) => ({
            name: obstacle.name,
            radius: obstacle.radius,
            position: obstacle.position,
          }))}
          obstacleSnapshots={snapshotsOf(preview)}
          previewTime={preview?.time}
        />
      ) : (
        <p className="muted">{t("common.loading")}</p>
      )}

      {/* Below the canvas rather than up with the noise it relates to:
          placing a waypoint is a thing you do *while looking at the map*,
          and a toolbar a screen away from the thing it draws on is the
          arrangement that made the old editor hard to use. */}
      <TrafficEditor
        obstacles={trafficOf(draft)}
        onChange={(next) => set("environment.dynamic_obstacles", next)}
        selection={trafficSelection}
        onSelect={(selection) => {
          setTrafficSelection(selection);
          setPlacing(selection ? selection.mode : "none");
        }}
        anchor={start ?? { x: 0, y: 0 }}
        disabled={frozen}
        /* Everything addressed to the environment that no control on
           this page already renders. Passing only `environment` left a
           deep path like `…dynamic_obstacles.0.radius` with nowhere to
           go, and a refusal nobody can see blocks filing without saying
           why. The noise amplitudes and the closing speed are excluded
           because they have inputs of their own, and `errorFor` puts
           their refusals beside them. */
        errors={shownErrors.filter(
          (entry) =>
            (entry.path === "environment" || entry.path.startsWith("environment.")) &&
            !entry.path.startsWith("environment.sensor_noise") &&
            entry.path !== V_OBSTACLE_MAX,
        )}
      />

      <div className="row" style={{ marginTop: 8, alignItems: "flex-end", gap: 12 }}>
        <label className="field" style={{ width: 130 }}>
          <span>{t("deployments.form.previewTime")}</span>
          <input
            type="number"
            step={0.5}
            min={0}
            value={previewTime}
            disabled={frozen || !activeMapId}
            onChange={(event) => {
              setPreviewTime(Number(event.target.value));
              scrubPreview();
            }}
          />
        </label>
        <label className="field" style={{ width: 110 }}>
          <span>{t("deployments.form.previewSeed")}</span>
          <input
            type="number"
            step={1}
            value={previewSeed}
            disabled={frozen || !activeMapId}
            onChange={(event) => {
              setPreviewSeed(Number(event.target.value));
              scrubPreview();
            }}
          />
        </label>
        <button type="button" disabled={frozen || !previewRequest} onClick={() => void refreshPreview()}>
          {t("deployments.form.preview")}
        </button>
        <span className="muted">{t("deployments.form.previewNote")}</span>
      </div>

      {/* The preview endpoint answers two questions and the first
          version read only one of them. It runs the scenario against the
          *map* — a start pose inside a wall, an obstacle spawned in
          occupied cells — and none of that is visible to
          `POST /task-profiles/validate`, which reads the document and
          never opens the grid. So a deployment can pass the check, come
          back from here with `valid: false`, and the author would have
          seen only traffic drawn as though nothing were wrong. */}
      {preview && !preview.valid ? (
        <div className="notice warn">
          <strong>{t("deployments.form.previewInvalid")}</strong>
          <ul>
            {preview.errors.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="row" style={{ marginTop: 16, alignItems: "center", gap: 12 }}>
        {/* Both frozen, and the reason is the same for each: while a map
            is being written out the canvas already shows it and the
            draft does not, so filing would store a deployment nobody is
            looking at. */}
        <button type="button" className="primary" disabled={frozen || !complete} onClick={() => void submit()}>
          {t("deployments.file.submit")}
        </button>
        <button type="button" disabled={frozen || !complete} onClick={() => void check()}>
          {checking ? t("deployments.form.validateBusy") : t("deployments.form.validate")}
        </button>
        <span className="muted">{t("deployments.file.idRule")}</span>
      </div>
      <p className="muted">{t("deployments.form.validateNote")}</p>
      {checkedClean ? <p className="notice">{t("deployments.form.validateOk")}</p> : null}
    </>
  );
}

function numberAt(draft: ProfileDraft, path: string): number | undefined {
  const value = at(draft, path);
  return typeof value === "number" ? value : undefined;
}

/** Draw a grid from scratch, save it, and hand it to the form.
 *
 * Three size boxes and the shared painter — the same one `/maps/[id]`
 * uses, so there is one answer to what painting a map means.
 */
function DrawNewMap({
  disabled,
  onSaved,
  onError,
}: {
  disabled: boolean;
  onSaved: (map: MapData, mapId: string) => void;
  onError: (message: string) => void;
}) {
  const { t } = useTranslation();
  const [width, setWidth] = useState(40);
  const [height, setHeight] = useState(30);
  const [resolution, setResolution] = useState(0.25);
  const [name, setName] = useState("");
  const [map, setMap] = useState<MapData>(() => emptyBorderedMap("drawn", 40, 30, 0.25));
  const [saving, setSaving] = useState(false);

  const reshape = (w: number, h: number, r: number) => {
    setWidth(w);
    setHeight(h);
    setResolution(r);
    // A resize cannot keep the painting: cell (3, 4) of a 40-wide grid is
    // somewhere else in a 60-wide one, so carrying the cells over would
    // shear the walls rather than preserve them.
    setMap(emptyBorderedMap(map.name, w, h, r));
  };

  const save = async () => {
    setSaving(true);
    try {
      const created = await api.createMap({ ...map, name: name.trim() || map.name });
      onSaved(created.map_data, created.id);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
        <label className="field">
          <span>{t("common.name")}</span>
          <input value={name} disabled={disabled} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>{t("deployments.form.cols")}</span>
          <input
            type="number"
            value={width}
            disabled={disabled}
            onChange={(e) => reshape(Number(e.target.value), height, resolution)}
          />
        </label>
        <label className="field">
          <span>{t("deployments.form.rows")}</span>
          <input
            type="number"
            value={height}
            disabled={disabled}
            onChange={(e) => reshape(width, Number(e.target.value), resolution)}
          />
        </label>
        <label className="field">
          <span>{t("maps.resolution")}</span>
          <input
            type="number"
            step={0.05}
            value={resolution}
            disabled={disabled}
            onChange={(e) => reshape(width, height, Number(e.target.value))}
          />
        </label>
      </div>
      <MapPainter
        map={map}
        onChange={setMap}
        disabled={disabled || saving}
        actions={
          <button type="button" className="primary" disabled={disabled || saving} onClick={() => void save()}>
            {t("deployments.form.saveMap")}
          </button>
        }
      />
    </>
  );
}

/** One input, its consequence, and the server's complaint about it.
 *
 * The complaint sits under the field rather than in a banner at the top:
 * a banner is exactly what makes a thirty-field form unusable, because
 * "2 validation errors for TaskProfile" leaves the reader to find which
 * two.
 */
function Field({
  label,
  note,
  error,
  value,
  step,
  disabled,
  onChange,
}: {
  label: string;
  note?: string;
  error?: string;
  value: unknown;
  step?: number;
  disabled: boolean;
  onChange: (value: unknown) => void;
}) {
  const numeric = step !== undefined;
  return (
    <label className="field" style={{ minWidth: 150 }}>
      <span>{label}</span>
      <input
        type={numeric ? "number" : "text"}
        step={step}
        disabled={disabled}
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(event) =>
          onChange(numeric ? Number(event.target.value) : event.target.value)
        }
        aria-invalid={error ? true : undefined}
      />
      {error ? <span className="badge err">{error}</span> : note ? <span className="muted">{note}</span> : null}
    </label>
  );
}

function Choice({
  label,
  value,
  options,
  disabled,
  onChange,
  error,
}: {
  label: string;
  value: unknown;
  options: string[];
  disabled: boolean;
  onChange: (value: string) => void;
  error?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={typeof value === "string" ? value : options[0]}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {error ? <span className="badge err">{error}</span> : null}
    </label>
  );
}
