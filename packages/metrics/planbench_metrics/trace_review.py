"""Read one stored episode back and say why it ended that way.

Every metric this platform quotes is recomputed from the Parquet files of
HĐ-5 — one per ``(candidate, episode_context)`` — and that is the whole
point of storing them. But the reading only ever goes one way. A gate
says ``G3: fail`` at 70%, :mod:`planbench_decision.gate_advice` says
"read the failure reasons per episode before tuning", and then the trail
stops: nothing opens one of those files and tells the reader what the
robot actually did. The three failed episodes behind a 70% success rate
are 1 300 rows of ground truth that nobody has ever looked at.

This module looks. It answers one question — *why did this episode end
that way* — from the nine columns of ``TRACE_SCHEMA`` and nothing else.

**It reads the file's shape, not the deployment's rules.** A trace
carries no thresholds: not the goal tolerance, not the near-miss
clearance, not the control period, not ``v_max``. So every rule here is
either about the shape of a trajectory (the robot stopped moving nine
seconds before the file ends) or about a ratio internal to the file (it
gave up nine tenths of its widest margin). Where a judgement needs a
declared number, this module says so and hands the reader back to the
gate that owns it. A constant here pretending to be a deployment
threshold would be the HĐ-7 violation :mod:`planbench_metrics.definitions`
opens by refusing.

**Nothing here is an HĐ-6 metric.** ``compute_metrics`` is the one place
those are defined, G2 and G4 read *that*, and the numbers below are a
description of one file rather than a second opinion about it. Where a
name would collide — minimum clearance, latency percentiles — the fields
are deliberately named differently (``clearance.min_m``,
``latency.p99_ms``) and nothing computed here is scored, gated, or
compared across candidates.

**The summary is the evidence, so the summary is what citations resolve
against.** :func:`summarise_trace` produces the dict, :func:`trace_advice`
cites into it, and every number a piece of advice mentions is a key a
reader can look up. A citation into the raw dataframe would point at a
row index, which is not evidence anybody can check.

What the file cannot answer, and where those answers live instead:

- the episode's ids, the first global plan's cost and the search-node
  counters ride in the Parquet *footer*, not the columns, so a caller
  that has read them may pass the ids in as labels and nothing else;
- whether a clearance of 4 cm was a near miss is the task profile's
  ``near_miss`` threshold to say;
- whether a planner latency missed the control deadline is G4's, against
  the deployment's control period — the ratio computed here is against
  the trace's own recording cadence, which is a different claim.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from planbench_decision.advice import Advice, keep_resolvable, order
from planbench_metrics.definitions import STOP_SPEED_EPS
from planbench_simulator.trace import TRACE_EVENTS

__all__ = [
    "TRACE_REVIEW_CODES",
    "summarise_trace",
    "trace_advice",
]

#: Published so a caller can say how many rules looked. "No advice" alone
#: does not tell a reader whether anything was checked; "eleven rules, no
#: advice" does, and it is what makes a false-alarm rate computable.
TRACE_REVIEW_CODES: tuple[str, ...] = (
    "TR_CLEARANCE_COLLAPSE",
    "TR_COLLISION",
    "TR_LATENCY_OVER_SAMPLE_PERIOD",
    "TR_MARGIN_SPENT",
    "TR_NO_PATH",
    "TR_NO_TERMINAL_EVENT",
    "TR_OSCILLATING",
    "TR_REPLAN_COST",
    "TR_SPINNING_IN_PLACE",
    "TR_STALLED_BEFORE_END",
    "TR_TIMEOUT_STILL_DRIVING",
)

#: Turn rate (rad/s) below which the robot counts as not turning. The
#: sibling of ``STOP_SPEED_EPS`` and chosen for the same reason: a pure
#: zero would miss a controller idling at 1e-9 rad/s, and anything larger
#: would start calling a slow deliberate arc "still". Diagnostic only —
#: no candidate is judged on it.
TURN_RATE_EPS = 1e-3

#: Seconds of no translation, at the end of a file, after which "the
#: episode ended here" is a better description than "the episode ran to
#: time". Two seconds is forty control steps at the 20 Hz these traces
#: were recorded at; a robot pausing for a crossing obstacle is inside
#: it, a wedged one is not.
STALL_SECONDS = 2.0

#: Angular-velocity sign changes per second, while driving, above which
#: the controller is changing its mind about which way to turn more often
#: than any plan would ask it to.
#:
#: It only decides whether to *speak*, and it is deliberately not a
#: separator: on the stored `demo_hall` evaluation set one episode that
#: reached its goal crosses this rate too. That is why the advice is
#: ``material`` and reads as a symptom to look at rather than a verdict.
OSCILLATION_PER_SECOND = 1.0

#: How much of its widest margin the robot may end up having given away
#: before that is worth saying out loud. A ratio rather than a distance,
#: because a distance here would be a clearance threshold nobody declared
#: — the deployment's near-miss number lives on the task profile.
MARGIN_SPENT_FRACTION = 0.10

#: The window before the last sample that "did the clearance collapse"
#: is asked over, and the share of the margin that must have gone inside
#: it. Long enough that one noisy sample cannot answer, short enough that
#: it describes the approach rather than the episode.
COLLAPSE_WINDOW_S = 2.0
COLLAPSE_FRACTION = 0.5


# --------------------------------------------------------------------
# Reading columns. Every helper answers None rather than raising: a
# summary of a frame that is missing a column is still worth having, and
# the sections built from it stay present-and-null so citations resolve.
# --------------------------------------------------------------------


def _floats(frame: Any, name: str) -> np.ndarray | None:
    """One numeric column as a 1-D array, or None if it is unusable.

    A single non-finite value discards the whole column rather than being
    filtered out. That is the rule ``EpisodeTraceRecorder`` already
    enforces when writing — "a NaN here propagates into every aggregate
    computed from this trace" — and silently dropping the row instead
    would produce a mean over a different set of samples than the one the
    reader thinks they are looking at.
    """
    try:
        if name not in frame.columns:
            return None
        values = np.asarray(frame[name], dtype=float)
    except Exception:
        return None
    if values.ndim != 1 or values.size == 0 or not bool(np.all(np.isfinite(values))):
        return None
    return values


def _events(frame: Any) -> list[str | None] | None:
    """The event column as strings and Nones.

    Nulls arrive as ``None`` from pyarrow and as ``nan`` from pandas
    depending on how the frame was built; both mean "no event on this
    row" and are normalised to ``None`` here so a caller cannot get two
    answers for one file.
    """
    try:
        if "event" not in frame.columns:
            return None
        raw = list(frame["event"])
    except Exception:
        return None
    out: list[str | None] = []
    for item in raw:
        if item is None or (isinstance(item, float) and math.isnan(item)):
            out.append(None)
        else:
            out.append(str(item))
    return out


def _rows(frame: Any) -> int:
    try:
        return int(len(frame))
    except Exception:
        return 0


def _f(value: Any) -> float | None:
    """A finite float, or None. Keeps ``inf`` out of the summary."""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0.0:
        return None
    return numerator / denominator


# --------------------------------------------------------------------
# The summary. One dict, every key always present.
# --------------------------------------------------------------------


def summarise_trace(
    frame: Any,
    *,
    candidate_id: str = "",
    episode_context_id: str = "",
) -> dict[str, Any]:
    """Describe one episode's trace. Pure over the frame.

    ``frame`` is a pandas DataFrame of the HĐ-5 columns — ``t``, ``x``,
    ``y``, ``theta``, ``v``, ``omega``, ``clearance_m``,
    ``planner_latency_ms``, ``event``. Nothing is read from disk, so a
    test can hand this a frame it built in three lines.

    The two ids are labels, taken as arguments because they are not in
    the columns: they live in the Parquet footer, and a caller that read
    the file with :func:`~planbench_simulator.trace.read_trace` already
    has them. They are carried so advice can name its subject, and are
    used for nothing else.

    Every key of the returned dict exists for every frame, including one
    missing half its columns; unavailable numbers are present and null.
    That is deliberate — ``keep_resolvable`` tests presence, not
    truthiness, so a rule may cite "this file recorded no replan" and a
    typo in a path still fails loudly in the tests instead of looking
    like a rule that chose not to fire.
    """
    t = _floats(frame, "t")
    x = _floats(frame, "x")
    y = _floats(frame, "y")
    v = _floats(frame, "v")
    omega = _floats(frame, "omega")
    clearance = _floats(frame, "clearance_m")
    latency = _floats(frame, "planner_latency_ms")
    events = _events(frame)

    episode = _episode_section(frame, t, events, candidate_id, episode_context_id)
    period = episode["sample_period_s"]
    progress = _progress_section(t, x, y, v, omega)
    return {
        "episode": episode,
        "clearance": _clearance_section(t, clearance),
        "oscillation": _oscillation_section(t, omega, progress),
        "progress": progress,
        "replan": _replan_section(t, latency, events),
        "latency": _latency_section(latency, period),
    }


def _episode_section(
    frame: Any,
    t: np.ndarray | None,
    events: list[str | None] | None,
    candidate_id: str,
    episode_context_id: str,
) -> dict[str, Any]:
    """What ended the episode, and when.

    ``terminal_event`` is the event on the **last row**, which is where
    the recorder puts the verdict. It is kept apart from ``last_event``,
    the last event anywhere in the file: a trace whose final row is bare
    but which recorded a ``replan`` at t = 4 s ended without a verdict,
    and folding the two together would report that episode as a replan.

    ``event_column`` is why both can be null without meaning the same
    thing. A file whose event column is there and empty on the last row
    is an episode that stopped without a verdict — worth saying. A frame
    with no event column at all is a frame somebody built without one,
    and reporting that as a cut-short episode would be this module
    inventing an outcome out of a missing column.
    """
    counts = dict.fromkeys(sorted(TRACE_EVENTS), 0)
    last_event: str | None = None
    last_event_index: int | None = None
    if events is not None:
        for index, name in enumerate(events):
            if name is None:
                continue
            counts[name] = counts.get(name, 0) + 1
            last_event, last_event_index = name, index

    start = _f(t[0]) if t is not None else None
    end = _f(t[-1]) if t is not None else None
    period: float | None = None
    if t is not None and t.size > 1:
        period = _f(np.median(np.diff(t)))

    return {
        "candidate_id": candidate_id,
        "episode_context_id": episode_context_id,
        "rows": _rows(frame),
        "t_start": start,
        "t_end": end,
        "duration_s": None if start is None or end is None else end - start,
        "sample_period_s": period,
        "event_column": events is not None,
        "terminal_event": events[-1] if events else None,
        "terminal_t": end,
        "last_event": last_event,
        "last_event_t": (
            None
            if last_event_index is None or t is None or last_event_index >= t.size
            else _f(t[last_event_index])
        ),
        "event_counts": counts,
    }


def _clearance_section(t: np.ndarray | None, clearance: np.ndarray | None) -> dict[str, Any]:
    """The margin over time, and how fast the last of it went.

    ``spent_fraction`` is the minimum over the maximum rather than over
    the first sample: a robot that starts wedged in a dock has a first
    sample that is already its minimum, and anchoring there would report
    the tightest episodes as the safest ones.
    """
    section: dict[str, Any] = {
        "first_m": None,
        "last_m": None,
        "min_m": None,
        "min_t": None,
        "max_m": None,
        "mean_m": None,
        "spent_fraction": None,
        "last_is_minimum": None,
        "window_s": None,
        "window_start_m": None,
        "drop_m": None,
        "approach_rate_m_per_s": None,
        "collapse_fraction": None,
    }
    if clearance is None or clearance.size == 0:
        return section

    lowest = float(np.min(clearance))
    widest = float(np.max(clearance))
    section.update(
        {
            "first_m": _f(clearance[0]),
            "last_m": _f(clearance[-1]),
            "min_m": _f(lowest),
            "max_m": _f(widest),
            "mean_m": _f(np.mean(clearance)),
            "spent_fraction": _ratio(lowest, widest),
            "last_is_minimum": bool(float(clearance[-1]) <= lowest),
        }
    )
    if t is None or t.size != clearance.size:
        return section

    section["min_t"] = _f(t[int(np.argmin(clearance))])
    start = int(np.searchsorted(t, t[-1] - COLLAPSE_WINDOW_S, side="left"))
    span = _f(t[-1] - t[start])
    if not span:
        return section

    drop = float(clearance[start] - clearance[-1])
    section.update(
        {
            "window_s": span,
            "window_start_m": _f(clearance[start]),
            "drop_m": _f(drop),
            "approach_rate_m_per_s": _ratio(drop, span),
            "collapse_fraction": _ratio(drop, _f(clearance[start])),
        }
    )
    return section


def _progress_section(
    t: np.ndarray | None,
    x: np.ndarray | None,
    y: np.ndarray | None,
    v: np.ndarray | None,
    omega: np.ndarray | None,
) -> dict[str, Any]:
    """Whether the robot was getting anywhere, and when it stopped.

    ``stalled_s`` is measured from the **last** sample that moved, not
    from the first that did not: a controller that pauses for a crossing
    obstacle and drives on has not stalled, and only the unbroken tail of
    stillness at the end of the file describes an episode that was over
    before its last row was written.
    """
    section: dict[str, Any] = {
        "path_length_m": None,
        "net_displacement_m": None,
        "straightness": None,
        "mean_speed_m_per_s": None,
        "max_speed_m_per_s": None,
        "moving_fraction": None,
        "ever_moved": None,
        "last_motion_t": None,
        "stalled_s": None,
        "stalled_fraction": None,
        "heading_swept_after_stall_rad": None,
        "turn_rate_after_stall_rad_per_s": None,
    }
    duration: float | None = None
    if t is not None and t.size > 0:
        duration = _f(t[-1] - t[0])

    if x is not None and y is not None and x.size == y.size and x.size > 1:
        steps = np.hypot(np.diff(x), np.diff(y))
        path = float(np.sum(steps))
        net = float(math.dist((x[0], y[0]), (x[-1], y[-1])))
        section["path_length_m"] = _f(path)
        section["net_displacement_m"] = _f(net)
        section["straightness"] = _ratio(net, path)
        section["mean_speed_m_per_s"] = _ratio(path, duration)

    if v is None or t is None or v.size != t.size or v.size == 0:
        return section

    speed = np.abs(v)
    moving = speed > STOP_SPEED_EPS
    section["max_speed_m_per_s"] = _f(np.max(speed))
    section["moving_fraction"] = float(np.count_nonzero(moving)) / float(moving.size)
    section["ever_moved"] = bool(moving.any())

    last = int(np.max(np.nonzero(moving)[0])) if moving.any() else 0
    stalled = _f(t[-1] - t[last])
    section["last_motion_t"] = _f(t[last])
    section["stalled_s"] = stalled
    section["stalled_fraction"] = _ratio(stalled, duration)

    if omega is not None and omega.size == t.size and last < t.size - 1:
        swept = float(np.sum(np.abs(omega[last + 1 :]) * np.diff(t[last:])))
        section["heading_swept_after_stall_rad"] = _f(swept)
        section["turn_rate_after_stall_rad_per_s"] = _ratio(swept, stalled)
    return section


def _oscillation_section(
    t: np.ndarray | None, omega: np.ndarray | None, progress: Mapping[str, Any]
) -> dict[str, Any]:
    """How often the commanded turn reversed, per second.

    Counted twice, over the whole file and over the driving phase alone,
    because the two answer different questions. A robot that fought its
    way to a wedge and then span steadily for ten seconds has its
    reversal rate halved by the still tail, which describes the stall,
    not the controller. ``per_second_driving`` is the one the rule reads.
    """
    section: dict[str, Any] = {
        "turn_rate_eps_rad_per_s": TURN_RATE_EPS,
        "sign_changes": None,
        "per_second": None,
        "driving_duration_s": None,
        "sign_changes_driving": None,
        "per_second_driving": None,
    }
    if omega is None or t is None or omega.size != t.size or omega.size == 0:
        return section

    duration = _f(t[-1] - t[0])
    section["sign_changes"] = _reversals(omega)
    section["per_second"] = _ratio(section["sign_changes"], duration)

    stop = progress.get("last_motion_t")
    if not isinstance(stop, (int, float)):
        return section
    driving = t <= stop
    section["driving_duration_s"] = _f(stop - t[0])
    section["sign_changes_driving"] = _reversals(omega[driving])
    section["per_second_driving"] = _ratio(
        section["sign_changes_driving"], section["driving_duration_s"]
    )
    return section


def _reversals(omega: np.ndarray) -> int:
    """Sign changes of the commanded turn rate, ignoring the deadband.

    Samples inside the deadband are dropped rather than counted as a
    sign, so a robot that turns left, drives straight, and turns left
    again scores zero reversals — it never changed its mind, it just
    stopped asking.
    """
    signs = np.sign(np.where(np.abs(omega) <= TURN_RATE_EPS, 0.0, omega))
    signs = signs[signs != 0]
    if signs.size < 2:
        return 0
    return int(np.count_nonzero(np.diff(signs) != 0))


def _replan_section(
    t: np.ndarray | None, latency: np.ndarray | None, events: list[str | None] | None
) -> dict[str, Any]:
    """How often a new global path was asked for, and what it cost.

    A replan leaves no signature in the trajectory — it is recoverable
    only from the event column — and the step it happens on carries the
    global planner's time in ``planner_latency_ms``. So the cost is the
    difference between those rows and the median of the rest, which is
    the number G4 pools into p99 along with everything else.
    """
    section: dict[str, Any] = {
        "count": 0,
        "times": [],
        "latency_at_replan_ms": [],
        "max_at_replan_ms": None,
        "mean_at_replan_ms": None,
        "median_elsewhere_ms": None,
        "extra_ms": None,
    }
    if events is None:
        section["count"] = None
        return section

    where = [index for index, name in enumerate(events) if name == "replan"]
    section["count"] = len(where)
    if t is not None and t.size == len(events):
        section["times"] = [_f(t[index]) for index in where]
    if latency is None or latency.size != len(events):
        return section

    mask = np.zeros(latency.size, dtype=bool)
    mask[where] = True
    at = latency[mask]
    elsewhere = latency[~mask]
    if at.size:
        section["latency_at_replan_ms"] = [_f(value) for value in at]
        section["max_at_replan_ms"] = _f(np.max(at))
        section["mean_at_replan_ms"] = _f(np.mean(at))
    if elsewhere.size:
        section["median_elsewhere_ms"] = _f(np.median(elsewhere))
    if section["max_at_replan_ms"] is not None and section["median_elsewhere_ms"] is not None:
        section["extra_ms"] = section["max_at_replan_ms"] - section["median_elsewhere_ms"]
    return section


def _latency_section(latency: np.ndarray | None, period_s: float | None) -> dict[str, Any]:
    """Planner latency, and how it sits against the recording cadence.

    The comparison is against the trace's own median sample period — the
    interval between the control steps this file recorded — and **not**
    against the deployment's control period, which is on the task profile
    and is G4's to judge. Calling the ratio a deadline miss here would be
    a seventh gate written against a number nobody declared.
    """
    period_ms = None if period_s is None else period_s * 1000.0
    section: dict[str, Any] = {
        "p50_ms": None,
        "p95_ms": None,
        "p99_ms": None,
        "max_ms": None,
        "mean_ms": None,
        "sample_period_ms": period_ms,
        "p99_over_sample_period": None,
        "steps_over_sample_period": None,
    }
    if latency is None or latency.size == 0:
        return section

    p50, p95, p99 = (float(value) for value in np.percentile(latency, [50, 95, 99]))
    section.update(
        {
            "p50_ms": _f(p50),
            "p95_ms": _f(p95),
            "p99_ms": _f(p99),
            "max_ms": _f(np.max(latency)),
            "mean_ms": _f(np.mean(latency)),
        }
    )
    if period_ms:
        section["p99_over_sample_period"] = _ratio(p99, period_ms)
        section["steps_over_sample_period"] = int(np.count_nonzero(latency > period_ms))
    return section


# --------------------------------------------------------------------
# The advice.
# --------------------------------------------------------------------


def trace_advice(summary: Mapping[str, Any]) -> tuple[Advice, ...]:
    """What this episode says, as advice. Never raises.

    An empty tuple for a clean episode is a result rather than a silence:
    with ``len(TRACE_REVIEW_CODES)`` beside it, it says eleven rules read
    the file and none of them objected.
    """
    try:
        found = tuple(_rules(summary))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(summary)))


def _subject(episode: Mapping[str, Any]) -> str:
    candidate = str(episode.get("candidate_id") or "")
    context = str(episode.get("episode_context_id") or "")
    if candidate and context:
        return f"{candidate}/{context}"
    return candidate or context


def _rules(summary: Mapping[str, Any]) -> Any:
    episode = dict(summary.get("episode") or {})
    clearance = dict(summary.get("clearance") or {})
    oscillation = dict(summary.get("oscillation") or {})
    progress = dict(summary.get("progress") or {})
    replan = dict(summary.get("replan") or {})
    latency = dict(summary.get("latency") or {})
    subject = _subject(episode)

    yield from _outcome_rules(episode, clearance, subject)
    yield from _motion_rules(episode, progress, oscillation, subject)
    yield from _clearance_rules(clearance, subject)
    yield from _cost_rules(replan, latency, subject)


def _num(value: Any) -> float | None:
    """The value when it is a real number, else None. ``bool`` is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _outcome_rules(episode: Mapping[str, Any], clearance: Mapping[str, Any], subject: str) -> Any:
    counts = dict(episode.get("event_counts") or {})
    terminal = episode.get("terminal_event")
    at = episode.get("terminal_t")
    when = f" at t = {at:.2f} s" if isinstance(at, (int, float)) else ""

    if _num(counts.get("collision")):
        closest = clearance.get("min_m")
        rate = clearance.get("approach_rate_m_per_s")
        ground = "the trace records a collision event"
        if isinstance(closest, (int, float)):
            ground += f"; clearance reached {closest:.3f} m"
        if isinstance(rate, (int, float)) and rate > 0:
            ground += f", closing at {rate:.3f} m/s over the final window"
        yield Advice(
            code="TR_COLLISION",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim=f"the robot hit something{when}",
            ground=ground,
            field_path="episode.event_counts.collision",
            do=(
                "read clearance.min_t and the speed the robot carried into it; a margin "
                "that fell smoothly is a tuning problem, one that fell in a single step "
                "is the controller reacting to something it saw late"
            ),
            do_not=(
                "retune until this one episode survives — G2 is a zero over the whole "
                "evaluation set, and an episode fixed in isolation is one sample, not a fix"
            ),
        )

    if _num(counts.get("no_path")):
        yield Advice(
            code="TR_NO_PATH",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim=f"the global planner returned no path{when}",
            ground=(
                "with no path there is nothing for the controller to follow, so every "
                "clearance, latency and efficiency number in this file describes a robot "
                "that was never given a route"
            ),
            field_path="episode.event_counts.no_path",
            do=(
                "check the mission fits the map at this robot radius before touching the "
                "controller — this is geometry, and G1 is where it is decided"
            ),
            do_not=(
                "pool this episode's latency or clearance in with the others; it measures "
                "a planner failing, not a stack driving"
            ),
        )

    if episode.get("rows") and episode.get("event_column") and terminal is None:
        last = episode.get("last_event")
        yield Advice(
            code="TR_NO_TERMINAL_EVENT",
            kind="diagnosis",
            severity="material",
            subject=subject,
            claim="this episode's last row carries no verdict",
            ground=(
                "the recorder writes the terminal event on the final sample; the last event "
                f"in this file is {last!r}, so the run stopped without one — a crash, a "
                "cancellation, or a file written by something other than a finished episode"
            ),
            field_path="episode.terminal_event",
            do="find out what stopped the run before reading anything else out of this file",
            do_not=(
                "count it as a failure of the candidate — an episode that never finished is "
                "a hole in the paired set, and its partner must be dropped or re-run with it"
            ),
        )


def _motion_rules(
    episode: Mapping[str, Any],
    progress: Mapping[str, Any],
    oscillation: Mapping[str, Any],
    subject: str,
) -> Any:
    terminal = episode.get("terminal_event")
    reached = terminal == "goal_reached"
    stalled = _num(progress.get("stalled_s"))
    stopped_at = progress.get("last_motion_t")

    if not reached and stalled is not None and stalled >= STALL_SECONDS:
        share = progress.get("stalled_fraction")
        part = f" ({share:.0%} of the file)" if isinstance(share, (int, float)) else ""
        moment = f" at t = {stopped_at:.2f} s" if isinstance(stopped_at, (int, float)) else ""
        yield Advice(
            code="TR_STALLED_BEFORE_END",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim=f"the robot stopped moving{moment} and never started again",
            ground=(
                f"the last {stalled:.2f} s of the trace{part} record no translation at all, "
                f"so the episode was decided there and the rest is the clock running out"
            ),
            field_path="progress.stalled_s",
            do=(
                "look at the clearance and the commanded velocity at the moment motion "
                "stopped; that sample, not the terminal row, is where this episode ended"
            ),
            do_not=(
                "raise the episode time limit so the run finishes — a robot that stopped "
                f"{stalled:.2f} s before the file ends was not short of time"
            ),
        )

        swept = _num(progress.get("heading_swept_after_stall_rad"))
        rate = _num(progress.get("turn_rate_after_stall_rad_per_s"))
        if swept is not None and rate is not None and rate > TURN_RATE_EPS:
            yield Advice(
                code="TR_SPINNING_IN_PLACE",
                kind="diagnosis",
                severity="material",
                subject=subject,
                claim=f"it kept turning after it stopped, sweeping {swept:.2f} rad on the spot",
                ground=(
                    f"a mean {rate:.3f} rad/s of commanded rotation with zero translation: "
                    "the controller was still issuing commands and still believed it was "
                    "doing something, which is a different defect from a robot that froze"
                ),
                field_path="progress.heading_swept_after_stall_rad",
                do=(
                    "check whether the controller can reach any admissible forward velocity "
                    "from that pose — an in-place spin is usually every translating sample "
                    "being scored as a collision"
                ),
                do_not=(
                    "read the moving heading as progress; the robot swept "
                    f"{swept:.2f} rad without covering a millimetre"
                ),
            )

    # `stalled is not None` is required rather than defaulted: without a
    # velocity column there is no evidence the robot was moving, and
    # "still driving" would then be a claim made out of a missing column.
    if terminal == "timeout" and stalled is not None and stalled < STALL_SECONDS:
        speed = progress.get("mean_speed_m_per_s")
        pace = f" at a mean {speed:.2f} m/s" if isinstance(speed, (int, float)) else ""
        yield Advice(
            code="TR_TIMEOUT_STILL_DRIVING",
            kind="diagnosis",
            severity="material",
            subject=subject,
            claim=f"the clock ran out while the robot was still driving{pace}",
            ground=(
                "there is no stall at the end of this file, so nothing was wedged; the "
                "route simply took longer than the episode was allowed"
            ),
            field_path="episode.terminal_event",
            do=(
                "compare the distance covered against the reference route before tuning: a "
                "robot that drove twice the reference took a detour, one that drove it once "
                "and slowly is speed-limited"
            ),
            do_not=(
                "raise the time limit until it passes — t_ideal_s is computed from the "
                "reference route and v_max, so a longer limit changes the deployment "
                "without changing what the stack can do"
            ),
        )

    driving = _num(oscillation.get("per_second_driving"))
    changes = oscillation.get("sign_changes_driving")
    if driving is not None and driving >= OSCILLATION_PER_SECOND:
        yield Advice(
            code="TR_OSCILLATING",
            kind="diagnosis",
            severity="material",
            subject=subject,
            claim=f"the commanded turn reversed {changes} times while driving, {driving:.2f}/s",
            ground=(
                "a reversal is the controller choosing the opposite side to the one it chose "
                "a moment earlier; at this rate that is chatter rather than a plan being "
                "followed, and it costs travel time and smoothness"
            ),
            field_path="oscillation.per_second_driving",
            do=(
                "read omega against clearance around those reversals — a controller flipping "
                "between two equally scored escapes looks exactly like this"
            ),
            do_not=(
                "cap the angular velocity until the reversals stop and call it fixed; a "
                "controller that cannot turn fast enough to reverse has not stopped changing "
                "its mind, it has only stopped being able to act on it"
            ),
        )


def _clearance_rules(clearance: Mapping[str, Any], subject: str) -> Any:
    collapse = _num(clearance.get("collapse_fraction"))
    rate = _num(clearance.get("approach_rate_m_per_s"))
    if (
        clearance.get("last_is_minimum")
        and collapse is not None
        and collapse >= COLLAPSE_FRACTION
        and rate is not None
        and rate > 0
    ):
        started = clearance.get("window_start_m")
        ended = clearance.get("last_m")
        window = clearance.get("window_s")
        yield Advice(
            code="TR_CLEARANCE_COLLAPSE",
            kind="diagnosis",
            severity="blocking",
            subject=subject,
            claim="the episode ended at its tightest point, and got there fast",
            ground=(
                f"clearance fell from {started:.3f} m to {ended:.3f} m over the last "
                f"{window:.2f} s — {collapse:.0%} of the margin at {rate:.3f} m/s — so the "
                "robot drove into this rather than being caught in it"
            ),
            field_path="clearance.approach_rate_m_per_s",
            do=(
                "check what the controller was scoring in that window; a margin given away "
                "this fast is a horizon too short to see the obstacle in time"
            ),
            do_not=(
                "widen the inflation radius until this episode clears — the margin is "
                "already being spent faster than the planner can replace it, and a wider "
                "one moves the same collapse somewhere else"
            ),
        )

    spent = _num(clearance.get("spent_fraction"))
    if spent is not None and spent <= MARGIN_SPENT_FRACTION:
        lowest = clearance.get("min_m")
        widest = clearance.get("max_m")
        at = clearance.get("min_t")
        moment = f" at t = {at:.2f} s" if isinstance(at, (int, float)) else ""
        yield Advice(
            code="TR_MARGIN_SPENT",
            kind="diagnosis",
            severity="disclosure",
            subject=subject,
            claim=(
                f"the robot passed within {lowest:.3f} m of something{moment}, having had "
                f"{widest:.3f} m at its widest"
            ),
            ground=(
                f"{spent:.0%} of its widest margin was left at the closest point; that is a "
                "fact about this trajectory, not a verdict — whether it is close enough to "
                "matter is the deployment's near-miss clearance to say, and this file does "
                "not carry it"
            ),
            field_path="clearance.min_m",
            do=(
                "put this number beside the task profile's near-miss clearance, and read "
                "near_miss_rate from the metrics rather than counting samples here"
            ),
            do_not=(
                "report it as a near miss on the strength of this file; the threshold that "
                "would make it one is declared on the deployment, not measured in the trace"
            ),
        )


def _cost_rules(replan: Mapping[str, Any], latency: Mapping[str, Any], subject: str) -> Any:
    count = _num(replan.get("count"))
    if count:
        extra = replan.get("extra_ms")
        baseline = replan.get("median_elsewhere_ms")
        cost = (
            f"the worst of them took {extra:.1f} ms more than the {baseline:.1f} ms median step"
            if isinstance(extra, (int, float)) and isinstance(baseline, (int, float))
            else "each one carries the global planner's time on its own control step"
        )
        yield Advice(
            code="TR_REPLAN_COST",
            kind="diagnosis",
            severity="material",
            subject=subject,
            claim=f"the stack asked for a new global path {int(count)} time(s) in this episode",
            ground=(
                f"{cost}; those rows go into the same latency sample as every other step, "
                "which is how a replan is charged for rather than scored separately"
            ),
            field_path="replan.count",
            do=(
                "read the times against the trajectory: recovering on the first replan and "
                "replanning repeatedly in one spot are opposite outcomes with one count"
            ),
            do_not=(
                "drop the replan steps from the latency sample to make p99 fit — the robot "
                "really did wait that long for a command"
            ),
        )

    ratio = _num(latency.get("p99_over_sample_period"))
    if ratio is not None and ratio > 1.0:
        p99 = latency.get("p99_ms")
        period = latency.get("sample_period_ms")
        over = latency.get("steps_over_sample_period")
        yield Advice(
            code="TR_LATENCY_OVER_SAMPLE_PERIOD",
            kind="diagnosis",
            severity="material",
            subject=subject,
            claim=(f"planning took longer than the interval it was sampled at on {over} step(s)"),
            ground=(
                f"p99 of {p99:.1f} ms against a {period:.1f} ms median sample period. This "
                "is the trace's own recording cadence, not the deployment's control period "
                "— G4 owns that comparison — but a planner slower than the steps it is "
                "recorded on is late by any definition"
            ),
            field_path="latency.p99_over_sample_period",
            do=(
                "reduce the search before reading G4: fewer velocity samples or a shorter "
                "horizon, then re-measure on a run pinned to dedicated cores"
            ),
            do_not=(
                "record the trace at a coarser interval so the ratio falls below one; the "
                "planner takes as long as it takes, and a sparser file only hides it"
            ),
        )
