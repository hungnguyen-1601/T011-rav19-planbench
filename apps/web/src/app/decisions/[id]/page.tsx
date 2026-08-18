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
import { Icon } from "@/components/Icon";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  GATES,
  approvedConfigUrl,
  coverage,
  decideConfig,
  withdrawConfig,
  getDecision,
  getTrace,
  listDecisionEvents,
  noCardReason,
  reviewRun,
  gateEvidence,
  gateResult,
  hasEpisodeOutcomes,
  outcomesByEpisode,
  type DecisionRun,
  type EpisodeOutcome,
  type GateVerdict,
  type ReviewEvent,
  type RunCandidate,
  type TracePayload,
  observationClasses,
} from "@/lib/decisions";
import { downloadDecisionReport } from "@/lib/reports";
import { initialPlayback, tick, type PlaybackState } from "@/lib/playback";

export default function DecisionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useTranslation();
  const [run, setRun] = useState<DecisionRun | null>(null);
  const [events, setEvents] = useState<ReviewEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [fetched, trail] = await Promise.all([getDecision(id), listDecisionEvents(id)]);
      setRun(fetched);
      setEvents(trail);
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
        <span className="decision-page-icon"><Icon name="benchmark" size={21} /></span>
        <div><span className="decision-eyebrow">{t("decisions.detail.eyebrow")}</span><h1>{run.task_profile_id}</h1>
        <p className="muted">
          {run.experiment_scope ?? "—"} · {run.created_at.slice(0, 16).replace("T", " ")} ·{" "}
          <Link href="/decisions">{t("decisions.backToList")}</Link>
        </p></div>
        <div className="decision-detail-badges"><span className={`badge ${run.ranked ? "ok" : "muted-badge"}`}>{run.ranked ? t("decisions.filter.ranked") : t("decisions.filter.unranked")}</span>
        <ExportReport runId={run.id} />
        </div>
      </header>

      <SampleBanner run={run} />
      <GateTable run={run} />
      <CandidateComparison run={run} />
      <TracePanel run={run} />
      <Outcome run={run} />
      <HumanActs run={run} onDone={refresh} />
      <Conditions run={run} />
      <Provenance run={run} />
      <AuditTrail events={events} />
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
  return (
    <section className="panel comparison-results" aria-labelledby="comparison-results-title">
      <div className="comparison-results-head">
        <div><span className="decision-eyebrow">{t("decisions.detail.evidence")}</span><h3 id="comparison-results-title">{t("decisions.detail.results")}</h3></div>
        {run.card ? <span className="badge ok"><Icon name="trophy" size={13} />{run.card.recommended.stack}</span> : <span className="badge muted-badge">{t("decisions.noCard.title")}</span>}
      </div>
      <div className="candidate-comparison-grid">
        {candidates.slice(0, 2).map((candidate, index) => (
          <CandidateComparisonColumn key={candidate.candidate_id} candidate={candidate} side={index === 0 ? "a" : "b"} recommended={run.recommended_candidate_id === candidate.candidate_id} />
        ))}
      </div>
    </section>
  );
}

function CandidateComparisonColumn({ candidate, side, recommended }: { candidate: RunCandidate; side: "a" | "b"; recommended: boolean }) {
  const { t } = useTranslation();
  const metrics = [
    [t("decisions.gates.successRate"), `${Math.round(candidate.success_rate * 100)}%`],
    [t("decisions.gates.p99"), `${candidate.pooled_p99_latency_ms.toFixed(2)} ms`],
    [t("decisions.gates.runs"), String(candidate.n_distinct_episodes)],
    [t("decisions.gates.replans"), candidate.replan_count === undefined ? "—" : String(candidate.replan_count)],
  ];
  return (
    <article className={`candidate-result candidate-${side}${recommended ? " is-recommended" : ""}`}>
      <header className="candidate-result-head">
        <span className="candidate-result-icon"><Icon name="cpu" size={19} /></span>
        <div><small>Candidate {side.toUpperCase()}</small><h4>{candidate.stack_label}</h4><code>{candidate.local_controller_config}</code></div>
        {recommended ? <span className="badge ok"><Icon name="check" size={12} />{t("decisions.card.recommended")}</span> : null}
      </header>
      <div className="candidate-result-metrics">
        {metrics.map(([label, value]) => <div className="metric-comparison-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      <details className="candidate-gates" open>
        <summary><span>{t("decisions.gates.title")}</span><span className={`badge ${candidate.cleared_gates ? "ok" : "err"}`}>{candidate.cleared_gates ? t("decisions.gates.cleared") : candidate.blocking_gates.join(", ")}</span></summary>
        <div>{GATES.map((gate) => <div key={gate}><code>{gate}</code><GateCell verdict={candidate.gates?.[gate]} /></div>)}</div>
      </details>
    </article>
  );
}

/** Look at the evidence the gate table was computed from.
 *
 * **Directly under the gate table, and that placement is the argument.**
 * A row saying "G3: fail, 70% success" is a claim about episodes; the
 * next thing a reader should be able to do is open one of them. Putting
 * the viewer below the recommendation instead would make the trajectory
 * an illustration of a conclusion rather than the thing the conclusion
 * came from.
 *
 * Loaded on demand. A run holds thirty to three hundred episodes per
 * candidate and each is a map plus a few hundred poses, so fetching them
 * all to show one would be paying for a hundred pictures nobody asked to
 * see.
 */
function TracePanel({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates = useMemo(() => (run.report?.candidates ?? []).slice(0, 2), [run.report?.candidates]);
  const episodes = run.report?.sample?.episode_context_ids ?? [];
  const [episodeId, setEpisodeId] = useState(episodes[0] ?? "");
  const [slots, setSlots] = useState<Record<string, TraceSlot>>({});
  const [mode, setMode] = useState<"flat" | "raised">("flat");
  const [playback, setPlayback] = useState<PlaybackState>(initialPlayback);
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

  if (candidates.length === 0 || episodes.length === 0) return null;

  const chooseEpisode = (episode: string, scroll = false) => {
    setEpisodeId(episode);
    if (scroll) window.setTimeout(() => comparisonRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  };

  return (
    <div className="panel decision-sample-panel episode-comparison">
      <div className="panel-head">
        <h3>{t("trace.title")}</h3>
      </div>
      <p className="muted">{t("trace.note")}</p>
      <p className="episode-pick-note">{t("trace.pickEpisode")}</p>

      <EpisodeOutcomes
        run={run}
        selectedEpisode={episodeId}
        onPick={(episode) => chooseEpisode(episode, true)}
      />

      <div className="episode-toolbar">
        <label className="field">
          <span>{t("trace.episode")}</span>
          <select value={episodeId} onChange={(event) => chooseEpisode(event.target.value)}>
            {episodes.map((episode, index) => {
              return (
                <option key={episode} value={episode}>
                  #{index + 1} · {episode.slice(0, 8)}
                </option>
              );
            })}
          </select>
        </label>
        <div className="episode-view-toggle" role="group" aria-label={t("trace.viewMode")}>
          {(["flat", "raised"] as const).map((option) => <button key={option} type="button" className={mode === option ? "primary" : ""} aria-pressed={mode === option} onClick={() => setMode(option)}>{t(`mapView.${option}`)}</button>)}
        </div>
      </div>

      <div ref={comparisonRef} className="episode-comparison-stage" tabIndex={-1}>
        <EpisodeHeader run={run} episodeId={episodeId} candidates={candidates} />
        <SharedPlayback playback={playback} duration={duration} onChange={setPlayback} />
        <EpisodeLegend />
        <div className="episode-comparison-grid">
          {candidates.map((candidate, index) => <CandidateEpisode key={candidate.candidate_id} candidate={candidate} side={index === 0 ? "a" : "b"} episodeId={episodeId} slot={slots[candidate.candidate_id] ?? { state: "loading" }} mode={mode} playbackTime={playback.time} onRetry={() => void loadPair(episodeId)} />)}
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
  return <div className="episode-legend" aria-label={t("trace.legend.title")}>{items.map(([tone, label]) => <span key={tone}><i className={`legend-dot legend-dot--${tone}`} aria-hidden="true" />{label}</span>)}</div>;
}

function CandidateEpisode({ candidate, side, episodeId, slot, mode, playbackTime, onRetry }: { candidate: RunCandidate; side: "a" | "b"; episodeId: string; slot: TraceSlot; mode: "flat" | "raised"; playbackTime: number; onRetry: () => void }) {
  const { t } = useTranslation();
  const outcome = outcomesByEpisode(candidate).get(episodeId);
  return <article className={`episode-candidate episode-candidate--${side}`}><header><div><span>Candidate {side.toUpperCase()}</span><h4>{candidate.stack_label}</h4><code>{candidate.local_controller_config}</code></div><span className={`badge ${outcomeTone(outcome)}`}>{outcomeLabel(outcome, t)}</span></header><div className="episode-map">{slot.state === "loading" ? <div className="episode-skeleton" role="status">{t("trace.loadingCandidate")}</div> : slot.state === "ready" ? <TraceViewer trace={slot.trace} playbackTime={playbackTime} mode={mode} showControls={false} candidateSide={side} /> : slot.state === "missing" ? <div className="episode-empty" role="status">{t("trace.missing")}</div> : slot.state === "empty" ? <div className="episode-empty" role="status">{t("trace.emptyFrames")}</div> : <div className="episode-error" role="alert"><p>{t("trace.loadError")}</p><button type="button" onClick={onRetry}>{t("common.retry")}</button></div>}</div><EpisodeMetrics outcome={outcome} /></article>;
}

function EpisodeMetrics({ outcome }: { outcome: EpisodeOutcome | undefined }) {
  const { t } = useTranslation();
  const rows: [string, string, string][] = [[t("trace.result"), outcome ? outcomeLabel(outcome, t) : "—", t("trace.tip.result")], [t("metrics.travelTime"), outcome ? `${outcome.travel_time_s.toFixed(2)} s` : "—", t("trace.tip.time")], [t("metrics.minClearance"), outcome ? `${outcome.min_clearance.toFixed(3)} m` : "—", t("trace.tip.clearance")], [t("trace.p99Latency"), outcome ? `${outcome.p99_latency_ms.toFixed(2)} ms` : "—", t("trace.tip.latency")], [t("trace.collision"), outcome ? String(outcome.collision_count) : "—", t("trace.tip.collision")], [t("metrics.replanCount"), outcome?.replan_count === undefined ? "—" : String(outcome.replan_count), t("trace.tip.replan")]];
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
  const candidates = run.report?.candidates ?? [];
  const episodes = run.report?.sample?.episode_context_ids ?? [];

  // Absent is "not recorded", never "all passed". Runs stored before the
  // field existed have no rows, and drawing them as a clean table would
  // report a measurement nobody made.
  if (!hasEpisodeOutcomes(run)) {
    return <p className="muted">{t("decisions.episodes.notRecorded")}</p>;
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
              {shown.map((episode) => {
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
    </>
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

/** What was asked for, beside what was measured.
 *
 * Above everything, because it qualifies every number below it. A run
 * stopped at 245 of 300 is a valid, smaller comparison — but reading its
 * gate table as a 300-episode result is a different claim from the one
 * the data supports.
 */
function SampleBanner({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const sample = run.report?.sample;
  if (!sample) return null;
  const covered = coverage(run);
  const short = sample.n_episodes < sample.n_min_required;

  return (
    <div className="panel decision-summary">
      <div className="stat-grid">
        <Figure label={t("decisions.sample.measured")} value={String(sample.n_episodes)} />
        {sample.n_episodes_requested !== undefined ? (
          <Figure
            label={t("decisions.sample.requested")}
            value={String(sample.n_episodes_requested)}
          />
        ) : null}
        <Figure
          label={t("decisions.sample.nMin")}
          value={String(sample.n_min_required)}
          unknown={short}
        />
        {covered !== undefined && covered < 1 ? (
          <Figure label={t("decisions.sample.coverage")} value={`${Math.round(covered * 100)}%`} />
        ) : null}
      </div>
      {sample.interrupted ? (
        <div className="notice" style={{ marginTop: 12 }}>
          {t("decisions.sample.interrupted")}
        </div>
      ) : null}
      {short ? (
        <div className="notice" style={{ marginTop: 12 }}>
          {t("decisions.sample.belowNMin")}
        </div>
      ) : null}
    </div>
  );
}

/** Six gates, every candidate, in contract order — first on the page.
 *
 * `n_distinct` sits beside the run count because the pair is what a
 * collision bound's denominator actually is: a hundred replays of one
 * episode is one independent sample, and printing only the run count is
 * how this project once published a 3.0% upper bound off a single
 * episode driven a hundred times.
 */
function GateTable({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const candidates = run.report?.candidates ?? [];
  if (candidates.length === 0) return null;

  return (
    <div className="panel decision-summary decision-summary--card">
      <div className="panel-head">
        <h3>{t("decisions.gates.title")}</h3>
      </div>
      <p className="muted">{t("decisions.gates.note")}</p>
      <ObservationNotice candidates={candidates} />
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("decisions.gates.candidate")}</th>
              <th>{t("decisions.gates.observation")}</th>
              <th>{t("decisions.gates.runs")}</th>
              <th>{t("decisions.gates.successRate")}</th>
              <th>{t("decisions.gates.p99")}</th>
              <th title={t("decisions.gates.replanNote")}>{t("decisions.gates.replans")}</th>
              {GATES.map((gate) => (
                <th key={gate}>{gate}</th>
              ))}
              <th>{t("decisions.gates.verdict")}</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => (
              <CandidateRow key={candidate.candidate_id} candidate={candidate} />
            ))}
          </tbody>
        </table>
      </div>
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
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <div>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setFailed(null);
          void downloadDecisionReport(runId)
            .catch((caught) => setFailed(caught instanceof Error ? caught.message : String(caught)))
            .finally(() => setBusy(false));
        }}
      >
        {busy ? t("decisions.export.busy") : t("decisions.export.markdown")}
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

function CandidateRow({ candidate }: { candidate: RunCandidate }) {
  const { t } = useTranslation();
  return (
    <tr>
      <td>
        <strong>{candidate.stack_label}</strong>
        <br />
        <span className="muted">{candidate.local_controller_config}</span>
        <br />
        <code className="muted">{candidate.candidate_id}</code>
      </td>
      {/* What this candidate was shown. Named rather than blank when
          undeclared: a stack whose inputs nobody wrote down cannot be
          shown to match the others, and a blank cell reads as "same as
          the rest". */}
      <td className="muted">
        {candidate.local_observation_class ?? (
          <span className="badge warn" title={t("decisions.gates.observationUnknownNote")}>
            {t("decisions.gates.observationUnknown")}
          </span>
        )}
      </td>
      {/* Evidence, not a score. "Recovered on the first try" and
          "replanned forty times and timed out" are different results and
          a bare `timeout` says neither. Undeclared renders as an em dash
          rather than 0: a run recorded before replanning was priced did
          not measure this, and 0 would assert it did. */}
      <td className="muted">{candidate.replan_count ?? "—"}</td>
      <td title={t("decisions.gates.distinctNote")}>
        {candidate.n_distinct_episodes}
        {/* A retired candidate genuinely covered fewer episodes than the
            others, so every number in this row rests on a smaller
            sample. Said in the row rather than in a footnote, because
            the row is where it is read. */}
        {candidate.stopped_early ? (
          <>
            <br />
            <span
              className="badge warn"
              title={`${candidate.stopped_early.gate}: ${candidate.stopped_early.rule}`}
            >
              {t("decisions.gates.stoppedEarly", {
                run: String(candidate.stopped_early.episodes_run),
                planned: String(candidate.stopped_early.episodes_planned),
                gate: candidate.stopped_early.gate,
              })}
            </span>
          </>
        ) : null}
      </td>
      <td>{Math.round(candidate.success_rate * 100)}%</td>
      <td>{candidate.pooled_p99_latency_ms.toFixed(2)} ms</td>
      {GATES.map((gate) => (
        <td key={gate}>
          <GateCell verdict={candidate.gates?.[gate]} />
        </td>
      ))}
      <td>
        {candidate.cleared_gates ? (
          <span className="badge ok">{t("decisions.gates.cleared")}</span>
        ) : (
          <span className="badge err" title={candidate.blocking_gates.join(", ")}>
            {candidate.blocking_gates.join(", ")}
          </span>
        )}
      </td>
    </tr>
  );
}

/** One gate's verdict, with its evidence in the tooltip.
 *
 * The evidence is not decoration: "G3: fail" without the numbers cannot
 * be argued with, and a verdict nobody can argue with is one people
 * learn to route around.
 */
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
        <h3>{t("decisions.card.title")}</h3>
        <span className="badge ok">{card.status}</span>
      </div>
      <div className="stat-grid">
        <Figure label={t("decisions.card.recommended")} value={card.recommended.stack} />
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

      <p className="muted" style={{ marginTop: 12 }}>
        {t("decisions.card.scopeNote", { scope: card.experiment_scope })}
      </p>
    </div>
  );
}

/** The world this was measured in.
 *
 * `sensor_noise` is here rather than buried in provenance because
 * `episode_context_id` does not hash the amplitudes (HĐ-3.1): two runs
 * at the same seeds under different sigma are two different experiments
 * whose context ids are identical. If this panel is wrong, nothing
 * downstream can tell.
 */
function Conditions({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const identity = run.report?.identity;
  const environment = run.report?.measurement_environment;
  if (!identity) return null;
  const host = environment?.benchmark_host as Record<string, unknown> | undefined;

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.conditions.title")}</h3>
      </div>
      <div className="stat-grid">
        <Figure
          label={t("decisions.conditions.lidarSigma")}
          value={`${identity.sensor_noise?.lidar_range_sigma_m ?? 0} m`}
        />
        <Figure
          label={t("decisions.conditions.wheelSlip")}
          value={`${((identity.sensor_noise?.wheel_slip_fraction ?? 0) * 100).toFixed(1)}%`}
        />
        {host?.cpu ? <Figure label={t("decisions.conditions.cpu")} value={String(host.cpu)} /> : null}
        {host?.cores_allocated !== undefined ? (
          <Figure
            label={t("decisions.conditions.cores")}
            value={`${String(host.cores_allocated)}/${String(host.logical_cores ?? "?")}`}
          />
        ) : null}
      </div>
      {/* G4 reads wall-clock latency, so an unpinned run measured a
          machine that was also doing something else. The warning travels
          with the result rather than living in a log nobody opens. */}
      {environment?.warning ? (
        <div className="notice" style={{ marginTop: 12 }}>
          {environment.warning}
        </div>
      ) : null}
    </div>
  );
}

/** What somebody else needs to rebuild this (HĐ-13). */
function Provenance({ run }: { run: DecisionRun }) {
  const { t } = useTranslation();
  const identity = run.report?.identity;
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.provenance.title")}</h3>
      </div>
      <dl className="stat-grid">
        <dt>{t("decisions.provenance.runId")}</dt>
        <dd>
          <code>{run.id}</code>
        </dd>
        <dt>{t("decisions.provenance.contracts")}</dt>
        <dd>{run.contracts_version}</dd>
        <dt>{t("decisions.provenance.anchors")}</dt>
        <dd>{identity?.anchor_config_version ?? "—"}</dd>
        <dt>{t("decisions.provenance.gitSha")}</dt>
        <dd>
          <code>{identity?.git_sha?.slice(0, 12) ?? "—"}</code>
        </dd>
        <dt>{t("decisions.provenance.runUri")}</dt>
        <dd>
          <code>{run.report?.run_uri ?? "—"}</code>
        </dd>
        {/* A URI alone cannot say the files behind it are still the ones
            this result came from — that is what the checksum is for
            (D15), so the two are shown together or not at all. */}
        <dt>{t("decisions.provenance.checksum")}</dt>
        <dd>
          <code>{run.report?.run_checksum?.slice(0, 16) ?? "—"}</code>
        </dd>
      </dl>
      {run.report?.checks?.length ? (
        <>
          <h4>{t("decisions.provenance.checks")}</h4>
          <ul>
            {run.report.checks.map((line) => (
              <li key={line} className="muted">
                {line}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

/** Append-only, oldest first (HĐ-14). Both ends of each change, because
 *  "approved" alone does not say what it replaced. */
function AuditTrail({ events }: { events: ReviewEvent[] }) {
  const { t } = useTranslation();
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.audit.title")}</h3>
      </div>
      {events.length === 0 ? (
        <p className="muted">{t("decisions.audit.empty")}</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>{t("decisions.audit.action")}</th>
                <th>{t("decisions.audit.who")}</th>
                <th>{t("decisions.audit.change")}</th>
                <th>{t("decisions.audit.comment")}</th>
                <th>{t("decisions.audit.when")}</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.sequence}>
                  <td>{event.sequence}</td>
                  <td>{t(`decisions.audit.${event.action}`)}</td>
                  <td>{event.username}</td>
                  <td className="muted">
                    {event.previous_state} → {event.new_state}
                  </td>
                  <td>{event.comment || "—"}</td>
                  <td className="muted">{event.created_at.slice(0, 16).replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** One labelled number.
 *
 * `unknown` rather than a colour for "not measured": the word changes,
 * not just the shade, so the distinction survives a greyscale print and
 * a reader who does not know the palette.
 */
function Figure({ label, value, unknown }: { label: string; value: string; unknown?: boolean }) {
  return (
    <div className="stat-card">
      <span className="stat-card-head">{label}</span>
      <span className={`stat-card-value${unknown ? " unknown" : ""}`}>{value}</span>
    </div>
  );
}
