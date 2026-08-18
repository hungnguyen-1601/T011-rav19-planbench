"""The end-to-end deadline screen (H10), and the protocol it obeys.

G4 has always asked one question — *is the controller fast enough for
this robot* — and answered it from ``planner_latency_ms``, the algorithm's
own compute. That number is still right for what it measures, and it is
no longer the whole tick: a plugin in the subprocess lane also pays
transport, and a run with a provider graph also pays for producing its
channels (§5.9). A candidate whose algorithm computes in 4 ms and whose
tick takes 60 ms misses every deadline while passing a gate that only
looked at the 4.

So G4 gains a **second screen** rather than a replacement. The legacy one
keeps its meaning and its history; the new one reads
``end_to_end_control_ms``, which is host-measured and therefore the only
layer a gate may read (§5.9 rule 6).

**The protocol is a committed file, not arguments.** Warm-up count,
repetitions, guard band, resample unit and confidence level all come from
``configs/latency-screening-v*.yaml``, which was committed before any
measurement existed. A screen whose parameters are passed in at call time
is a screen whose parameters can be chosen after seeing the data.

**The resample unit is the part that had to be fixed before measuring.**
v1 said "bootstrap" and did not say of what. Ticks inside one episode are
not independent — same map, same seed, same trajectory, same caches — so
resampling ticks would report an interval narrower than the truth by
roughly the square root of the ticks per episode, and a gate reading it
would pass on a confidence nobody has. v2 resamples **episodes** and
recomputes the pooled percentile inside each resample.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field

# No import of ``planbench_metrics.statistics`` here on purpose. Its
# ``bootstrap_ci`` resamples the sequence it is handed, so using it would
# mean handing it ticks — a per-tick interval wearing an episode-level
# name. ``_episode_bootstrap`` below resamples episodes instead, and
# keeping the dependency out also keeps this gate layer from pulling the
# simulator in through the metrics package.


#: Where the committed protocols live.
PROTOCOL_DIR = Path("configs")

#: What the screen concluded. ``not_measured`` is a statement about the
#: *host*, not about the candidate: the machine moved under the
#: measurement, so nothing was learned either way.
LatencyVerdict = Literal["pass", "fail", "inconclusive", "not_measured"]


class ProtocolError(ValueError):
    """The screening protocol cannot be used as written."""


class LatencyProtocol(BaseModel):
    """One committed screening protocol, validated on load."""

    model_config = ConfigDict(frozen=True, extra="allow")

    version: str = Field(min_length=1)
    warmup_episodes: int = Field(ge=0)
    repetitions: int = Field(gt=0)
    guard_band_ms: float = Field(ge=0.0)
    confidence_level: float = Field(gt=0.0, lt=1.0)
    bootstrap_resamples: int = Field(gt=0)
    bootstrap_seed: int = 0
    sentinel_drift_max_fraction: float = Field(gt=0.0)
    min_episodes_for_verdict: int = Field(gt=0)
    min_ticks_for_percentile: int = Field(gt=0)
    #: **No default.** Defaulting this to ``episode`` would let v1 — which
    #: never said what it resampled — be used under an assumption it does
    #: not make, which is precisely the ambiguity v2 exists to remove. A
    #: protocol that does not say is refused rather than interpreted.
    resample_unit: str | None = None
    worker_count: int = 1
    blas_threads: int = 1
    core_affinity: tuple[int, ...] = ()

    @classmethod
    def load(cls, path: Path | str) -> LatencyProtocol:
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ProtocolError(f"{path} is not a protocol document")
        # **Checked on the raw document, before field validation.** v1 is
        # missing several fields v2 added, so validating first would
        # answer "2 validation errors" — true, and not the reason anybody
        # needs. The substantive reason is that it never said what it
        # resamples, and a refusal should lead with the defect rather
        # than with its consequences.
        if "resample_unit" not in data:
            raise ProtocolError(
                f"{path} does not say what it resamples. 'bootstrap_ci' names a method and "
                "not a unit, and the two answers differ by more than the guard band — so "
                "a verdict computed under it would be confident for a reason nobody chose"
            )
        try:
            protocol = cls.model_validate(data)
        except Exception as error:  # noqa: BLE001 - any malformed protocol is one refusal
            raise ProtocolError(f"{path} is not a usable screening protocol: {error}") from error
        if protocol.resample_unit != "episode":
            # The one parameter this module refuses to be flexible about.
            # Per-tick resampling produces an interval that is narrow for
            # a reason unrelated to the measurement, and a verdict read
            # from it is confident about nothing.
            raise ProtocolError(
                f"{path} asks for resample_unit={protocol.resample_unit!r}; this screen "
                "resamples episodes, because ticks within one episode share a map, a "
                "seed and a trajectory and are not independent draws"
            )
        return protocol


class HostConditions(BaseModel):
    """What the machine was doing while it was measured.

    Recorded rather than assumed: a verdict produced on a laptop with
    four other builds running is not comparable with one produced on a
    quiet host, and nothing in the numbers themselves says which
    happened.
    """

    model_config = ConfigDict(frozen=True)

    worker_count: int = 1
    blas_threads: int = 1
    core_affinity: tuple[int, ...] = ()
    host_description: str = ""


class SentinelReading(BaseModel):
    """The reference candidate's own p99, before and after the session."""

    model_config = ConfigDict(frozen=True)

    before_ms: float = Field(ge=0.0)
    after_ms: float = Field(ge=0.0)

    @property
    def drift_fraction(self) -> float:
        """Relative movement, against the *larger* of the two.

        Against the larger rather than the first: dividing by whichever
        happened to be measured first makes the same physical drift look
        different depending on which direction the host moved.
        """
        larger = max(self.before_ms, self.after_ms)
        if larger <= 0.0:
            return 0.0
        return abs(self.after_ms - self.before_ms) / larger


class LatencyVerdictRecord(BaseModel):
    """Everything needed to re-derive this verdict, or to distrust it."""

    model_config = ConfigDict(frozen=True)

    verdict: LatencyVerdict
    reason: str = ""
    protocol_version: str
    #: **The number that decides how wide the interval is.** Resampling
    #: episodes means the effective sample size is the episode count, not
    #: the tick count — so it is recorded next to the interval rather
    #: than left to be inferred from a CI that looks narrow.
    episodes: int = Field(ge=0)
    ticks: int = Field(ge=0)
    p99_ms: float | None = None
    ci_lower_ms: float | None = None
    ci_upper_ms: float | None = None
    deadline_ms: float = Field(gt=0.0)
    guard_band_ms: float = Field(ge=0.0)
    sentinel: SentinelReading | None = None
    host: HostConditions = Field(default_factory=HostConditions)
    git_sha: str = ""
    candidate_id: str = ""
    runtime_profile: dict[str, Any] = Field(default_factory=dict)
    #: Filled only when a session was re-run, with the reason. Retrying
    #: until the number is agreeable is what this field makes visible.
    retry_reason: str = ""


def pooled_percentile(episodes: Sequence[Sequence[float]], *, percentile: float = 99.0) -> float:
    """The percentile over every tick of the given episodes, pooled.

    Not the mean of per-episode percentiles: a percentile of percentiles
    is a statistic of nothing, and the same argument already governs
    ``pooled_p99_latency_ms``.
    """
    ticks = [value for episode in episodes for value in episode]
    if not ticks:
        return 0.0
    return float(np.percentile(np.asarray(ticks, dtype=float), percentile))


def screen(
    episodes: Sequence[Sequence[float]],
    *,
    protocol: LatencyProtocol,
    deadline_ms: float,
    sentinel: SentinelReading | None = None,
    host: HostConditions | None = None,
    candidate_id: str = "",
    git_sha: str = "",
    runtime_profile: dict[str, Any] | None = None,
    retry_reason: str = "",
) -> LatencyVerdictRecord:
    """Decide whether the whole control tick fits the deployment's period.

    ``episodes`` is one sequence of per-tick ``end_to_end_control_ms``
    per episode — kept nested rather than flattened, because the nesting
    *is* the resampling unit and flattening it here would silently make
    the interval a per-tick one again.
    """
    host = host or HostConditions(
        worker_count=protocol.worker_count,
        blas_threads=protocol.blas_threads,
        core_affinity=protocol.core_affinity,
    )
    tick_count = sum(len(episode) for episode in episodes)
    base = {
        "protocol_version": protocol.version,
        "episodes": len(episodes),
        "ticks": tick_count,
        "deadline_ms": deadline_ms,
        "guard_band_ms": protocol.guard_band_ms,
        "sentinel": sentinel,
        "host": host,
        "candidate_id": candidate_id,
        "git_sha": git_sha,
        "runtime_profile": dict(runtime_profile or {}),
        "retry_reason": retry_reason,
    }

    if sentinel is not None and sentinel.drift_fraction > protocol.sentinel_drift_max_fraction:
        # The host moved under the measurement. Not a statement about the
        # candidate, and re-running until the sentinel behaves is exactly
        # what ``retry_reason`` exists to make visible.
        return LatencyVerdictRecord(
            verdict="not_measured",
            reason=(
                f"sentinel drifted {sentinel.drift_fraction:.1%} between the start and "
                f"end of the session, over the {protocol.sentinel_drift_max_fraction:.0%} "
                "the protocol admits; the host was not quiet and nothing was learned "
                "about this candidate"
            ),
            **base,
        )

    if len(episodes) < protocol.min_episodes_for_verdict:
        return LatencyVerdictRecord(
            verdict="inconclusive",
            reason=(
                f"{len(episodes)} episodes is below the protocol's floor of "
                f"{protocol.min_episodes_for_verdict}. An interval built from a handful "
                "of episodes can be narrow and still say nothing about the next one"
            ),
            **base,
        )
    if tick_count < protocol.min_ticks_for_percentile:
        return LatencyVerdictRecord(
            verdict="inconclusive",
            reason=(
                f"{tick_count} control steps is below the protocol's floor of "
                f"{protocol.min_ticks_for_percentile}; a 99th percentile over that many "
                "points is a tail statistic of a handful of samples rather than a p99"
            ),
            **base,
        )

    observed = pooled_percentile(episodes)
    lower, upper = _episode_bootstrap(episodes, protocol)

    if upper < deadline_ms - protocol.guard_band_ms:
        verdict: LatencyVerdict = "pass"
        reason = ""
    elif lower > deadline_ms + protocol.guard_band_ms:
        verdict = "fail"
        reason = (
            f"the whole tick's p99 is above {deadline_ms:.1f} ms by more than the "
            f"{protocol.guard_band_ms:.1f} ms guard band, with 95% confidence"
        )
    else:
        verdict = "inconclusive"
        reason = (
            f"the interval [{lower:.1f}, {upper:.1f}] ms straddles the deadline's guard "
            f"band around {deadline_ms:.1f} ms; more episodes would narrow it, and "
            "calling it either way from here would be a preference rather than a result"
        )

    return LatencyVerdictRecord(
        verdict=verdict,
        reason=reason,
        p99_ms=observed,
        ci_lower_ms=lower,
        ci_upper_ms=upper,
        **base,
    )


def _episode_bootstrap(
    episodes: Sequence[Sequence[float]], protocol: LatencyProtocol
) -> tuple[float, float]:
    """Resample **episodes**, recomputing the pooled p99 each time.

    Implemented here rather than by handing ticks to ``bootstrap_ci``
    because the unit is the whole point: ``bootstrap_ci`` resamples the
    sequence it is given, so giving it ticks would produce a per-tick
    interval wearing an episode-level name.
    """
    rng = np.random.default_rng(protocol.bootstrap_seed)
    count = len(episodes)
    draws = np.empty(protocol.bootstrap_resamples, dtype=float)
    for index in range(protocol.bootstrap_resamples):
        picks = rng.integers(0, count, size=count)
        draws[index] = pooled_percentile([episodes[pick] for pick in picks])
    tail = (1.0 - protocol.confidence_level) / 2.0
    lower = float(np.percentile(draws, 100.0 * tail))
    upper = float(np.percentile(draws, 100.0 * (1.0 - tail)))
    return lower, upper


__all__ = [
    "PROTOCOL_DIR",
    "HostConditions",
    "LatencyProtocol",
    "LatencyVerdict",
    "LatencyVerdictRecord",
    "ProtocolError",
    "SentinelReading",
    "pooled_percentile",
    "screen",
]
