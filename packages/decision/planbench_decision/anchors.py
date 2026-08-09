"""Absolute anchors and the single normalisation formula (HĐ-8).

Four metrics measured in metres, milliseconds, megabytes and "per metre"
cannot be added together, so each is first mapped onto [0, 1]:

    u(m) = clip((m - bad) / (good - bad), 0, 1)

The whole design of this module is about *where those two numbers come
from*, because that choice decides the ranking as surely as the weights
do.

**Exogenous, never min-max over the candidate set.** Normalising against
the candidates being compared makes the score of one candidate depend on
which others were entered: add a third planner at 200 ms and two rivals
at 10 ms and 20 ms go from 1.00/0.00 to 1.00/0.95 — the same code, a
different winner (§17 ban 3). Anchors here come from the physics of the
task and from the deployment's declared limits instead, which also makes
``u`` mean something: 0.7 on clearance is "1.7 robot radii from the
wall", not "second best in this batch".

**A gated metric anchors its ``bad`` to the gate's own threshold.** If
``metric_anchors.yaml`` hardcoded ``success_rate.bad = 0.90`` while the
customer declared ``success_rate_min = 0.95``, a candidate at 0.96 would
be scored for clearing a bar nobody set, and the file and the deployment
would drift apart with nothing to show it. So ``bad`` for those metrics
must be a ``${...}`` reference, and :func:`load_anchors` refuses the file
otherwise (HĐ-8.3 law 2).

**References are resolved, not evaluated.** ``${robot.radius * 2.0}``
is parsed by :func:`_resolve_expression` into a field lookup and at most
one multiply or divide. Running these through ``eval`` would turn a YAML
file — the kind of thing a user uploads — into arbitrary code execution,
and the grammar the contract uses is small enough to read by hand.

The anchors are themselves an assumption, which is why they carry a
``version`` that HĐ-13 puts in every manifest, and why
:meth:`ResolvedAnchors.scaled` exists for the ±10% sensitivity sweep
HĐ-8.3 law 3 requires of every decision.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_schemas.task_profile import TaskProfile

__all__ = [
    "ANCHORABLE_METRICS",
    "DEFAULT_ANCHORS_PATH",
    "GATED_METRICS",
    "Anchor",
    "AnchorError",
    "AnchorSet",
    "ResolvedAnchors",
    "load_anchors",
    "u",
]

#: Where the project's anchors live (CONTRACTS §16: ``contracts/``).
DEFAULT_ANCHORS_PATH = Path(__file__).resolve().parents[3] / "contracts" / "metric_anchors.yaml"

#: Metrics an anchor may be declared for. Names are HĐ-6's, with the two
#: aggregates the objectives need (``success_rate`` over an evaluation
#: set, ``tuning_wall_clock_h`` declared at registration). An anchor for
#: anything else is refused rather than ignored: a typo like
#: ``path_efficency`` would otherwise sit in the file forever, scoring
#: nothing, while the metric it meant to anchor silently has none.
ANCHORABLE_METRICS: frozenset[str] = frozenset(
    {
        "success_rate",
        "path_efficiency",
        "time_efficiency",
        "min_clearance",
        "near_miss_rate",
        "p99_latency_ms",
        "memory_estimate_mb",
        "cpu_time_per_mission_s",
        "cpu_time_s",
        "tuning_wall_clock_h",
        "tuning_trials_used",
        "n_tunable_params",
    }
)

#: Metrics that also pass through a feasibility gate (HĐ-7): G3, G4, G5.
#: Their ``bad`` must reference the deployment's threshold — see the
#: module docstring and HĐ-8.3 law 2.
GATED_METRICS: frozenset[str] = frozenset({"success_rate", "p99_latency_ms", "memory_estimate_mb"})

#: ``${path.to.field}`` or ``${path.to.field * 2.0}`` / ``${... / 4}``.
#: Deliberately this small: see the module docstring on not using eval.
_REFERENCE = re.compile(
    r"^\$\{\s*(?P<path>[A-Za-z_][A-Za-z0-9_.]*)\s*"
    r"(?:(?P<op>[*/])\s*(?P<factor>-?\d+(?:\.\d+)?)\s*)?\}$"
)


class AnchorError(ValueError):
    """An anchor file that would score candidates against the wrong bar."""


def u(value: float, good: float, bad: float) -> float:
    """The one normalisation formula of HĐ-8.1.

    The order of ``good`` and ``bad`` encodes the direction, so a metric
    where less is better (latency, memory, near misses) needs no separate
    case — it simply has ``good < bad``.
    """
    if good == bad:
        raise AnchorError(
            f"anchor has good == bad == {good}; the metric would have no scale at all "
            "and every candidate would score the same"
        )
    if not math.isfinite(value):
        raise AnchorError(f"cannot normalise a non-finite measurement ({value!r})")
    return min(max((value - bad) / (good - bad), 0.0), 1.0)


class Anchor(BaseModel):
    """One metric's ``good``/``bad`` pair, before resolution.

    Either side may be a literal number or a ``${...}`` reference into
    the task profile.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    good: float | str
    bad: float | str

    def references(self, side: str) -> bool:
        value = self.good if side == "good" else self.bad
        return isinstance(value, str)


class AnchorSet(BaseModel):
    """The anchor file as written, with its version (HĐ-8.2).

    Unresolved on purpose: the same file is valid for every deployment,
    and what it means is only fixed once a task profile supplies the
    thresholds. :meth:`resolve` is where the two meet.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    anchors: dict[str, Anchor]

    @model_validator(mode="after")
    def _validate_anchors(self) -> AnchorSet:
        """The two file-level laws of HĐ-8.3.

        Raised through Pydantic, so a caller building an ``AnchorSet``
        sees a ``ValidationError`` wrapping :class:`AnchorError` — the
        same shape :class:`~planbench_decision.candidate.Candidate` uses
        for its own schema rules. Errors from *resolving* against a
        profile stay plain :class:`AnchorError`, because by then the
        object is valid and the deployment is what disagrees.
        """
        unknown = sorted(set(self.anchors) - ANCHORABLE_METRICS)
        if unknown:
            raise AnchorError(
                f"anchor(s) {unknown} name no metric this system computes; anchors are keyed "
                f"by the HĐ-6 metric names. Known: {sorted(ANCHORABLE_METRICS)}"
            )
        hardcoded = sorted(
            name
            for name in self.anchors
            if name in GATED_METRICS and not self.anchors[name].references("bad")
        )
        if hardcoded:
            raise AnchorError(
                f"metric(s) {hardcoded} have a feasibility gate, so their 'bad' must reference "
                "the deployment's own threshold with ${...} rather than a literal (HĐ-8.3 law "
                "2). With a literal, a candidate is scored for clearing a bar nobody set, and "
                "this file drifts away from the deployment without a symptom"
            )
        return self

    def resolve(self, profile: TaskProfile) -> ResolvedAnchors:
        """Bind every reference against one deployment's thresholds."""
        resolved: dict[str, tuple[float, float]] = {}
        for name, anchor in self.anchors.items():
            good = _resolve_value(anchor.good, profile, name, "good")
            bad = _resolve_value(anchor.bad, profile, name, "bad")
            if good == bad:
                raise AnchorError(
                    f"anchor {name!r} resolves to good == bad == {good} for task profile "
                    f"{profile.id!r}; the metric would have no scale"
                )
            resolved[name] = (good, bad)
        return ResolvedAnchors(version=self.version, anchors=resolved)


class ResolvedAnchors(BaseModel):
    """Anchors bound to one task profile: pure numbers from here on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    anchors: dict[str, tuple[float, float]]

    def u(self, metric: str, value: float) -> float:
        """Normalise one measurement (HĐ-8.1).

        An unanchored metric raises rather than defaulting: silently
        scoring it as 0 (or 1) would let a metric enter the utility with
        a scale nobody chose.
        """
        pair = self.anchors.get(metric)
        if pair is None:
            raise AnchorError(
                f"no anchor for {metric!r} in anchor config {self.version}; a metric without "
                f"an anchor has no scale. Anchored metrics: {sorted(self.anchors)}"
            )
        good, bad = pair
        return u(value, good, bad)

    def scaled(self, factor: float) -> ResolvedAnchors:
        """Every anchor multiplied by ``factor`` — the ±10% sweep.

        HĐ-8.3 law 3 requires every decision to report whether shifting
        the anchors ±10% changes the recommendation, because the anchors
        are an assumption like any other. Both ends move together: the
        question is whether the *scale* was chosen well, not whether one
        end of it was.

        The version string records the shift so a card produced under a
        perturbed scale can never be mistaken for one produced under the
        declared anchors.
        """
        if factor <= 0:
            raise AnchorError(f"anchor scale factor must be positive, got {factor}")
        return ResolvedAnchors(
            version=f"{self.version}±{(factor - 1.0) * 100:+.0f}%",
            anchors={
                name: (good * factor, bad * factor) for name, (good, bad) in self.anchors.items()
            },
        )


def load_anchors(path: Path | str = DEFAULT_ANCHORS_PATH) -> AnchorSet:
    """Read ``metric_anchors.yaml`` (HĐ-8.2)."""
    path = Path(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AnchorError(f"anchor config not found at {path}") from exc
    except yaml.YAMLError as exc:
        raise AnchorError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(payload, dict) or "metric_anchors" not in payload:
        raise AnchorError(f"{path} must contain a top-level 'metric_anchors' mapping")
    block = payload["metric_anchors"]
    if not isinstance(block, dict):
        raise AnchorError(f"'metric_anchors' in {path} must be a mapping")

    version = block.get("version")
    if not version:
        raise AnchorError(
            f"{path} has no anchor version; HĐ-13 requires anchor_config_version in every "
            "manifest, and a recommendation computed under unknown anchors cannot be rebuilt"
        )

    anchors = {
        name: Anchor.model_validate(value) for name, value in block.items() if name != "version"
    }
    if not anchors:
        raise AnchorError(f"{path} declares no anchors")
    return AnchorSet(version=str(version), anchors=anchors)


def _resolve_value(value: float | str, profile: TaskProfile, metric: str, side: str) -> float:
    if isinstance(value, int | float):
        return float(value)
    return _resolve_expression(value, profile, metric, side)


def _resolve_expression(text: str, profile: TaskProfile, metric: str, side: str) -> float:
    match = _REFERENCE.match(text.strip())
    if match is None:
        raise AnchorError(
            f"anchor {metric}.{side} = {text!r} is not a number and not a reference of the form "
            "${path.to.field} or ${path.to.field * 2.0}"
        )
    field_path = match.group("path")
    base = _lookup(profile, field_path, metric, side)
    op, factor = match.group("op"), match.group("factor")
    if op is None:
        return base
    factor_value = float(factor)
    if op == "/":
        if factor_value == 0:
            raise AnchorError(f"anchor {metric}.{side} divides by zero")
        return base / factor_value
    return base * factor_value


def _lookup(profile: TaskProfile, path: str, metric: str, side: str) -> float:
    """Walk a dotted path into the task profile.

    Restricted to the profile so an anchor cannot reach into anything
    else, and the value has to be a number — a reference to a whole
    block is a mistake worth naming rather than stringifying.
    """
    current: Any = profile
    for part in path.split("."):
        if part.startswith("_"):
            raise AnchorError(f"anchor {metric}.{side} references private field {path!r}")
        current = getattr(current, part, None)
        if current is None:
            raise AnchorError(
                f"anchor {metric}.{side} references {path!r}, which task profile "
                f"{profile.id!r} does not have"
            )
    if isinstance(current, bool) or not isinstance(current, int | float):
        raise AnchorError(
            f"anchor {metric}.{side} references {path!r}, which is "
            f"{type(current).__name__}, not a number"
        )
    return float(current)
