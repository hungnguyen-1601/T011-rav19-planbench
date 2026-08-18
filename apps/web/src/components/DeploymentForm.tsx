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

import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import Link from "next/link";

import { Hint } from "@/components/Hint";
import { Icon, type IconName } from "@/components/Icon";
import { MapPainter } from "@/components/MapPainter";
import {
  MissionCanvas,
  MissionPoseFields,
  PlacementButtons,
  PlacementCaption,
  type PlacementMode,
} from "@/components/MissionPlacer";
import { Tabs, type TabDefinition } from "@/components/Tabs";
import { TrafficEditor, placementNote } from "@/components/TrafficEditor";
import { api } from "@/lib/api";
import { authFetch, fieldErrorsOf } from "@/lib/auth";
import { createSequencer } from "@/lib/sequencer";
import {
  addObstacle,
  changeMotionKind,
  placeOnMotion,
  previewRequestOf,
  removeObstacle,
  snapshotsOf,
  trafficOf,
} from "@/lib/traffic";
import {
  deleteWaypointAt,
  hitTest,
  interpretDoubleClick,
  interpretPointer,
  moveHandle,
  overlayOf,
} from "@/lib/trafficOverlay";
import { IDLE_TRAFFIC_UI, dragGate, trafficUiReducer, type Hit } from "@/lib/trafficUi";
import { pushHistory, undoHistory, type Snapshot } from "@/lib/undo";
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
import { COLUMN_GAP_PX, canvasSize, sideBySide } from "@/lib/canvasSize";
import { emptyBorderedMap } from "@/lib/demoMap";
import { firstTabWithError, tallyErrors, type FormTab } from "@/lib/formTabs";
import { useTranslation } from "@/lib/i18n";
import { listRobotProfiles, type RobotProfile } from "@/lib/models";
import type { LibraryEntry } from "@/lib/platformTypes";
import type { MapData, MapSummary, Point2D, Pose2D, ScenarioPreview } from "@/lib/types";
import { safetyEnvelope } from "@/lib/keepOut";

/** Where the map under this deployment comes from. */
type MapSource = "library" | "stored" | "drawn";

/** Everything one undo puts back.
 *
 * The mission is in here alongside the draft because it *is* part of
 * the document — `documentOf` assembles the two into one profile — and
 * because a misplaced start pose is the commonest thing to want back:
 * one click on the canvas moves it, and before this there was no way
 * to return it except by remembering the old numbers. */
interface FormMemory {
  draft: ProfileDraft;
  start: Pose2D | null;
  goal: Pose2D | null;
}

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
  /** The mission's own placement mode — start, goal or nothing.
   *
   * Traffic placement is *not* in here any more: which obstacle is
   * highlighted, which field the next click writes and which handle a
   * drag holds are three separate questions with invariants between
   * them, and they live in one reducer (`lib/trafficUi`) so no pair of
   * handlers can leave them pointing at different obstacles. The canvas
   * still sees a single mode: traffic placement wins while it is active,
   * this state otherwise. */
  const [placing, setPlacing] = useState<PlacementMode>("start");
  const [trafficUi, dispatchTrafficUi] = useReducer(trafficUiReducer, IDLE_TRAFFIC_UI);
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
  /** Which panel of controls is on top.
   *
   * Opens on the mission, because that is the tab whose controls the
   * map beside it is for. */
  const [activeTab, setActiveTab] = useState<FormTab>("mission");
  /** Measured rather than guessed from the viewport: a sidebar makes
   *  the window's width a liar about the room this form has.
   *
   * One measurement, of the whole form. The map column used to be
   * measured too, but it was a `1fr` track — so it grew to whatever
   * was left over while the canvas inside it stayed capped, and the
   * two columns ended up with a 290 px gap between them that belonged
   * to neither. The column is now exactly as wide as the map, which
   * makes measuring it the same as computing it. */
  const [shellRef, shellWidth] = useMeasuredWidth();

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
  /** What Ctrl-Z puts back, and what Ctrl-Shift-Z takes forward again.
   *
   * A snapshot holds the mission as well as the draft, because moving
   * a start pose is as much a change to the deployment as typing in a
   * field — and it is the one an author is most likely to make by
   * accident, since a stray click on the canvas does it. */
  const [history, setHistory] = useState<Snapshot<FormMemory>[]>([]);
  const [future, setFuture] = useState<Snapshot<FormMemory>[]>([]);
  /** The draft as it is *now*, for the handlers that resume after an
   *  await. A `draft` captured in a closure is the document as it was
   *  when the handler started, and writing it back undoes whatever was
   *  typed in between. */
  const draftRef = useRef(draft);
  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);
  /** The mission as it is now, for the same reason `draftRef` exists:
   *  a snapshot taken inside a handler must be of the document on
   *  screen, not of the render that created the handler. */
  const missionRef = useRef<{ start: Pose2D | null; goal: Pose2D | null }>({ start, goal });
  useEffect(() => {
    missionRef.current = { start, goal };
  }, [start, goal]);
  /** Distinguishes one continuous gesture from the next. Two drags of
   *  the same handle are two undo steps; the frames within one drag
   *  are not. */
  const gestureCount = useRef(0);

  /** Record the document a change is about to replace.
   *
   * Called *before* every write. `label` is what collapses a run into
   * one step: consecutive writes sharing it are one edit, so typing
   * four digits into a radius costs one undo rather than four, while
   * two separate drags of the same waypoint cost two.
   *
   * Redo is dropped here rather than merged, because a new edit made
   * after an undo is a different branch — keeping the old future would
   * offer to "redo" its way into a document nobody ever had.
   */
  const remember = useCallback((label: string) => {
    const document = draftRef.current;
    if (!document) return;
    setHistory((stack) =>
      pushHistory(stack, label, { draft: document, ...missionRef.current }),
    );
    setFuture((stack) => (stack.length === 0 ? stack : []));
  }, []);
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

  /** The press in flight, as the gesture itself needs to see it.
   *
   * **A companion to the reducer's `activeDrag`, not a rival.** The
   * reducer owns what is *shown* — which row is lit, whether the drag
   * has committed — and a dispatch is not visible to the handler that
   * made it, while a pointer-move arriving a millisecond later has to
   * know what was grabbed. So the mechanics live in a ref and the
   * display in the reducer, and the two are written at the same
   * moments.
   */
  const gesture = useRef<{
    hit: Hit;
    downClient: Point2D;
    committed: boolean;
    /** Which gesture this is, for the undo label. */
    id: number;
    /** The last position a *move* reported. What `pointercancel`
     *  flushes: cancel can arrive from a gesture interruption carrying
     *  a position nobody pointed at. */
    lastWorld: Point2D | null;
    pending: Point2D | null;
    frame: number | null;
  } | null>(null);
  /** Whether the current click sequence contained a real drag, so the
   *  double-click that ends it knows not to also delete. */
  const draggedInSequence = useRef(false);

  const set = useCallback(
    (path: string, value: unknown) => {
      // Labelled by path, so a run of keystrokes into one box is one
      // undo step and moving to another box starts a new one.
      remember(path);
      if (draft) onDraftChange(withValue(draft, path, value));
      invalidateCheck();
    },
    [draft, onDraftChange, invalidateCheck, remember],
  );

  /** The same write, but onto the document as it is *now*.
   *
   * A drag writes once per animation frame, and `set` closes over the
   * `draft` of the render that created the handler — so the second
   * frame would rebuild the document from the state before the first,
   * and the point would jitter between two positions. `draftRef` is
   * already the answer to this elsewhere (the map adoption had the same
   * bug across its `await`); this is the same fix for a callback that
   * outlives its render by design.
   */
  const setLive = useCallback(
    (path: string, value: unknown, label: string) => {
      remember(label);
      const current = draftRef.current;
      if (current) onDraftChange(withValue(current, path, value));
      invalidateCheck();
    },
    [onDraftChange, invalidateCheck, remember],
  );

  /** Write one handle to a position.
   *
   * **Takes the handle rather than reading it back off `gesture`**, and
   * that is not tidiness: the last write of a drag happens as the
   * gesture ends, and an earlier version cleared `gesture.current`
   * before calling this — so the flush found nothing to move and every
   * drag silently discarded the position the pointer was released at.
   * A parameter cannot be cleared out from under the call. */
  const flushDrag = useCallback(
    (hit: Hit, point: Point2D, gesture: number) => {
      const obstacles = trafficOf(draftRef.current);
      if (!obstacles[hit.index]) return;
      setLive(
        "environment.dynamic_obstacles",
        obstacles.map((obstacle, at) =>
          at === hit.index
            ? { ...obstacle, motion: moveHandle(obstacle.motion, hit.handle, point) }
            : obstacle,
        ),
        // Every frame of one drag shares a label and collapses to one
        // undo step; the next drag gets a new number and its own step.
        `drag#${gesture}`,
      );
    },
    [setLive],
  );

  /** One write per frame, however many moves the pointer reports.
   *
   * A move arrives per pixel travelled, and each one rebuilds the
   * document and re-renders the form. Coalescing to the frame keeps the
   * drag smooth; the position that matters — where the pointer stopped
   * — is written by the up handler regardless, so nothing is lost by
   * dropping the intermediate ones. */
  const scheduleFlush = useCallback(() => {
    const active = gesture.current;
    if (!active || active.frame !== null) return;
    active.frame = requestAnimationFrame(() => {
      const current = gesture.current;
      if (!current) return;
      current.frame = null;
      if (current.pending) {
        flushDrag(current.hit, current.pending, current.id);
        current.pending = null;
      }
    });
  }, [flushDrag]);

  /** The two shortcuts, reachable from an effect that is registered
   *  once.
   *
   * A ref rather than dependencies on the handlers themselves: those
   * close over `draft`, so a listener rebound on every keystroke would
   * add and remove a window handler per character typed. */
  const shortcuts = useRef<{ undo: () => void; redo: () => void }>({
    undo: () => {},
    redo: () => {},
  });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      if (event.key !== "z" && event.key !== "Z" && event.key !== "y" && event.key !== "Y") return;
      // A text box has its own undo, on the characters in it. Taking
      // that over to rewind the whole profile would answer a request
      // for one word back by throwing away a map.
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      const redo = event.key === "y" || event.key === "Y" || event.shiftKey;
      if (redo) shortcuts.current.redo();
      else shortcuts.current.undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
  /** Take the next adoption token and say so on screen.
   *
   * **The freezing has to start with the fetch, not with the commit.**
   * It began inside `adopt`, which runs only once the grid has arrived —
   * so for the whole length of the request the picker already showed the
   * new map while the draft, the canvas and the mission were still the
   * old one, and nothing was disabled. Filing in that window stores a
   * deployment nobody is looking at; previewing draws the old world
   * under the new map's name. The verdict and the picture go at the same
   * moment and for the same reason: what is on screen is already out of
   * date, whatever the answer turns out to be.
   */
  const beginAdoption = useCallback(() => {
    const token = adoption.claim();
    setAdopting(true);
    invalidateCheck();
    return token;
  }, [adoption, invalidateCheck]);

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
        // Nothing on the new map is the thing that was selected — and a
        // clamped index would be in range and wrong, so this clears.
        dispatchTrafficUi({ type: "reset" });
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
      if (!id) {
        adoption.supersede();
        setStoredMapId("");
        setAdopting(false);
        return;
      }
      const token = beginAdoption();
      setStoredMapId(id);
      void (async () => {
        try {
          const resource = await api.getMap(id);
          await adopt(resource.map_data, id, null, token);
        } catch (caught) {
          if (adoption.isCurrent(token)) {
            setError(caught instanceof Error ? caught.message : String(caught));
          }
        } finally {
          if (adoption.isCurrent(token)) setAdopting(false);
        }
      })();
    },
    [adoption, beginAdoption, adopt],
  );

  // Open on the default library scenario, so the form has a real map and
  // a drivable pair of poses before anybody touches it.
  useEffect(() => {
    if (!draft || mapData || source !== "library") return;
    let cancelled = false;
    const token = beginAdoption();
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
      } finally {
        // Without this a failed import leaves the form frozen for good:
        // `adopt`, which is what normally lifts it, is never reached.
        if (adoption.isCurrent(token)) setAdopting(false);
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

  /** Put back the document as it was before the last change.
   *
   * **Not bound while the caret is in a text box.** The browser's own
   * undo works there, on the characters being typed, and taking that
   * away to rewind the whole profile instead would be a surprise of
   * the worst kind — the author asked for their word back and lost
   * their map. Outside an input the shortcut is unclaimed, and that is
   * where it applies.
   *
   * Frozen while a check or an adoption is in flight, for the reason
   * every other control is: the answer coming back is about the
   * document that was sent.
   */
  const stepBack = () => {
    if (frozen) return;
    const step = undoHistory(history, { draft, ...missionRef.current });
    if (!step) return;
    setHistory(step.stack);
    setFuture((stack) => [...stack, step.undone]);
    onDraftChange(step.value.draft);
    setStart(step.value.start);
    setGoal(step.value.goal);
    invalidateCheck();
  };

  const stepForward = () => {
    if (frozen) return;
    const step = undoHistory(future, { draft, ...missionRef.current });
    if (!step) return;
    setFuture(step.stack);
    setHistory((stack) => [...stack, step.undone]);
    onDraftChange(step.value.draft);
    setStart(step.value.start);
    setGoal(step.value.goal);
    invalidateCheck();
  };

  // Rebound each render so the window listener, which is registered
  // once, always calls the version closed over the current document.
  shortcuts.current = { undo: stepBack, redo: stepForward };

  /** How near the pointer has to be, in screen pixels, to catch a
   *  point. Converted to metres at each event, because a map zoomed
   *  out has a very different idea of how far 8 px is. */
  const HIT_TOLERANCE_PX = 8;

  const whatIsUnder = (x: number, y: number, worldPerPixel: number) =>
    hitTest(
      trafficOf(draft),
      trafficUi.selectedObstacleIndex,
      { x, y },
      HIT_TOLERANCE_PX * worldPerPixel,
    );

  /** First refusal on every press. Returns whether the traffic took it.
   *
   * Declining is what leaves the mission placer exactly as it was: a
   * press on empty floor still moves the start, and a press while a
   * placement is armed still places, including the guard that stops a
   * drag spraying waypoints. */
  const claimPress = (press: {
    world: Point2D;
    client: Point2D;
    worldPerPixel: number;
    pointerId: number;
    detail: number;
  }): boolean => {
    if (frozen) return false;
    // The first press of a sequence starts it clean. `detail` counts
    // clicks, so the second press of a double-click leaves the flag
    // from the first alone — which is how the double-click handler
    // knows whether a real drag happened in between.
    if (press.detail <= 1) draggedInSequence.current = false;
    const hit = whatIsUnder(press.world.x, press.world.y, press.worldPerPixel);
    const verdict = interpretPointer(trafficUi.trafficPlacement !== null, hit);
    if (verdict === "place" || verdict === "mission" || hit === null) return false;
    if (verdict === "select") {
      dispatchTrafficUi({ type: "select", index: hit.index });
      return true;
    }
    gestureCount.current += 1;
    gesture.current = {
      hit,
      downClient: press.client,
      committed: false,
      id: gestureCount.current,
      lastWorld: press.world,
      pending: null,
      frame: null,
    };
    dispatchTrafficUi({
      type: "beginDrag",
      hit,
      pointerId: press.pointerId,
      downClient: press.client,
    });
    return true;
  };

  const dragTo = (move: { world: Point2D; client: Point2D }) => {
    const active = gesture.current;
    if (!active) return;
    const { world, client } = move;
    active.lastWorld = world;
    if (!active.committed) {
      // **Below the threshold nothing moves.** A press that ends here
      // is a click: it selected, or it was half of a double-click, and
      // nudging the point under it would be an edit nobody asked for.
      if (!dragGate(active.downClient, client)) return;
      active.committed = true;
      draggedInSequence.current = true;
      dispatchTrafficUi({ type: "dragCommitted" });
    }
    active.pending = world;
    scheduleFlush();
  };

  const endDrag = (end: { world: Point2D; cancelled: boolean }) => {
    const active = gesture.current;
    gesture.current = null;
    dispatchTrafficUi({ type: "endDrag" });
    if (!active) return;
    if (active.frame !== null) cancelAnimationFrame(active.frame);
    // A candidate never wrote anything and must not start now.
    if (!active.committed) return;
    // On cancel the event's own position is not to be trusted — a
    // gesture interruption can report one nobody pointed at — so the
    // last position a *move* gave is what the document keeps.
    const settled = end.cancelled ? active.lastWorld : end.world;
    if (settled) flushDrag(active.hit, settled, active.id);
  };

  const removeWaypointUnder = (at: { world: Point2D; worldPerPixel: number }) => {
    if (frozen) return;
    const hit = whatIsUnder(at.world.x, at.world.y, at.worldPerPixel);
    const verdict = interpretDoubleClick(
      trafficUi.trafficPlacement !== null,
      hit,
      draggedInSequence.current,
    );
    if (!verdict.delete) return;
    const obstacles = trafficOf(draft);
    set(
      "environment.dynamic_obstacles",
      obstacles.map((obstacle, at) =>
        at === verdict.index
          ? { ...obstacle, motion: deleteWaypointAt(obstacle.motion, verdict.waypoint) }
          : obstacle,
      ),
    );
  };

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
      // A refusal behind a tab nobody has reason to open is a refusal
      // nobody sees, and filing stays blocked with no visible cause.
      // The badges say where they are; this saves the author having to
      // hunt. Refusals on the identity row or with an address no tab
      // claims move nothing: both are already on screen, and jumping to
      // an unrelated tab to show them nothing is worse than staying.
      const jump = firstTabWithError(addressed);
      if (jump) setActiveTab(jump);
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
      unit={unitFor(path)}
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
      <div key={path} className="field deployment-noise-field">
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
          {note ? <Hint text={note} label={label} /> : null}
        </label>
        <Field
          label=""
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
    // Five fields at once, so one undo has to take back all five.
    remember(`vehicle:${id}`);
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

  const tally = tallyErrors(shownErrors);
  const twoColumns = sideBySide(shellWidth);
  const mapAspect = mapData && mapData.width > 0 ? mapData.height / mapData.width : 0.75;
  /** The map takes what is left after the panel has its minimum, up to
   *  its own cap. The panel then takes the rest — so on a wide screen
   *  the spare room goes to the controls rather than becoming a gap
   *  between two things that are supposed to sit beside each other. */
  // The map now owns a full-width row below the two configuration
  // columns. Its drawing buffer follows the measured form width (minus
  // the frame's margin, border and padding), so CSS never stretches the
  // canvas away from the coordinate system pointer events use.
  const roomForMap = Math.max(0, shellWidth - 44);
  const canvas = canvasSize(roomForMap, mapAspect, roomForMap);

  const badgeFor = (tab: FormTab) => tally.byTab[tab] || undefined;
  const badgeWord = (tab: FormTab) =>
    tally.byTab[tab]
      ? t("deployments.form.tabs.badge", { n: String(tally.byTab[tab]) })
      : undefined;

  const identityErrors = shownErrors.filter((entry) =>
    ["id", "claim_level", "deployment_role"].includes(entry.path),
  ).length;

  const missionTab = (
    <>
      <div className="toolbar" style={{ marginTop: 8 }}>
        <PlacementButtons
          mode={trafficUi.trafficPlacement?.mode ?? placing}
          onModeChange={(next) => {
            if (next === "start" || next === "goal" || next === "none") {
              setPlacing(next);
              dispatchTrafficUi({ type: "endPlacement" });
            }
          }}
          disabled={frozen}
        />
      </div>
      {/* Typed as well as clicked: a canvas cannot land on 2.00 exactly,
          and a deployment written to two decimals is the one somebody
          can repeat from the report. */}
      <MissionPoseFields
        start={start}
        goal={goal}
        onChange={(poses) => {
          setStart(poses.start);
          setGoal(poses.goal);
          invalidateCheck();
        }}
        disabled={frozen}
        startNote={t("decisions.map.startHeadingNote")}
        goalNote={t("decisions.map.goalHeadingNote")}
      />
    </>
  );

  const trafficTab = (
    <TrafficEditor
      obstacles={trafficOf(draft)}
      onChange={(next) => set("environment.dynamic_obstacles", next)}
      selectedIndex={trafficUi.selectedObstacleIndex}
      placement={trafficUi.trafficPlacement}
      onSelect={(index) => dispatchTrafficUi({ type: "select", index })}
      onPlacementToggle={(index, mode) => {
        const active =
          trafficUi.trafficPlacement?.index === index && trafficUi.trafficPlacement.mode === mode;
        dispatchTrafficUi(
          active ? { type: "endPlacement" } : { type: "beginPlacement", index, mode },
        );
        // While traffic owns the click, the mission must not also
        // believe the next one is its own.
        if (!active) setPlacing("none");
      }}
      onAdd={() => {
        const next = addObstacle(trafficOf(draft), start ?? { x: 0, y: 0 });
        set("environment.dynamic_obstacles", next);
        dispatchTrafficUi({ type: "obstacleAdded", count: next.length });
      }}
      onRemove={(index) => {
        set("environment.dynamic_obstacles", removeObstacle(trafficOf(draft), index));
        dispatchTrafficUi({ type: "obstacleRemoved", index });
      }}
      onKindChange={(index, kind) => {
        set(
          "environment.dynamic_obstacles",
          trafficOf(draft).map((each, at) =>
            at === index ? changeMotionKind(each, kind, start ?? { x: 0, y: 0 }) : each,
          ),
        );
        // The old law's handles and placements name fields that no
        // longer exist; the row stays selected — it is still the one
        // being edited.
        dispatchTrafficUi({ type: "motionKindChanged", index });
      }}
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
  );

  const robotTab = (
    <>
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
          <span>
            {t("deployments.form.vehicle")}
            <Hint text={t("deployments.form.vehicleNote")} label={t("deployments.form.vehicle")} />
          </span>
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
        {/* The undeclared-acceleration line stays visible: it is about
            *this* vehicle having a gap, not about what the picker
            does. The general explanation moved behind the mark. */}
        {undeclaredAccelerations ? (
          <p className="muted" style={{ flex: "1 1 260px", margin: 0 }}>
            {t("deployments.form.vehicleUndeclared")}
          </p>
        ) : null}
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
    </>
  );

  const constraintsTab = (
    <>
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
    </>
  );

  const noiseTab = (
    <>
      {/* Every source has a switch, and the switch writes an amplitude
          rather than a flag — see `noiseField`. Unticking one is how a
          deployment says "this site does not have that problem". */}
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        {noiseField("environment.sensor_noise.lidar_range_sigma_m", t("deployments.form.lidarSigma"))}
        {noiseField("environment.sensor_noise.wheel_slip_fraction", t("deployments.form.wheelSlip"))}
        {noiseField(
          "environment.sensor_noise.localization_drift_m",
          t("deployments.form.localizationDrift"),
          t("deployments.form.localizationDriftNote"),
        )}
      </div>
      <div className="row" style={{ alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
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
          G2's bound rests on a sample of one. Traffic is authored on the
          tab next to this one, against the map beside it.
       *
       * **This one stays on the page.** It is not an explanation of a
       * control, it is a warning about a *combination* of two — there
       * is no single mark to hang it on, and an author who never
       * hovers is exactly the one it is for. */}
      <p className="muted">{t("deployments.form.noiseNote")}</p>
    </>
  );

  const policiesTab = (
    <>
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
            <Hint
              text={
                obstacleSpeedDeclared
                  ? t("deployments.form.obstacleSpeedNote")
                  : t("deployments.form.obstacleSpeedOffNote")
              }
              label={t("deployments.form.obstacleSpeedEnabled")}
            />
          </label>
        </div>
        {obstacleSpeedDeclared
          ? field(V_OBSTACLE_MAX, t("deployments.form.obstacleSpeedValue"), 0.1)
          : null}
      </div>

      {/* **On the same tab as the closing speed, and next to the map
          rather than a scroll away from it.** Deciding whether the robot
          may replan is a thought you have *while looking at the traffic
          you just picked*, and in the single column this form used to be
          the control sat far below the picker that provokes it.

          It is highlighted rather than ticked when the chosen scenario
          has moving obstacles. Ticking it would be the form deciding an
          evaluation condition on the author's behalf, and the whole
          reason this field exists on the deployment is that such
          decisions are declared rather than inferred. Highlighting says
          "this is the choice you are about to skip"; ticking would say
          "we made it for you". */}
      <div className={traffic > 0 ? "notice warn" : ""} style={{ marginTop: 12 }}>
        <label className="row" style={{ alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={Boolean(at(draft, "replanning.enabled"))}
            disabled={frozen}
            onChange={(event) => set("replanning.enabled", event.target.checked)}
          />
          <strong>{t("deployments.form.replanningEnabled")}</strong>
          <Hint
            text={t("deployments.form.replanningNote")}
            label={t("deployments.form.replanningEnabled")}
          />
        </label>
        {/* The warning stays on the page; the explanation went behind
            the mark. This line only appears when the chosen scenario
            has traffic and replanning is off — a specific thing about
            to be measured wrongly, not a description of a control. */}
        {traffic > 0 && !at(draft, "replanning.enabled") ? (
          <p className="muted">{t("deployments.form.replanningTraffic", { n: String(traffic) })}</p>
        ) : null}
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
          <Hint
            text={t("deployments.form.recoveryNote")}
            label={t("deployments.form.recoveryEnabled")}
          />
        </label>
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
    </>
  );

  const hardwareTab = (
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
  );

  /* Labels written out rather than assembled from the id: the locale
     guard reads this file for translation keys written as literals, and
     a key built from a template variable is a key it cannot see — so a
     tab could ship without a translation and nothing would say so. */
  const TAB_CONTENT: { id: FormTab; label: string; content: ReactNode }[] = [
    { id: "mission", label: t("deployments.form.tabs.mission"), content: missionTab },
    { id: "traffic", label: t("deployments.form.tabs.traffic"), content: trafficTab },
    { id: "robot", label: t("deployments.form.tabs.robot"), content: robotTab },
    { id: "constraints", label: t("deployments.form.tabs.constraints"), content: constraintsTab },
    { id: "noise", label: t("deployments.form.tabs.noise"), content: noiseTab },
    { id: "policies", label: t("deployments.form.tabs.policies"), content: policiesTab },
    { id: "hardware", label: t("deployments.form.tabs.hardware"), content: hardwareTab },
  ];
  const sectionIcons: Record<FormTab, IconName> = {
    mission: "map",
    traffic: "alert",
    robot: "cpu",
    constraints: "check",
    noise: "sparkles",
    policies: "benchmark",
    hardware: "monitor",
  };
  const TABS: TabDefinition<FormTab>[] = TAB_CONTENT.map((tab) => ({
    ...tab,
    content: (
      <DeploymentSection
        title={tab.label}
        icon={sectionIcons[tab.id]}
        tone={tab.id}
        errors={tally.byTab[tab.id]}
        checked={checkedClean}
      >
        {tab.content}
      </DeploymentSection>
    ),
    badge: badgeFor(tab.id),
    badgeLabel: badgeWord(tab.id),
  }));

  const mapSelector = (
    <div className="deployment-map-selector">
      <div className="deployment-map-workspace">
      <div className="deployment-map-head">
        <div><span className="deployment-section-icon" aria-hidden="true"><Icon name="map" size={18} /></span><h4>{t("deployments.form.map")}</h4></div>
        {mapData ? <span className="badge muted-badge">{mapData.width} × {mapData.height}</span> : null}
      </div>
      <div className="deployment-map-sources" role="group" aria-label={t("deployments.form.map")}>
        {(["library", "stored", "drawn"] as MapSource[]).map((option) => (
          <button
            key={option}
            type="button"
            disabled={frozen}
            className={`deployment-map-source${source === option ? " active" : ""}`}
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
        <Link className="deployment-map-library-link" href="/maps">{t("decisions.map.drawOne")}</Link>
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

      </div>
    </div>
  );

  const mapArea = (
    <div className="deployment-map-fullwidth">
      {source === "drawn" ? (
        <div className="deployment-map-workspace deployment-map-stage deployment-map-editor">
          <DrawNewMap
            disabled={frozen}
            availableWidth={roomForMap}
            /* The claim is taken as the saved grid arrives rather than
               before the save: `DrawNewMap` owns that request and disables
               its own button while it runs, so there is never a second one
               to be overtaken by. */
            onSaved={(data, id) => void adopt(data, id, null, adoption.claim())}
            onError={setError}
          />
        </div>
      ) : (
      <div className="deployment-map-workspace deployment-map-stage deployment-map-preview">
      {mapData ? (
        <div className="deployment-map-frame">
        <MissionCanvas
          map={mapData}
          width={canvas.width}
          height={canvas.height}
          start={start}
          goal={goal}
          onChange={(poses) => {
            // The mission is part of the document being checked, so
            // moving it is as much an edit as typing in a field — and
            // as undoable. A stray click here is the accident this
            // whole history exists for.
            remember("mission");
            setStart(poses.start);
            setGoal(poses.goal);
            invalidateCheck();
          }}
          toolbar={
            <div className="toolbar" style={{ marginTop: 12 }}>
              <PlacementCaption
                mode={trafficUi.trafficPlacement?.mode ?? placing}
                modeNote={placementNote(trafficUi.trafficPlacement, trafficOf(draft), t)}
              />
            </div>
          }
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
          mode={trafficUi.trafficPlacement?.mode ?? placing}
          onModeChange={(next) => {
            // The toolbar only speaks the mission's modes. Choosing one
            // ends the traffic placement, or the editor would keep a
            // button lit for clicks it no longer receives.
            if (next === "start" || next === "goal" || next === "none") {
              setPlacing(next);
              dispatchTrafficUi({ type: "endPlacement" });
            }
          }}
          onPlace={(x, y) => {
            const placement = trafficUi.trafficPlacement;
            if (!placement) return;
            const obstacles = trafficOf(draft);
            const chosen = obstacles[placement.index];
            if (!chosen) return;
            set(
              "environment.dynamic_obstacles",
              obstacles.map((obstacle, at) =>
                at === placement.index
                  ? {
                      ...obstacle,
                      motion: placeOnMotion(obstacle.motion, placement.mode, { x, y }),
                    }
                  : obstacle,
              ),
            );
          }}
          /* Traffic sees each press first and takes only what belongs
             to it — a handle to drag, an obstacle to select. Everything
             it declines reaches the poses exactly as before. */
          onPointerDownFirst={claimPress}
          onPointerMoveWhileDown={dragTo}
          onPointerFinished={endDrag}
          onDoubleClickMap={removeWaypointUnder}
          dynamicObstacles={(preview?.dynamic_obstacles ?? []).map((obstacle) => ({
            name: obstacle.name,
            radius: obstacle.radius,
            position: obstacle.position,
          }))}
          obstacleSnapshots={snapshotsOf(preview)}
          /* The document's own traffic, drawn from the points it
             stores. Until this existed, placing waypoints drew nothing
             until somebody pressed Preview — so a route was authored by
             clicking into an empty map and hoping. */
          authoredTraffic={overlayOf(trafficOf(draft), trafficUi.selectedObstacleIndex)}
          previewTime={preview?.time}
        />
        <div className="deployment-map-legend" aria-label={t("deployments.form.map")}>
          <span><i className="legend-start" />{t("decisions.map.start")}</span>
          <span><i className="legend-goal" />{t("decisions.map.goal")}</span>
          <span><i className="legend-traffic" />{t("deployments.form.tabs.traffic")}</span>
        </div>
        </div>
      ) : (
        <p className="muted">{t("common.loading")}</p>
      )}

      {/* Two drawings of the same obstacles, and only one of them is
          the author's to move. Saying so beside the canvas rather than
          leaving it to be inferred from colour: the amber marker is the
          backend's answer to "where is it at t", and clicking it does
          nothing on purpose. */}
      {traffic > 0 ? (
        <p className="muted">
          {t("deployments.form.traffic.legendShort")}
          <Hint
            text={t("deployments.form.traffic.legend")}
            label={t("deployments.form.traffic.legendShort")}
          />
        </p>
      ) : null}

      <div className="row" style={{ marginTop: 8, alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        {/* Both boxes are asking a question about the episode rather
            than setting anything on the deployment, and neither label
            says so on its own: "Time" and "Seed" beside a map read as
            two more fields somebody has to fill in correctly. */}
        <label className="field" style={{ width: 130 }}>
          <span>
            {t("deployments.form.previewTime")}
            <Hint
              text={t("deployments.form.previewTimeNote")}
              label={t("deployments.form.previewTime")}
            />
          </span>
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
          <span>
            {t("deployments.form.previewSeed")}
            <Hint
              text={t("deployments.form.previewSeedNote")}
              label={t("deployments.form.previewSeed")}
            />
          </span>
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
        <Hint text={t("deployments.form.previewNote")} label={t("deployments.form.preview")} />
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
      </div>
      )}
    </div>
  );

  return (
    <div ref={shellRef} className="deployment-form">
      {error ? <div className="error-box">{error}</div> : null}

      {/* Above the tabs rather than on one of them: the id and the two
          claim fields are what the deployment *is*, and burying them
          behind a tab would make the first thing an author types the
          one thing they have to go looking for. */}
      <section className="deployment-section deployment-section--identity" id="deployment-identity">
      <div className="deployment-section-head">
        <span className="deployment-section-icon" aria-hidden="true"><Icon name="info" size={18} /></span>
        <h4>{t("deployments.form.identity")}</h4>
        {identityErrors ? <span className="badge err"><Icon name="alert" size={12} />{identityErrors}</span> : null}
      </div>
      <div className="deployment-identity-grid">
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
      </section>

      {/* Select the world beside its configuration. The actual map is a
          separate full-width row below, so both columns keep their job
          without confining the drawing to the left half. */}
      <div
        className={`deployment-config-grid${twoColumns ? " is-two-column" : ""}`}
        style={{
          display: "grid",
          gridTemplateColumns: twoColumns ? "minmax(0, 1fr) minmax(0, 1fr)" : "minmax(0, 1fr)",
          gap: COLUMN_GAP_PX,
          alignItems: "start",
          marginTop: 12,
        }}
      >
        {mapSelector}
        <div className="deployment-config-panel">
          <Tabs
            tabs={TABS}
            active={activeTab}
            onSelect={setActiveTab}
            idPrefix="deployment-form"
            ariaLabel={t("deployments.form.tabs.label")}
            className="deployment-tabs"
          />
        </div>
      </div>
      {mapArea}

      {/* **Sticky inside the form, not fixed to the window.** Fixed
          would sit over whatever is at the bottom of the page and take
          a bite out of a phone screen permanently. */}
      <div className="deployment-action-bar" id="deployment-actions">
        <div className="deployment-action-main">
          {/* Both frozen, and the reason is the same for each: while a map
              is being written out the canvas already shows it and the
              draft does not, so filing would store a deployment nobody is
              looking at. */}
          <button type="button" className="primary deployment-submit" disabled={frozen || !complete} onClick={() => void submit()} title={!complete ? t("deployments.file.idRule") : undefined}>
            {t("deployments.file.submit")}
          </button>
          <button type="button" disabled={frozen || !complete} onClick={() => void check()}>
            {checking ? t("deployments.form.validateBusy") : t("deployments.form.validate")}
          </button>
          {/* Buttons as well as the shortcut. Ctrl-Z is discoverable
              only to somebody who already suspects it is there, and the
              accident it undoes — a stray click that moved the start —
              happens to people who have not thought about undo at
              all. */}
          <button
            type="button"
            disabled={frozen || history.length === 0}
            onClick={stepBack}
            title={t("deployments.form.undoHint")}
          >
            <Icon name="chevronLeft" size={15} />
            {t("deployments.form.undo")}
          </button>
          <button
            type="button"
            disabled={frozen || future.length === 0}
            onClick={stepForward}
            title={t("deployments.form.redoHint")}
          >
            {t("deployments.form.redo")}
            <Icon name="chevronRight" size={15} />
          </button>
        </div>
        <div className="deployment-action-summary">
          <span className="muted">
            {t("deployments.file.idRule")}
            <Hint text={t("deployments.form.validateNote")} label={t("deployments.form.validate")} />
          </span>
          {tally.total > 0 ? (
            <span className="badge err">
              {t("deployments.form.tabs.total", { n: String(tally.total) })}
            </span>
          ) : null}
        </div>
        {checkedClean ? <p className="notice">{t("deployments.form.validateOk")}</p> : null}
        {/* Addresses no tab claims. Shown here in full rather than
            counted into whichever tab looked closest: a refusal filed
            under a heading that does not own it is a refusal the author
            will not find, and filing stays blocked meanwhile. */}
        {tally.unmapped.map((entry) => (
          <p key={`${entry.path}:${entry.message}`} className="notice warn">
            {entry.path}: {entry.message}
          </p>
        ))}
      </div>
    </div>
  );
}

function numberAt(draft: ProfileDraft, path: string): number | undefined {
  const value = at(draft, path);
  return typeof value === "number" ? value : undefined;
}

/** Display-only units. Values and payloads stay untouched; the suffix is
 * outside the input and exists solely to make engineering quantities
 * scannable without reopening their help text. */
function unitFor(path: string): string | undefined {
  if (path.endsWith("_mb")) return "MB";
  if (path === V_OBSTACLE_MAX) return "m/s";
  if (path.endsWith("_probability") || path.endsWith("_fraction") || path.endsWith("_rate_max") || path.endsWith("_rate_min")) return "ratio";
  if (path.endsWith("_velocity")) return path.includes("angular") ? "rad/s" : "m/s";
  if (path.endsWith("_acceleration")) return path.includes("angular") ? "rad/s²" : "m/s²";
  if (path.endsWith("_rad")) return "rad";
  if (path.endsWith("_s") || path === "robot.control_period") return "s";
  if (path.endsWith("_m") || path === "robot.radius") return "m";
  return undefined;
}

function DeploymentSection({
  title,
  icon,
  tone,
  errors,
  checked,
  children,
}: {
  title: string;
  icon: IconName;
  tone: FormTab;
  errors: number;
  checked: boolean;
  children: ReactNode;
}) {
  return (
    <section className={`deployment-section deployment-section--${tone}`}>
      <div className="deployment-section-head">
        <span className="deployment-section-icon" aria-hidden="true"><Icon name={icon} size={18} /></span>
        <h4>{title}</h4>
        {errors ? (
          <span className="badge err"><Icon name="alert" size={12} />{errors}</span>
        ) : checked ? (
          <span className="badge ok"><Icon name="check" size={12} /></span>
        ) : (
          <span className="badge muted-badge">—</span>
        )}
      </div>
      <div className="deployment-section-body">{children}</div>
    </section>
  );
}

/** The width of an element, kept current as it changes.
 *
 * A callback ref rather than `useRef`, because the node this watches
 * does not exist on the first render — the form shows a loading line
 * until the template arrives, and an effect that ran once at mount
 * would observe nothing and never look again.
 *
 * Zero until the first measurement. `canvasSize` treats that as "not
 * measured yet" and draws full size for one frame rather than
 * collapsing to nothing.
 */
function useMeasuredWidth(): [(node: HTMLDivElement | null) => void, number] {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!node || typeof ResizeObserver === "undefined") return;
    setWidth(node.getBoundingClientRect().width);
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);
  return [setNode, width];
}

/** Draw a grid from scratch, save it, and hand it to the form.
 *
 * Three size boxes and the shared painter — the same one `/maps/[id]`
 * uses, so there is one answer to what painting a map means.
 */
function DrawNewMap({
  disabled,
  availableWidth,
  onSaved,
  onError,
}: {
  disabled: boolean;
  availableWidth: number;
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
  const painterSize = canvasSize(availableWidth, height / Math.max(width, 1), availableWidth);

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
        width={painterSize.width}
        height={painterSize.height}
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
 * **The consequence is behind a mark; the complaint never is.** Those
 * two lines used to sit in the same place and they are not the same
 * kind of thing. A note explains a field to whoever wants it explained,
 * and thirty of them at once buried the controls they described. A
 * refusal is the server saying *this document will not be filed*, and
 * hiding that behind a hover would leave an author staring at a form
 * that does nothing when they press the button.
 */
function Field({
  label,
  note,
  error,
  value,
  step,
  unit,
  disabled,
  onChange,
}: {
  label: string;
  note?: string;
  error?: string;
  value: unknown;
  step?: number;
  unit?: string;
  disabled: boolean;
  onChange: (value: unknown) => void;
}) {
  const numeric = step !== undefined;
  const hasValue = value !== null && value !== undefined && String(value).trim() !== "";
  return (
    <label className={`field deployment-field${error ? " has-error" : hasValue ? " has-value" : ""}`}>
      <span>
        {label}
        {note ? <Hint text={note} label={label} /> : null}
      </span>
      <span className="deployment-field-control">
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
      {unit ? <span className="deployment-field-unit" aria-hidden="true">{unit}</span> : null}
      {hasValue && !error ? <Icon name="check" size={14} className="deployment-field-check" /> : null}
      </span>
      {error ? <span className="badge err">{error}</span> : null}
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
    <label className={`field deployment-field${error ? " has-error" : " has-value"}`}>
      <span>{label}</span>
      <select
        value={typeof value === "string" ? value : options[0]}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {error ? <span className="deployment-field-error"><Icon name="alert" size={13} />{error}</span> : null}
    </label>
  );
}
