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

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  GATES,
  approvedConfigUrl,
  coverage,
  decideConfig,
  getDecision,
  listDecisionEvents,
  noCardReason,
  reviewRun,
  gateEvidence,
  gateResult,
  type DecisionRun,
  type GateVerdict,
  type ReviewEvent,
  type RunCandidate,
} from "@/lib/decisions";

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
    <section>
      <div className="page-head">
        <h1>{run.task_profile_id}</h1>
        <p className="muted">
          {run.experiment_scope ?? "—"} · {run.created_at.slice(0, 16).replace("T", " ")} ·{" "}
          <Link href="/decisions">{t("decisions.backToList")}</Link>
        </p>
      </div>

      <SampleBanner run={run} />
      <GateTable run={run} />
      <Outcome run={run} />
      <HumanActs run={run} onDone={refresh} />
      <Conditions run={run} />
      <Provenance run={run} />
      <AuditTrail events={events} />
    </section>
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
    <div className="panel">
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
          // A plain link, not a fetch: the endpoint returns text/plain
          // and the browser keeps the filename the server chose.
          <a href={approvedConfigUrl(run.id)} download>
            {t("decisions.acts.download")}
          </a>
        ) : null}
      </div>

      {/* Why a button is off, in words. A disabled control with no
          explanation is read as a broken page. */}
      <p className="muted" style={{ marginTop: 12 }}>
        {!rankable
          ? t("decisions.acts.whyNoConfig")
          : decided
            ? t("decisions.acts.whyDecided", {
                state: t(`decisions.config.${run.config_state}`),
                who: run.config_decided_by ?? "?",
              })
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
    <div className="panel">
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
    <div className="panel">
      <div className="panel-head">
        <h3>{t("decisions.gates.title")}</h3>
      </div>
      <p className="muted">{t("decisions.gates.note")}</p>
      <div className="table-scroll wide">
        <table>
          <thead>
            <tr>
              <th>{t("decisions.gates.candidate")}</th>
              <th>{t("decisions.gates.runs")}</th>
              <th>{t("decisions.gates.successRate")}</th>
              <th>{t("decisions.gates.p99")}</th>
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
