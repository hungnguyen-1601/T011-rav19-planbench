"use client";

/** One selection run, read-only.
 *
 * **The gate table comes first, and that ordering is the point.** Six
 * feasibility gates run before anything is scored (HĐ-7), so a candidate
 * that failed one was never ranked at all — it is not a worse choice, it
 * is not a choice. Putting the recommendation at the top and the gates
 * in a tab underneath would invert the contract on screen and let a
 * reader take a winner without seeing who was eliminated to produce it.
 *
 * A run with no card is rendered as a *result*, never as an error: the
 * gate table answers "who was eliminated where, after how many runs",
 * which is the question HĐ-12 puts on a card in the first place.
 */

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { TraceViewer } from "@/components/TraceViewer";
import { ComparisonGrid } from "@/components/ComparisonGrid";
import { ConclusionPanel } from "@/components/ConclusionPanel";
import { Hint } from "@/components/Hint";
import { type HeadingField, candidateNames, headingField } from "@/lib/candidateHeading";
import { gateSummary } from "@/lib/gateSummary";
import {
  clampPage,
  pageCount,
  pageOf,
  pageSlice,
  pageWindow,
} from "@/lib/episodePages";
import { ProgressSync, type SyncSlot } from "@/components/ProgressSync";
import { commonProgress, panelCandidates, sideProgress, sideTime } from "@/lib/replaySync";
import { EvidencePanel } from "@/components/EvidencePanel";
import { panelPlan } from "@/lib/explainPanel";
import { Icon } from "@/components/Icon";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { BELOW_N_MIN, noticeKey, sampleLineFor, sampleNotice } from "@/lib/sample";
import { COPY_FEEDBACK_MS, type CopyOutcome, copyDecisionId, copyStateKey } from "@/lib/copyId";
import {
  GATES,
  approvedConfigUrl,
  decideConfig,
  withdrawConfig,
  getDecision,
  getTrace,
  getReplaySync,
  getExemplars,
  noCardReason,
  reviewRun,
  gateEvidence,
  gateResult,
  hasEpisodeOutcomes,
  hostWarningView,
  recommendedCandidateLabel,
  outcomesByEpisode,
  type DecisionRun,
  type EpisodeOutcome,
  type GateVerdict,
  type RunCandidate,
  type TracePayload,
  type DivergencePoint,
  type Exemplar,
  type ReplaySyncView,
  type RunningSample,
  observationClasses,
} from "@/lib/decisions";
import { downloadDecisionReport, downloadDecisionWorkbook } from "@/lib/reports";
import { initialPlayback, tick, type PlaybackState } from "@/lib/playback";

export default function DecisionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useTranslation();
  const [run, setRun] = useState<DecisionRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      // The review journal is no longer drawn, so it is no longer
      // fetched — a request whose response nothing reads is a request
      // that will keep working long after it stops meaning anything.
      const fetched = await getDecision(id);
      setRun(fetched);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (error) return <div className="error-box">{error}</div>;
  if (!run) return <p className="muted">{t("common.loading")}</p>;

  return (
    <section className="decision-page decision-detail-page">
      <header className="page-head decision-detail-head">
        {/* No 40px icon tile. It was the same `benchmark` glyph on every
            decision, so it distinguished nothing and named nothing —
            it only took the width the title needed. */}
        <div><span className="decision-eyebrow">{t("decisions.detail.eyebrow")}</span><h1>{run.task_profile_id}</h1>
        <p className="muted">
          {run.experiment_scope ?? "—"} · {run.created_at.slice(0, 16).replace("T", " ")} ·{" "}
          <Link href="/decisions">{t("decisions.backToList")}</Link>{" "}
          <CopyRunId id={run.id} />
        </p>
        <SampleLine run={run} /></div>
        <div className="decision-detail-badges"><span className={`badge ${run.ranked ? "ok" : "muted-badge"}`}>{run.ranked ? t("decisions.filter.ranked") : t("decisions.filter.unranked")}</span>
        </div>
      </header>

      {/* **The answer, then how it was reached, then who was allowed to
          be in the running.** The page used to open on the gate table,
          which is a list of eliminations — a reader arriving for the
          result met six columns of pass/fail before anything told them
          what the run concluded.

          Two of these positions are arguments rather than taste, and
          they survive any later reshuffle:

          - `SampleNotice` stays first. It says the run was cut short or
            ran fewer episodes than the declared risk allows, and that
            qualifies *every* number below it. (The sample *size* moved
            up into the page head as one line — a figure earns a card
            only when it is abnormal.)
          - `ExplanationHeader` stays immediately above `EvidencePanel`.
            It carries the evidence's caveats, and a qualifier under the
            thing it qualifies has already been scrolled past. */}
      <SampleNotice run={run} />
      <CandidateComparison run={run} />
      <TracePanel run={run} />
      <ExplanationHeader run={run} />
      <EvidencePanel run={run} />
      {/* The marks come after the evidence that justifies them, and the
          export buttons after the marks — that is the point at which a
          reader knows whether this run is worth sending on. */}
      <ConclusionPanel run={run} />
      <ExportReport runId={run.id} />
      {/* **No gate table.** Every candidate now has a card carrying
          G1-G6 and its blocking list, and the table under the cards
          carries the numbers the gate table used to hold - for all of
          them, not the first two. What was left of it was the same
          data a third time. */}
      <Outcome run={run} />
      {/* `Conditions`, `Provenance` and the review journal are out for
          now, at An's call — the measurement environment, the ids for
          rebuilding a run and the list of who read it are not what this
          page is being read for yet. `HumanActs` stays: it is what
          *records* an approval, and only the display of that record
          went. */}
      <HumanActs run={run} onDone={refresh} />
    </section>
  );
}

/** Side-by-side presentation of the backend's candidate evidence.
 * Recommendation comes only from `recommended_candidate_id`; metric
 * direction is deliberately not inferred in this view. */
function CandidateComparison({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates = run.report?.candidates ?? [];
  if (candidates.length === 0) return null;
  // The table itself lives in `components/ComparisonGrid` — exported so
  // tests can render it, which they cannot do with a function declared
  // inside a page that fetches. What stays here is the panel around it.
  //
  // One choice of heading for the whole panel: the gate detail below
  // names each candidate the same way its column does.
  const heading = headingField(candidates);
  const summary = gateSummary(candidates);
  return (
    <section className="panel comparison-results" aria-labelledby="comparison-results-title">
      <div className="comparison-results-head">
        <div><span className="decision-eyebrow">{t("decisions.detail.evidence")}</span><h3 id="comparison-results-title">{t("decisions.detail.results")}</h3></div>
        {/* Shown only when there *is* one. "No recommendation from this
            run" said here as well as in the header badge and again in
            the panel below, which spells out which of the three
            no-card situations this is and what to do about it — three
            copies of one fact, and the least useful of them was this. */}
        {run.card ? <span className="badge ok"><Icon name="trophy" size={13} />{recommendedCandidateLabel(run) ?? run.card.recommended.candidate_id}</span> : null}
      </div>
      {/* Moved off the gate table, which is gone. This is a *finding* —
          two candidates shown different things are answering different
          questions, and ΔU would be measuring the privilege rather than
          the planner — so it cannot leave the page with the table it
          happened to sit in. */}
      <ObservationNotice candidates={candidates} />
      {/* The host warning is *not* a banner over the table. G4 reads
          wall-clock latency, so an unpinned machine qualifies the p99 row
          and nothing else; above the table it reads as a caveat on every
          number, which is a wider claim than the measurement supports. */}
      <ComparisonGrid run={run} candidates={candidates} hostWarning={<HostWarning run={run} />} />

      {/* **Collapsed, because the verdict is already on the column head.**
          Open, it is six cells per candidate — the *reason* behind a
          verdict the reader has already been given. Closed, its summary
          still has to be true, which is why the badge states a ratio: it
          sits on the control somebody uses to decide whether to open
          this at all, so "cleared" over a field where one candidate was
          eliminated is wrong at the point of maximum cost. */}
      {summary ? (
        <details className="comparison-gate-detail">
          <summary>
            <Icon name="chevronRight" size={14} />
            <span>{t("decisions.gates.detail")}</span>
            <Hint text={t("decisions.gates.note")} label={t("decisions.gates.detail")} />
            <span className={`badge ${summary.tone}`}>
              {t(summary.key, {
                total: String(summary.total),
                blocked: String(summary.blocked),
                cleared: String(summary.cleared),
              })}
            </span>
          </summary>
          <div className="comparison-gate-detail-body">
            {candidates.map((candidate, index) => (
              <div key={candidate.candidate_id}>
                <p className={`comparison-gate-owner candidate-${SIDES[index] ?? "n"}`}>
                  {candidateNames(candidate, heading).heading}
                </p>
                <div className="comparison-gate-grid">
                  {GATES.map((gate) => (
                    <div key={gate}>
                      <span className="candidate-gate-name">
                        <code>{gate}</code>
                        <Hint text={t(`decisions.gates.blocks.${gate}`)} label={gate} />
                      </span>
                      <GateCell verdict={candidate.gates?.[gate]} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

/** What the machine was doing while the latency was measured.
 *
 * **Not context — a caveat on a number two rows down.** G4 reads
 * wall-clock latency, so a run measured on an unpinned host measured a
 * machine that was also doing something else: the same candidate came
 * out at 59.30 ms unpinned and 16.10 ms pinned to two cores.
 *
 * It used to sit in the panel describing the measurement environment.
 * That panel is gone, and this could not go with it: the grid below
 * shows pooled p99 against the deployment's limit, and a figure that may
 * be several times too high is worse company for a limit than no figure
 * would be.
 *
 * **What may and may not be reinterpreted.** The rule used to be that
 * the whole sentence was rendered verbatim, because a client that
 * rewords a caveat can water it down. The rule was right about the
 * wrong thing: what must survive intact is the **numbers**, and holding
 * the language fixed too meant an English page showing a Vietnamese
 * paragraph. So the platform now sends a code and its figures, and the
 * wording is chosen here — while a run that predates that, or one
 * carrying a code this build has never heard of, still renders the
 * platform's own sentence untouched.
 */
function HostWarning({ run }: { run: DecisionRun }) {
  const { t, locale } = useTranslation();
  const view = hostWarningView(run.report?.measurement_environment, locale);
  if (!view) return null;
  return (
    // A line inside the p99 row's label, not a `.notice` box. It used to
    // be a bordered banner over the whole table, which is a box shaped
    // like a claim about everything under it; the caveat is about one
    // row. The box also cannot sit in a table cell without looking like
    // a panel that lost its way.
    <span className="comparison-host-warning">
      <Icon name="alert" size={12} />
      <span>{view.translated ? t(view.key, view.vars) : view.text}</span>
    </span>
  );
}

/** Column letters, and a tint that runs out on purpose.
 *
 * The pair colours cover two. A third candidate gets `candidate-n` —
 * neutral — rather than looping back to candidate A's blue, which would
 * put two different stacks in one colour on a page whose whole job is
 * telling them apart.
 */
const SIDES = ["a", "b"] as const;


function ExplanationHeader({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const plan = panelPlan(run);
  return (
    <div className="panel explanation-header">
      <div className="panel-head">
        <h3>{t("explain.title")}</h3>
      </div>
      <p>{t(plan.headlineKey)}</p>
      {plan.caveatKeys.length > 0 ? (
        <ul className="explanation-caveats">
          {plan.caveatKeys.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function TracePanel({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  // Winner first, and the *same* two the exemplar recipe runs on — both
  // read the card rather than list order.
  const candidates = useMemo(
    () => panelCandidates(run, run.report?.candidates ?? []),
    [run],
  );
  // From the **whole** report, not from `candidates` above: that list is
  // reordered and can be shorter than the field, and a heading chosen
  // from a subset could name a different field than the comparison grid
  // did. One page must not call the same candidate two things.
  const heading = headingField(run.report?.candidates ?? []);
  const episodes = run.report?.sample?.episode_context_ids ?? [];
  const [episodeId, setEpisodeId] = useState(episodes[0] ?? "");
  const [slots, setSlots] = useState<Record<string, TraceSlot>>({});
  const [mode, setMode] = useState<"flat" | "raised">("flat");
  // Named `syncMode`, not `mode`: `mode` above is how the map is *drawn*
  // (2D or 2.5D). Two unrelated ideas under one name is how a later
  // reader concludes the page already had two sync modes.
  const [syncMode, setSyncMode] = useState<"time" | "progress">("time");
  // **One switch per canvas.** The first version shared a single
  // control, on the reasoning that two panels showing different kinds
  // of number cannot be compared. That was already untrue of its own
  // automatic behaviour — each replay flips to its result when *it*
  // runs out, so a short run and a long one legitimately differ for
  // half the episode — and it forbade the case a reader actually wants:
  // reading one stack's results while the other is still driving.
  //
  // Unset means automatic: that replay switches when it reaches its own
  // end.
  const [finalFor, setFinalFor] = useState<{ a: boolean; b: boolean }>({ a: false, b: false });
  const [sync, setSync] = useState<SyncSlot>({ state: "idle" });
  /** Empty until the recipe answers, and empty for a run too old to
   *  carry per-episode utility — the plain list is the honest fallback,
   *  not a set chosen another way under a preregistered label. */
  const [exemplars, setExemplars] = useState<Exemplar[]>([]);
  const [playback, setPlayback] = useState<PlaybackState>(initialPlayback);
  /** Where the progress playhead is, in metres of arc length. A second
   *  state rather than reusing `playback.time`, whose unit is seconds —
   *  one variable holding two units is a bug waiting for a reader. */
  const [scan, setScan] = useState<PlaybackState>(initialPlayback);
  const comparisonRef = useRef<HTMLDivElement | null>(null);
  const requestId = useRef(0);

  const loadPair = useCallback(async (episode: string) => {
    const currentRequest = ++requestId.current;
    setPlayback(initialPlayback);
    setSlots(Object.fromEntries(candidates.map((candidate) => [candidate.candidate_id, { state: "loading" }])));
    await Promise.all(candidates.map(async (candidate) => {
      const outcome = outcomesByEpisode(candidate).get(episode);
      if (!outcome) {
        if (currentRequest === requestId.current) {
          setSlots((current) => ({ ...current, [candidate.candidate_id]: { state: "missing" } }));
        }
        return;
      }
      try {
        const trace = await getTrace(run.id, candidate.candidate_id, episode);
        if (currentRequest === requestId.current) {
          setSlots((current) => ({ ...current, [candidate.candidate_id]: trace.x.length > 0 ? { state: "ready", trace } : { state: "empty" } }));
        }
      } catch (caught) {
        if (currentRequest !== requestId.current) return;
        const message = caught instanceof Error ? caught.message : String(caught);
        setSlots((current) => ({
          ...current,
          [candidate.candidate_id]: /404|not found|does not exist/i.test(message)
            ? { state: "missing" }
            : { state: "error", message },
        }));
      }
    }));
  }, [candidates, run.id]);

  useEffect(() => {
    if (episodeId) void loadPair(episodeId);
  }, [episodeId, loadPair]);

  useEffect(() => {
    let live = true;
    getExemplars(run.id)
      .then((set) => {
        if (!live) return;
        // Fail closed on disagreement. The server reads the card and so
        // does this page, so they should never differ — and if they ever
        // do, four chips labelling episodes of *another* pair is worse
        // than no chips.
        const shown = candidates.map((candidate) => candidate.candidate_id);
        const about = [set.candidate_a, set.candidate_b];
        setExemplars(about.every((id) => shown.includes(id)) ? set.exemplars : []);
      })
      .catch(() => live && setExemplars([]));
    return () => {
      live = false;
    };
  }, [candidates, run.id]);

  // Progress-sync is computed by the platform, not here: projecting in
  // the browser would put a second copy of the arc-length rules in
  // TypeScript, and the two would drift the first time either is fixed.
  //
  // **Fetched in both alignment modes**, not just the progress one. The
  // same response carries the per-step series the tiles under each
  // canvas read, and those are shown whichever way the two replays are
  // aligned — the numbers are each candidate's own standing at its own
  // current row, which does not depend on how the panels are paired.
  // Not fetching it in time mode was the reason the metrics appeared
  // only behind a toggle nobody had a reason to press.
  useEffect(() => {
    if (!episodeId || candidates.length < 2) return;
    let live = true;
    setSync({ state: "loading" });
    setScan(initialPlayback);
    getReplaySync(run.id, episodeId, candidates[0].candidate_id, candidates[1].candidate_id)
      .then((view) => live && setSync({ state: "ready", view }))
      .catch((caught: unknown) =>
        live &&
        setSync({ state: "error", message: caught instanceof Error ? caught.message : String(caught) }),
      );
    return () => {
      live = false;
    };
  }, [candidates, episodeId, run.id]);

  const traces = candidates.flatMap((candidate) => {
    const slot = slots[candidate.candidate_id];
    return slot?.state === "ready" ? [slot.trace] : [];
  });
  const duration = Math.max(0, ...traces.map((trace) => trace.t.at(-1) ?? 0));

  useEffect(() => {
    if (!playback.playing) return;
    const timer = window.setInterval(() => setPlayback((current) => tick(current, 0.05, duration)), 50);
    return () => window.clearInterval(timer);
  }, [duration, playback.playing]);

  const view: ReplaySyncView | null = sync.state === "ready" ? sync.view : null;

  /** A click on one candidate's latency chart, applied to **both**.
   *
   * The chart hands back a moment on that candidate's own clock, and
   * what the pair does with it depends on the alignment:
   *
   * - by time, the two panels share a wall clock, so the seconds go
   *   straight to the shared scrubber;
   * - by progress, the scrubber is in **metres**, so the timestamp is
   *   converted through the rows the view published — the same rows
   *   `sideTime` reads forwards.
   *
   * Seeking only the canvas that was clicked would be the smaller
   * change and would break the one thing this view is for: at any
   * moment the two panels are supposed to be answering the same
   * question.
   */
  const seekFrom = (side: "a" | "b", seconds: number) => {
    // **Playback is left alone.** An earlier version paused on every
    // seek, reasoning that a replay which keeps rolling walks away from
    // the moment just asked for. In use that is backwards: clicking the
    // chart is how you jump to the interesting part and *watch it*, and
    // having to press play again every time makes the chart a worse
    // scrubber than the scrubber.
    if (syncMode === "time") {
      setPlayback((current) => ({ ...current, time: Math.min(seconds, duration) }));
      return;
    }
    setScan((current) => ({ ...current, time: sideProgress(view, seconds, side) }));
  };
  const span = view ? commonProgress(view) : 0;

  useEffect(() => {
    if (!scan.playing) return;
    const timer = window.setInterval(() => setScan((current) => tick(current, 0.05, span)), 50);
    return () => window.clearInterval(timer);
  }, [scan.playing, span]);

  const plan = panelPlan(run);
  if (candidates.length === 0 || episodes.length === 0) return null;
  // The viewer stays for every outcome — a candidate that failed a gate
  // has traces, and hiding them would hide the only evidence those runs
  // have. What a run without a comparison does not get is the four
  // preregistered episodes, below.
  if (!plan.showTraceEvidence) return null;

  const chooseEpisode = (episode: string, scroll = false) => {
    setEpisodeId(episode);
    if (scroll) window.setTimeout(() => comparisonRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  };

  return (
    <div className="panel decision-sample-panel episode-comparison">
      <div className="panel-head">
        <h3>{t("trace.title")} <Hint text={t("trace.note")} label={t("trace.title")} /></h3>
      </div>

      <EpisodeOutcomes
        run={run}
        selectedEpisode={episodeId}
        onPick={(episode) => chooseEpisode(episode, true)}
      />

      {/* **No episode dropdown.** It listed ids and nothing else, so
          choosing from it was choosing blind — the table above says
          which episodes anyone failed and which two candidates
          disagreed on, which is what a reader picks by. Rows and
          exemplar chips are the pickers now. */}
      <div className="episode-toolbar">
        <div className="episode-view-toggle" role="group" aria-label={t("trace.viewMode")}>
          {(["flat", "raised"] as const).map((option) => <button key={option} type="button" className={mode === option ? "primary" : ""} aria-pressed={mode === option} onClick={() => setMode(option)}>{t(`mapView.${option}`)}</button>)}
        </div>
        {plan.showExemplars && exemplars.length > 0 ? (
          <div className="episode-exemplars" aria-label={t("trace.exemplar.title")}>
            <span className="muted">{t("trace.exemplar.title")}:</span>
            {exemplars.map((item) => (
              <button
                key={item.role}
                type="button"
                className={`chip${episodeId === item.episode_context_id ? " primary" : ""}`}
                title={t(`trace.exemplar.why.${item.role}`)}
                onClick={() => chooseEpisode(item.episode_context_id, true)}
              >
                {t(`trace.exemplar.${item.role}`)}
                {item.tie_break_over.length > 0 ? ` (${t("trace.exemplar.tied")})` : ""}
              </button>
            ))}
          </div>
        ) : null}
        <div className="episode-view-toggle" role="group" aria-label={t("trace.sync.mode")}>
          {(["time", "progress"] as const).map((option) => <button key={option} type="button" className={syncMode === option ? "primary" : ""} aria-pressed={syncMode === option} onClick={() => setSyncMode(option)}>{t(`trace.sync.${option}`)}</button>)}
        </div>
      </div>

      <div ref={comparisonRef} className="episode-comparison-stage" tabIndex={-1}>
        <EpisodeHeader run={run} episodeId={episodeId} candidates={candidates} />
        {syncMode === "time" ? (
          <SharedPlayback playback={playback} duration={duration} onChange={setPlayback} />
        ) : (
          <ProgressSync sync={sync} scan={scan} span={span} onScan={setScan} candidates={candidates} />
        )}
        <EpisodeLegend />
        <div className="episode-comparison-grid">
          {/* The same choice the comparison grid made. Two panels on one
              page naming a candidate by different fields is worse than
              either choice on its own. */}
          {candidates.map((candidate, index) => {
            const side = index === 0 ? "a" : "b";
            // In progress-sync the two panels are at *different*
            // timestamps on purpose — that is the whole difference
            // between the modes, and it is why the warning above is
            // not optional.
            const at = syncMode === "progress" ? sideTime(view, scan.time, side) : playback.time;
            return (
              <CandidateEpisode
                key={candidate.candidate_id}
                candidate={candidate}
                heading={heading}
                side={side}
                episodeId={episodeId}
                slot={slots[candidate.candidate_id] ?? { state: "loading" }}
                mode={mode}
                playbackTime={at}
                running={view?.running?.by_step[side] ?? null}
                forceFinal={finalFor[side]}
                onToggleFinal={() => setFinalFor((current) => ({ ...current, [side]: !current[side] }))}
                onSeek={(seconds) => seekFrom(side, seconds)}
                isReferenceRuler={view?.reference_source_candidate_id === candidate.candidate_id}
                onRetry={() => void loadPair(episodeId)}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

type TraceSlot =
  | { state: "loading" }
  | { state: "ready"; trace: TracePayload }
  | { state: "missing" | "empty" }
  | { state: "error"; message: string };

function outcomeLabel(outcome: EpisodeOutcome | undefined, t: (key: string) => string): string {
  if (!outcome) return t("trace.missing");
  return outcome.success ? t("decisions.episodes.pass") : t(`decisions.episodes.reason.${outcome.failure_reason}`);
}

function outcomeTone(outcome: EpisodeOutcome | undefined): string {
  if (!outcome) return "muted-badge";
  if (outcome.success) return "ok";
  return outcome.failure_reason === "timeout" ? "warn" : "err";
}

function EpisodeHeader({ run, episodeId, candidates }: { run: DecisionRun; episodeId: string; candidates: RunCandidate[] }) {
  const { t } = useTranslation();
  const index = (run.report?.sample?.episode_context_ids ?? []).indexOf(episodeId) + 1;
  return <header className="episode-comparison-head"><div><span className="decision-eyebrow">{t("trace.episode")} #{index}</span><h4>{episodeId}</h4><p className="muted">{t("trace.deployment")}: {run.task_profile_id}</p></div><div className="episode-result-badges">{candidates.map((candidate, candidateIndex) => { const outcome = outcomesByEpisode(candidate).get(episodeId); return <span key={candidate.candidate_id} className={`badge ${outcomeTone(outcome)}`}>Candidate {candidateIndex === 0 ? "A" : "B"}: {outcomeLabel(outcome, t)}</span>; })}</div></header>;
}

function SharedPlayback({ playback, duration, onChange }: { playback: PlaybackState; duration: number; onChange: (next: PlaybackState) => void }) {
  const { t } = useTranslation();
  return <div className="episode-playback"><button type="button" aria-label={playback.playing ? t("trace.pause") : t("trace.play")} onClick={() => onChange({ ...playback, playing: !playback.playing && duration > 0 })}>{playback.playing ? t("trace.pause") : t("trace.play")}</button><button type="button" aria-label={t("trace.replay")} onClick={() => onChange({ ...playback, time: 0, playing: duration > 0 })}>{t("trace.replay")}</button><label><span>{t("trace.speed")}</span><select value={playback.speed} onChange={(event) => onChange({ ...playback, speed: Number(event.target.value) })}>{[0.25, 0.5, 1, 2, 4, 8].map((speed) => <option key={speed} value={speed}>{speed}×</option>)}</select></label><input type="range" min={0} max={duration || 0} step="0.01" value={Math.min(playback.time, duration)} aria-label={t("trace.timeline")} aria-valuetext={`${playback.time.toFixed(1)} / ${duration.toFixed(1)} s`} onChange={(event) => onChange({ ...playback, playing: false, time: Number(event.target.value) })}/><output>{playback.time.toFixed(1)} / {duration.toFixed(1)} s</output></div>;
}

function EpisodeLegend() {
  const { t } = useTranslation();
  const items = [["start", t("trace.legend.start")], ["goal", t("trace.legend.goal")], ["candidate-a", t("trace.legend.candidateA")], ["candidate-b", t("trace.legend.candidateB")], ["dynamic", t("trace.legend.dynamic")], ["collision", t("trace.legend.collision")]];
  // The colour note used to sit under each canvas — the same four
  // sentences rendered twice, side by side. It describes how the canvas
  // is drawn, which is one fact about the pair rather than one per
  // candidate, so it belongs here with the legend it explains.
  return <div className="episode-legend" aria-label={t("trace.legend.title")}><div className="episode-legend-keys">{items.map(([tone, label]) => <span key={tone}><i className={`legend-dot legend-dot--${tone}`} aria-hidden="true" />{label}</span>)}</div><Hint text={t("trace.colourNote")} label={t("trace.legend.title")} /></div>;
}

function CandidateEpisode({ candidate, heading, side, episodeId, slot, mode, playbackTime, running, forceFinal, onToggleFinal, onSeek, isReferenceRuler, onRetry }: { candidate: RunCandidate; heading: HeadingField; side: "a" | "b"; episodeId: string; slot: TraceSlot; mode: "flat" | "raised"; playbackTime: number; running: RunningSample[] | null; forceFinal: boolean; onToggleFinal: () => void; onSeek: (seconds: number) => void; isReferenceRuler: boolean; onRetry: () => void }) {
  const { t } = useTranslation();
  const outcome = outcomesByEpisode(candidate).get(episodeId);
  const ready = slot.state === "ready" ? slot : null;
  const finalPanel = <EpisodeMetrics outcome={outcome} lastEvent={ready ? (ready.trace.events.at(-1)?.event ?? null) : null} />;
  // Whichever field distinguishes this run's candidates — the same one
  // the comparison grid uses. On a local-controller comparison the stack
  // is identical on both sides, so naming the card by the stack labelled
  // both cards `astar+dwa`, and so did the accessible name of each
  // card's "Show final results" button.
  const names = candidateNames(candidate, heading);
  return <article className={`episode-candidate episode-candidate--${side}`}><header><div><span>Candidate {side.toUpperCase()}</span><h4>{names.heading}</h4><code>{names.secondary}</code></div><div className="episode-candidate-actions"><span className={`badge ${outcomeTone(outcome)}`}>{outcomeLabel(outcome, t)}</span>{/* Named with the field that differs, because the page carries
        two of these and "Show final results" twice over is two controls
        a screen reader cannot tell apart — which is exactly what the
        stack gave it whenever the stack was the same on both sides. */}
      <button type="button" className={forceFinal ? "primary" : ""} aria-pressed={forceFinal} aria-label={`${t(forceFinal ? "trace.metricsView.live" : "trace.metricsView.final")} — ${names.heading}`} title={t("trace.metricsView.hint")} onClick={onToggleFinal}>{t(forceFinal ? "trace.metricsView.live" : "trace.metricsView.final")}</button></div></header><div className="episode-map">{slot.state === "loading" ? <div className="episode-skeleton" role="status">{t("trace.loadingCandidate")}</div> : ready ? <TraceViewer trace={ready.trace} playbackTime={playbackTime} mode={mode} showControls={false} candidateSide={side} running={running} finalPanel={finalPanel} forceFinal={forceFinal} onSeek={onSeek} isReferenceRuler={isReferenceRuler} /> : slot.state === "missing" ? <div className="episode-empty" role="status">{t("trace.missing")}</div> : slot.state === "empty" ? <div className="episode-empty" role="status">{t("trace.emptyFrames")}</div> : <div className="episode-error" role="alert"><p>{t("trace.loadError")}</p><button type="button" onClick={onRetry}>{t("common.retry")}</button></div>}</div>{/* A candidate whose trace would not load has no replay to run, so
      there is no live row for the result to replace — and the result
      is still the answer to what happened. Shown outright rather than
      hidden behind a swap that has nothing to swap with. */}
    {ready ? null : finalPanel}</article>;
}

/** What the episode came to, once. Nothing here moves with the scrubber.
 *
 * `Last event` sits here rather than beside the live readings because it
 * is a fact about the end of the run, not about the moment on screen. It
 * is kept **beside** `Result` rather than folded into it: `Result` is
 * the gate's reading of the episode and `Last event` is HĐ-5's own final
 * record, and the two are only usually the same sentence.
 *
 * There is no `Episode length` row to add — `Travel time` is that
 * number, taken from the scored outcome instead of from the trace's last
 * timestamp, so the tile that used to show it was a second reading of
 * one quantity.
 */
function EpisodeMetrics({ outcome, lastEvent }: { outcome: EpisodeOutcome | undefined; lastEvent: string | null }) {
  const { t } = useTranslation();
  const rows: [string, string, string][] = [[t("trace.result"), outcome ? outcomeLabel(outcome, t) : "—", t("trace.tip.result")], [t("trace.outcome"), lastEvent ?? t("trace.noEvent"), t("trace.tip.lastEvent")], [t("metrics.travelTime"), outcome ? `${outcome.travel_time_s.toFixed(2)} s` : "—", t("trace.tip.time")], [t("metrics.minClearance"), outcome ? `${outcome.min_clearance.toFixed(3)} m` : "—", t("trace.tip.clearance")], [t("trace.p99Latency"), outcome ? `${outcome.p99_latency_ms.toFixed(2)} ms` : "—", t("trace.tip.latency")], [t("trace.collision"), outcome ? String(outcome.collision_count) : "—", t("trace.tip.collision")], [t("metrics.replanCount"), outcome?.replan_count === undefined ? "—" : String(outcome.replan_count), t("trace.tip.replan")]];
  return <dl className="episode-metrics">{rows.map(([label, value, tip]) => <div key={label} title={tip}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}

/** Which episodes each candidate passed, one row per episode.
 *
 * **The gate table says how much went wrong; this says which part.** A
 * row reading "G3: fail, 70% success" is a claim about thirty episodes
 * nobody could name, and thirty collisions and thirty timeouts produce
 * that identical row while asking for completely different work. The
 * numbers were always computed — every `EpisodeMetricSet` carries
 * `success` and `failure_reason` — and the report simply pooled them.
 *
 * Episodes down and candidates across, because the comparison is
 * *paired*: the same episode ran for every candidate (HĐ-7.3), and the
 * interesting cell is the one where they disagree. Candidates down would
 * put those two verdicts in different rows.
 *
 * A cell is a button. Finding the episode that collided and then having
 * to copy its hash into a dropdown is most of the work of looking at it.
 */
function EpisodeOutcomes({
  run,
  selectedEpisode,
  onPick,
}: {
  run: DecisionRun;
  selectedEpisode: string;
  onPick: (episodeContextId: string) => void;
}) {
  const { t } = useTranslation();
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [page, setPage] = useState(0);
  const candidates = run.report?.candidates ?? [];
  const episodes = run.report?.sample?.episode_context_ids ?? [];

  // **Follow the selection onto its page.** Exemplar chips and the
  // viewer can move the episode from outside this table; leaving the
  // strip where it was would highlight nothing and read as the pick not
  // registering.
  useEffect(() => {
    const index = episodes.indexOf(selectedEpisode);
    if (index >= 0) setPage(pageOf(index));
  }, [episodes, selectedEpisode]);

  // Absent is "not recorded", never "all passed". Runs stored before the
  // field existed have no rows, and drawing them as a clean table would
  // report a measurement nobody made.
  if (!hasEpisodeOutcomes(run)) {
    // No verdicts to tabulate — but the reader still has to be able to
    // reach an episode, and the dropdown that used to do that is gone.
    // Ids and nothing else is what the dropdown offered too; here it is
    // all the run recorded.
    return (
      <>
        <p className="muted">{t("decisions.episodes.notRecorded")}</p>
        <EpisodePager
          episodes={episodes}
          page={page}
          onPage={setPage}
          selected={selectedEpisode}
          onPick={onPick}
          bare
        />
      </>
    );
  }

  const byCandidate = new Map(
    candidates.map((candidate) => [candidate.candidate_id, outcomesByEpisode(candidate)]),
  );

  // An episode nobody passed, or one somebody failed — the disagreements
  // and the losses, which is what a reader opens this table for. A
  // warehouse sweep is three hundred rows and most of them are two
  // greens.
  const interesting = episodes.filter((episode) =>
    candidates.some(
      (candidate) => byCandidate.get(candidate.candidate_id)?.get(episode)?.success === false,
    ),
  );
  const shown = failuresOnly ? interesting : episodes;
  // Clamped, not trusted: switching the filter on can leave two pages
  // where there were twelve, and page 7 of two is a blank table that
  // reads as a run with no episodes.
  const current = clampPage(page, shown.length);
  const visible = pageSlice(shown, current);

  return (
    <>
      <div className="row" style={{ alignItems: "center", gap: 12, marginBottom: 8 }}>
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={failuresOnly}
            onChange={(event) => setFailuresOnly(event.target.checked)}
          />
          <span>{t("decisions.episodes.failuresOnly")}</span>
        </label>
        {/* The count of what is hidden, always. A table that quietly
            dropped rows would read as a complete one. */}
        <span className="muted">
          {t("decisions.episodes.showing", {
            shown: String(shown.length),
            total: String(episodes.length),
          })}
        </span>
      </div>

      {shown.length === 0 ? (
        <p className="muted">{t("decisions.episodes.noFailures")}</p>
      ) : (
        <div className="table-scroll wide" style={{ marginBottom: 12 }}>
          <table>
            <thead>
              <tr>
                <th>{t("decisions.episodes.episode")}</th>
                {candidates.map((candidate) => {
                  const outcomes = byCandidate.get(candidate.candidate_id);
                  const failed = [...(outcomes?.values() ?? [])].filter(
                    (one) => !one.success,
                  ).length;
                  return (
                    <th key={candidate.candidate_id}>
                      {candidate.stack_label} · {candidate.local_controller_config}
                      <br />
                      <span className="muted">
                        {t("decisions.episodes.failedOf", {
                          failed: String(failed),
                          total: String(outcomes?.size ?? 0),
                        })}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {visible.map((episode) => {
                const outcomes = candidates.map((candidate) => byCandidate.get(candidate.candidate_id)?.get(episode));
                const differs = outcomes.length > 1 && outcomes[0]?.success !== outcomes[1]?.success;
                return (
                <tr key={episode} className={episode === selectedEpisode ? "is-selected" : ""} aria-selected={episode === selectedEpisode} tabIndex={0} onClick={() => onPick(episode)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onPick(episode); } }}>
                  {/* The number is the episode's place in the run, not
                      its place in this table — filtering must not
                      renumber them, or "#7 collided" would mean a
                      different episode with the checkbox on than off. */}
                  <td title={episode}>
                    #{episodes.indexOf(episode) + 1} ·{" "}
                    <code className="muted">{episode.slice(0, 8)}</code>
                    {differs ? <span className="episode-difference" title={t("trace.differentResults")} aria-label={t("trace.differentResults")}>!</span> : null}
                  </td>
                  {candidates.map((candidate) => (
                    <td key={candidate.candidate_id}>
                      <EpisodeCell
                        outcome={byCandidate.get(candidate.candidate_id)?.get(episode)}
                      />
                    </td>
                  ))}
                </tr>
              );})}
            </tbody>
          </table>
        </div>
      )}
      <EpisodePager
        episodes={shown}
        page={current}
        onPage={setPage}
        selected={selectedEpisode}
        onPick={onPick}
      />
    </>
  );
}

/** Five episodes a window, and a strip of tabs to move between them.
 *
 * **The strip is windowed too.** A three-hundred-episode sweep is sixty
 * pages, and sixty tabs is the problem the paging was added to solve
 * wearing a different control — so `pageWindow` caps how many are
 * offered and keeps that count constant at both ends, rather than
 * shrinking as the reader reaches the edges.
 *
 * `bare` is the fallback for a run with no recorded per-episode
 * outcomes: no table to page, just the ids, because that reader has to
 * be able to reach an episode too.
 */
function EpisodePager({
  episodes,
  page,
  onPage,
  selected,
  onPick,
  bare = false,
}: {
  episodes: string[];
  page: number;
  onPage: (page: number) => void;
  selected: string;
  onPick: (episode: string) => void;
  bare?: boolean;
}) {
  const { t } = useTranslation();
  const total = pageCount(episodes.length);
  const visible = bare ? pageSlice(episodes, page) : [];
  if (total <= 1 && !bare) return null;
  return (
    <div className="episode-pager">
      {bare ? (
        <div className="episode-pager-ids">
          {visible.map((episode) => (
            <button
              key={episode}
              type="button"
              className={`chip${episode === selected ? " primary" : ""}`}
              onClick={() => onPick(episode)}
            >
              #{episodes.indexOf(episode) + 1} · {episode.slice(0, 8)}
            </button>
          ))}
        </div>
      ) : null}
      {total > 1 ? (
        <div className="episode-pager-tabs" role="tablist" aria-label={t("decisions.episodes.pages")}>
          <button
            type="button"
            disabled={page === 0}
            aria-label={t("decisions.episodes.prevPage")}
            onClick={() => onPage(clampPage(page - 1, episodes.length))}
          >
            ‹
          </button>
          {pageWindow(page, episodes.length).map((number) => (
            <button
              key={number}
              type="button"
              role="tab"
              aria-selected={number === page}
              className={number === page ? "primary" : ""}
              onClick={() => onPage(number)}
            >
              {number + 1}
            </button>
          ))}
          <button
            type="button"
            disabled={page >= total - 1}
            aria-label={t("decisions.episodes.nextPage")}
            onClick={() => onPage(clampPage(page + 1, episodes.length))}
          >
            ›
          </button>
          <span className="muted">
            {t("decisions.episodes.pageOf", { page: String(page + 1), total: String(total) })}
          </span>
        </div>
      ) : null}
    </div>
  );
}

/** One (candidate, episode) verdict, clickable into the viewer.
 *
 * A missing outcome is drawn as "not run", not as a blank: early
 * stopping retires a candidate mid-sweep, so its later episodes were
 * never driven — a different statement from one that was driven and
 * passed, and the one that explains why this row's denominator is
 * smaller than the table's.
 */
function EpisodeCell({
  outcome,
}: {
  outcome: EpisodeOutcome | undefined;
}) {
  const { t } = useTranslation();
  if (outcome === undefined) {
    return (
      <span className="badge muted-badge" title={t("decisions.episodes.notRunNote")}>
        {t("decisions.episodes.notRun")}
      </span>
    );
  }
  const label = outcome.success
    ? t("decisions.episodes.pass")
    : t(`decisions.episodes.reason.${outcome.failure_reason}`);
  return (
    <span
      className="badge-button"
      title={t("decisions.episodes.cellNote", {
        clearance: outcome.min_clearance.toFixed(3),
        time: outcome.travel_time_s.toFixed(1),
        latency: outcome.p99_latency_ms.toFixed(2),
      })}
    >
      <span className={`badge ${outcome.success ? "ok" : "err"}`}>{label}</span>
    </span>
  );
}

/** The two things a person can do to a run, kept apart (HĐ-14).
 *
 * Below the evidence, not above it. Both acts are claims about evidence
 * the reader is supposed to have read, and putting the buttons first
 * invites the click before the reading.
 *
 * **Nothing here re-implements a rule.** The server refuses a second
 * review, a second decision, an approval by the person who started the
 * run, and any approval of a run with no card. This component disables
 * the obvious cases so the page is not lying about what will happen, but
 * it never decides — it shows what came back. A copy of the rule here
 * would be free to drift from the one that is enforced.
 */
function HumanActs({ run, onDone }: { run: DecisionRun; onDone: () => Promise<void> }) {
  const { t } = useTranslation();
  const session = useSession();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const act = async (perform: () => Promise<unknown>) => {
    setBusy(true);
    setFailed(null);
    try {
      await perform();
      setComment("");
      await onDone();
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const reviewed = run.review_state === "reviewed";
  const decided = run.config_state === "approved" || run.config_state === "rejected";
  const rankable = run.config_state !== "not_applicable";
  // Shown as a hint, never relied on: the server owns this rule and its
  // answer is the one that counts. `created_by` is null on runs filed by
  // the importer, and null is not "you".
  const ownRun = session?.user.id != null && session.user.id === run.created_by;

  if (!session) {
    return (
      <div className="panel">
        <div className="panel-head">
          <h3>{t("decisions.acts.title")}</h3>
        </div>
        <p className="muted">{t("decisions.acts.signedOut")}</p>
      </div>
    );
  }

  return (
    <div className="panel decision-gates-panel">
      <div className="panel-head">
        <h3>{t("decisions.acts.title")}</h3>
      </div>

      {failed ? <div className="error-box">{failed}</div> : null}

      <label className="field">
        <span>{t("decisions.acts.comment")}</span>
        <input
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder={t("decisions.acts.commentHint")}
          disabled={busy}
        />
      </label>

      <div className="row" style={{ marginTop: 12, alignItems: "center", gap: 12 }}>
        <button
          type="button"
          disabled={busy || reviewed}
          onClick={() => act(() => reviewRun(run.id, comment))}
        >
          {reviewed
            ? t("decisions.acts.alreadyRead", { who: run.reviewed_by ?? "?" })
            : t("decisions.acts.markRead")}
        </button>
        <span className="muted">{t("decisions.acts.reviewNote")}</span>
      </div>

      <div className="row" style={{ marginTop: 12, alignItems: "center", gap: 12 }}>
        <button
          type="button"
          className="primary"
          disabled={busy || !rankable || decided || ownRun}
          onClick={() => act(() => decideConfig(run.id, "approve", comment))}
        >
          {t("decisions.acts.approve")}
        </button>
        <button
          type="button"
          disabled={busy || !rankable || decided || ownRun}
          onClick={() => act(() => decideConfig(run.id, "reject", comment))}
        >
          {t("decisions.acts.reject")}
        </button>
        {run.config_state === "approved" ? (
          <>
            {/* A plain link, not a fetch: the endpoint returns text/plain
                and the browser keeps the filename the server chose. */}
            <a href={approvedConfigUrl(run.id)} download>
              {t("decisions.acts.download")}
            </a>
            {/* The only way out of an approval, and it exists because the
                alternative was a wall: deleting a deployment refuses
                while any of its runs is approved, and telling somebody to
                withdraw an approval they cannot withdraw is a sign on a
                locked door. Not restricted to another account the way
                approving is — undoing your own signature is not the
                conflict of interest HĐ-14 guards against. */}
            <button type="button" disabled={busy} onClick={() => act(() => withdrawConfig(run.id, comment))}>
              {busy ? t("decisions.withdraw.busy") : t("decisions.withdraw.action")}
            </button>
          </>
        ) : null}
      </div>

      {/* Why a button is off, in words. A disabled control with no
          explanation is read as a broken page. */}
      <p className="muted" style={{ marginTop: 12 }}>
        {!rankable
          ? t("decisions.acts.whyNoConfig")
          : decided
            ? `${t("decisions.acts.whyDecided", {
                state: t(`decisions.config.${run.config_state}`),
                who: run.config_decided_by ?? "?",
              })} ${run.config_state === "approved" ? t("decisions.withdraw.note") : ""}`
            : ownRun
              ? t("decisions.acts.whyOwnRun")
              : t("decisions.acts.configNote")}
      </p>
    </div>
  );
}

/** The run's id, and a button that copies it.
 *
 * **The id stays legible in every state**, so the failure case is still
 * usable: the reader selects it and copies by hand. That is not a
 * nicety — the clipboard API refuses outside a secure context, when the
 * document is not focused, and whenever the permission is denied, and a
 * button that swallowed the id to show "Copy failed" would leave them
 * with nothing.
 *
 * The decision itself is `lib/copyId`, which takes the write function as
 * a parameter so both branches can be tested without a browser.
 */
function CopyRunId({ id }: { id: string }) {
  const { t } = useTranslation();
  const [outcome, setOutcome] = useState<CopyOutcome | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleared on unmount as well as before each new timer: copying twice
  // and then leaving the page would otherwise set state on a component
  // that is gone.
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const copy = async () => {
    const result = await copyDecisionId(id, (text) =>
      // Optional-chained rather than assumed: `navigator.clipboard` is
      // absent entirely on an insecure origin, and reading `.writeText`
      // off `undefined` would throw before the helper's catch.
      navigator.clipboard?.writeText(text) ??
      Promise.reject(new Error("clipboard unavailable")),
    );
    setOutcome(result);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setOutcome(null), COPY_FEEDBACK_MS);
  };

  const stateKey = copyStateKey(outcome);
  return (
    <button
      type="button"
      className="decision-copy-id"
      data-state={outcome ?? undefined}
      aria-label={t("decisions.detail.copyId", { id })}
      onClick={() => void copy()}
    >
      <Icon name={outcome === "copied" ? "check" : "copy"} size={12} />
      <code>{id}</code>
      {/* Announced rather than only recoloured: the outcome is the whole
          point of pressing this, and a colour change says nothing to a
          screen reader. */}
      <span className="copy-state" aria-live="polite">
        {stateKey ? t(stateKey) : ""}
      </span>
    </button>
  );
}

/** One line saying how big the sample was, in the page head.
 *
 * This replaced three 26px figures — measured, requested, N_min — which
 * on an ordinary run print the same number three times at the largest
 * type on screen. A figure earns a card when it is abnormal; when it is
 * fine it earns a clause.
 *
 * Every decision here is `lib/sample`, and the reason is the repo's, not
 * taste: there is no jsdom, so a rule written inside JSX is a rule no
 * test can reach. What is left is looking up keys and rendering.
 */
function SampleLine({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const line = sampleLineFor(run);
  if (!line) return null;

  return (
    <p className="sample-line">
      {/* Bold in the markup, not in the dictionary: `translate` returns a
          plain string and React escapes it, so a `<b>` in a locale file
          would render as four visible characters. */}
      <b>{line.params.n}</b> {t("decisions.sample.line.measured")}
      <span className="sep">·</span>
      <span className={line.nMinKey === BELOW_N_MIN ? "sample-below" : undefined}>
        {t(line.nMinKey, { n: String(line.params.n), min: String(line.params.min) })}
      </span>
      {line.ranFullRequest ? (
        <>
          <span className="sep">·</span>
          {t("decisions.sample.line.full")}
        </>
      ) : null}
      {line.coveragePercent !== null ? (
        <>
          <span className="sep">·</span>
          {t("decisions.sample.line.coverage", { percent: String(line.coveragePercent) })}
        </>
      ) : null}
    </p>
  );
}

/** The one notice the sample earns, or nothing.
 *
 * Above everything, because it qualifies every number below it. A run
 * stopped at 245 of 300 is a valid, smaller comparison — but reading its
 * gate table as a 300-episode result is a different claim from the one
 * the data supports.
 *
 * **One notice, never a stack.** A run both short and interrupted used
 * to draw two boxes, and two boxes of the same shape read as two
 * problems of the same weight. Below N_min voids the numbers;
 * interrupted explains how the run got there. The combined case has its
 * own wording that says both in one box.
 */
function SampleNotice({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const sample = run.report?.sample;
  if (!sample) return null;
  const notice = noticeKey(sampleNotice(sample));
  if (!notice) return null;

  return (
    <div className={`notice ${notice.variant}`}>
      {t(notice.key, {
        n: String(sample.n_episodes),
        min: String(sample.n_min_required),
      })}
    </div>
  );
}


/** Say so when a comparison put unlike inputs side by side.
 *
 * **This is a fairness finding, not a formatting detail.** A controller
 * reading the static map and one reading only its LiDAR are answering
 * different questions, so the gap between their numbers is mostly the
 * gap between what they were given — ΔU would be measuring the
 * privilege rather than the planner, and the card would name a winner on
 * that basis.
 *
 * Every registry entry declares `lidar_only` today, so this renders
 * nothing. That is the point of adding it now: the first entry that does
 * not match would otherwise make an unlike comparison look like a like
 * one, with nothing on screen to catch it.
 *
 * It states the fact and stops. Refusing to show the run would be this
 * component overruling a comparison the platform agreed to perform, and
 * the reader is the one who knows whether the difference was deliberate.
 */

/** Hand the whole run to somebody who will not open this page.
 *
 * **Offered for every run, not only ranked ones.** Most produce no card
 * — fewer than two candidates through the gates means no ΔU (HĐ-7) — and
 * an export button that appeared only on the ranked ones would make the
 * ordinary outcome the one nobody can put in a ticket.
 *
 * Separate from `approved_config.yaml`, which is gated on approval. This
 * describes what was measured; reading it is the act approval follows
 * (HĐ-14), so gating it would invert the order.
 */
function ExportReport({ runId }: { runId: string }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<"md" | "xlsx" | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  /** One handler, because the only difference is which document the API
   *  builds — the fetch, the Blob and the failure path are identical,
   *  and two copies of them would drift on the first fix. */
  const save = (format: "md" | "xlsx") => {
    setBusy(format);
    setFailed(null);
    const download = format === "md" ? downloadDecisionReport : downloadDecisionWorkbook;
    void download(runId)
      .catch((caught) => setFailed(caught instanceof Error ? caught.message : String(caught)))
      .finally(() => setBusy(null));
  };

  return (
    <div className="decision-export">
      <button type="button" disabled={busy !== null} onClick={() => save("md")}>
        {busy === "md" ? t("decisions.export.busy") : t("decisions.export.markdown")}
      </button>
      {/* Excel beside Markdown rather than replacing it: one goes in a
          ticket, the other into a spreadsheet, and they are read by
          different people. */}
      <button type="button" disabled={busy !== null} onClick={() => save("xlsx")}>
        {busy === "xlsx" ? t("decisions.export.busy") : t("decisions.export.excel")}
      </button>
      {failed ? <span className="error-text">{failed}</span> : null}
    </div>
  );
}

function ObservationNotice({ candidates }: { candidates: RunCandidate[] }) {
  const { t } = useTranslation();
  const classes = observationClasses(candidates);
  if (classes.length < 2) return null;
  return (
    <div className="notice warn">
      {t("decisions.gates.mixedObservation", {
        classes: classes.map((name) => name ?? t("decisions.gates.observationUnknown")).join(", "),
      })}
    </div>
  );
}

function GateCell({ verdict }: { verdict: GateVerdict | undefined }) {
  const result = gateResult(verdict);
  if (result === undefined) return <span className="muted">—</span>;
  // The same badge whichever shape the verdict arrived in. A gate that
  // serialised as the bare string "pass" is not a lesser judgement than
  // one that carried evidence, and rendering it as plain text beside
  // coloured chips would say it was.
  const detail = gateEvidence(verdict)
    .map(([key, value]) => `${key}: ${value}`)
    .join("\n");
  return (
    <span className={`badge ${result === "pass" ? "ok" : "err"}`} title={detail || undefined}>
      {result}
    </span>
  );
}

/** The recommendation when there is one, and what to do when there is not. */
function Outcome({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  if (run.card) return <CardPanel run={run} />;

  const reason = noCardReason(run);
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.noCard.title")}</h3>
      </div>
      {/* The heading says "no recommendation", not "failed". Three
          situations end up here and each asks for a different next
          action; collapsing them into one message is what makes a gate
          table read like a broken run. */}
      <p>
        <strong>{t(`decisions.reason.${reason}`)}</strong>
      </p>
      <p className="muted">{t(`decisions.noCard.whatNext.${reason}`)}</p>
      {run.report?.gate_only_deployment ? (
        <div className="notice" style={{ marginTop: 12 }}>
          {run.report.gate_only_deployment}
        </div>
      ) : null}
      {run.report?.why_no_card ? (
        <details style={{ marginTop: 12 }}>
          <summary className="muted">{t("decisions.noCard.verbatim")}</summary>
          <p>{run.report.why_no_card}</p>
        </details>
      ) : null}
    </div>
  );
}

function CardPanel({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const card = run.card!;
  const evidence = card.evidence;
  const [low, high] = evidence.ci95;

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.card.title")} <Hint text={t("decisions.card.scopeNote", { scope: card.experiment_scope })} label={t("decisions.card.title")} /></h3>
        <span className="badge ok">{card.status}</span>
      </div>
      <div className="stat-grid">
        <Figure
          label={t("decisions.card.recommended")}
          value={recommendedCandidateLabel(run) ?? card.recommended.candidate_id}
        />
        <Figure label={t("decisions.card.utility")} value={card.decision_utility.toFixed(6)} />
        <Figure
          label={t("decisions.card.deltaU")}
          value={`${evidence.delta_u_vs_second >= 0 ? "+" : ""}${evidence.delta_u_vs_second.toFixed(6)}`}
        />
        <Figure
          label={t("decisions.card.ci95")}
          value={`[${low.toFixed(6)}, ${high.toFixed(6)}]`}
        />
        <Figure label={t("decisions.card.nEpisodes")} value={String(evidence.n_episodes)} />
        <Figure label={t("decisions.card.pareto")} value={card.pareto_label} />
      </div>

      {/* Null means "not measured", never "stable". HĐ-12 defines it
          that way, and rendering a blank as reassurance is how a card
          that measured nothing reads like one that measured everything. */}
      <h4>{t("decisions.card.sensitivity")}</h4>
      <div className="stat-grid">
        <Figure
          label={t("decisions.card.weightStability")}
          value={
            evidence.weight_stability_margin === null
              ? t("decisions.card.notMeasured")
              : evidence.weight_stability_margin.toFixed(3)
          }
          unknown={evidence.weight_stability_margin === null}
        />
        <Figure
          label={t("decisions.card.anchorStability")}
          value={evidence.anchor_stability ?? t("decisions.card.notMeasured")}
          unknown={evidence.anchor_stability === null}
        />
        <Figure
          label={t("decisions.card.robustness")}
          value={
            evidence.robustness_margin === null
              ? t("decisions.card.notMeasured")
              : evidence.robustness_margin.toFixed(3)
          }
          unknown={evidence.robustness_margin === null}
        />
      </div>


    </div>
  );
}

function Figure({ label, value, unknown }: { label: string; value: string; unknown?: boolean }) {
  return (
    <div className="stat-card">
      <span className="stat-card-head">{label}</span>
      <span className={`stat-card-value${unknown ? " unknown" : ""}`}>{value}</span>
    </div>
  );
}
