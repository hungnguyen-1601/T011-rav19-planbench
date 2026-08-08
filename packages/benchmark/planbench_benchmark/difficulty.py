"""Measured scenario difficulty: calibration cache and lookup (P03).

Difficulty here is not an opinion and not a curriculum position. It is a
measurement:

``difficulty(scenario) = 1 - success_rate(pinned baseline, fixed seeds)``

Which makes the *baseline* the whole content of the claim. "A* + DWA
fails 40% of the time" only means something if the reader can tell which
A* + DWA, on which robot, over which seeds, with replanning on or off,
at which commit. So the cache pins all of it, and a lookup carries the
baseline along with the number rather than handing out a bare float.

Three rules the design follows:

- **Difficulty is not a field on** :class:`~planbench_schemas.scenario.Scenario`.
  It is an outcome of running the scenario, not part of what the scenario
  *is*; putting it in the schema would fold a measurement into the
  ``conditions_checksum`` and make re-calibrating look like a change of
  physics. Same reasoning as the dev/held-out split (P05).
- **The cache is versioned and identifies its own inputs.** Changing the
  baseline means a new ``calibration_version``, never an overwrite:
  numbers produced under different baselines are different quantities
  that happen to share a name.
- **A scenario that has not been calibrated has no difficulty.**
  :func:`get_difficulty` returns ``None``; it never guesses, never
  raises, and never falls back to the curriculum ordering — that ordering
  is a hand-written intention, and checking it against measurement is the
  point of this module.

The cache file is written by ``scripts/calibrate_difficulty.py`` and is
meant to be reproducible from it. Nothing here writes it, and nothing
here repairs it: a cache that does not match the schema is an error, not
a set of scenarios that quietly lose their labels.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from planbench_benchmark.scenario_protocol import ScenarioSplit

CALIBRATION_FILE = Path(__file__).with_name("difficulty_calibration.json")

#: Coarse label for a measured difficulty. Bands exist so a UI can group
#: scenarios without inventing its own thresholds; the number and its
#: interval stay the thing to quote. ``unsolved`` is kept apart from
#: ``hard`` deliberately: a scenario the baseline never once solved says
#: nothing about *how much* harder it is than one it solved twice, and
#: calling both "hard" hides that the scale has run out.
DifficultyBand = Literal["easy", "moderate", "hard", "unsolved"]

#: Upper bounds (inclusive) of each band, in difficulty. Stated once so
#: backend, script and UI cannot drift apart.
BAND_THRESHOLDS: tuple[tuple[float, DifficultyBand], ...] = (
    (0.2, "easy"),
    (0.6, "moderate"),
    (0.999, "hard"),
)

#: The seeds a calibration run uses unless told otherwise. Fixed, and
#: written into the cache: difficulty measured over a different set of
#: seeds is a different measurement, and "30 seeds" alone does not say
#: which 30.
DEFAULT_CALIBRATION_SEEDS: tuple[int, ...] = tuple(range(30))

#: Below this, a difficulty is a hint rather than a measurement. Matches
#: the P04 adequacy threshold on purpose — the underlying quantity is a
#: success rate over seeds either way.
MIN_CALIBRATION_SEEDS = 30

#: A difficulty range narrower than this means the scenario set does not
#: separate algorithms: every stack sees roughly the same wall. Reported,
#: never silently smoothed.
MIN_USEFUL_DIFFICULTY_SPREAD = 0.3

#: The interior of the scale: scenarios the baseline sometimes solves and
#: sometimes does not. These are the only ones that can separate two
#: stacks that are both roughly competent — outside this band, either
#: everything passes or everything fails and both stacks score the same.
MIDRANGE_DIFFICULTY = (0.2, 0.8)

#: Below this many interior scenarios the set is bimodal: it spans the
#: full range and still discriminates almost nothing. Checked separately
#: from the spread, because a set sitting entirely at 0.0 and 1.0 passes
#: the spread test with the maximum possible score.
MIN_MIDRANGE_SCENARIOS = 2


def difficulty_band(value: float) -> DifficultyBand:
    """Band a difficulty falls in. ``1.0`` is ``unsolved``, not ``hard``."""
    for upper, band in BAND_THRESHOLDS:
        if value <= upper:
            return band
    return "unsolved"


class DifficultyCalibrationError(RuntimeError):
    """The calibration cache is unreadable or does not match the schema."""


class BaselineSpec(BaseModel):
    """Everything that had to be pinned for the numbers to mean anything.

    Storing only ``"astar+dwa"`` would be a name, not a baseline: the same
    stack with different DWA weights, a different robot radius or
    replanning enabled produces a different difficulty scale, and a reader
    comparing two caches would have no way to notice.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm: str = Field(min_length=1)
    #: The local-planner overrides the baseline ran with. Empty means the
    #: registry defaults — recorded as empty rather than expanded, so a
    #: later change to those defaults shows up as a code change (git sha)
    #: rather than being silently absorbed.
    algorithm_config: dict = Field(default_factory=dict)
    #: Replanning was not implemented when this scale was measured. When
    #: it arrives it changes what the baseline can do and therefore every
    #: number here, which is why it is pinned rather than assumed.
    replanning_enabled: bool = False
    seeds: tuple[int, ...] = Field(min_length=1)
    #: Robot the whole scale was measured on. One profile for the entire
    #: cache: difficulties measured on robots of different size are not
    #: points on one scale.
    robot_profile: dict
    #: Contract version of the benchmark engine that produced the runs.
    benchmark_spec_version: str = Field(min_length=1)
    #: Evaluation-protocol version in force at calibration time (P05).
    #: Recorded, not used: splits do not affect difficulty, but a reader
    #: comparing a difficulty against a split needs to know they came from
    #: the same moment.
    protocol_version: str | None = None
    #: Commit the calibration ran at. ``"unknown"`` when the tree is not a
    #: git checkout — stated as unknown rather than omitted, because a
    #: missing field reads as "nobody thought about it".
    git_sha: str = Field(min_length=1)


class ScenarioCalibration(BaseModel):
    """One scenario's measured difficulty, with what it was measured on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    difficulty: float = Field(ge=0.0, le=1.0)
    #: Interval for the difficulty itself (Wilson, mirrored from the
    #: success-rate interval). A difficulty of 0.0 from 30 seeds is not
    #: certainty that the scenario is trivial, and the interval is what
    #: says so.
    ci95: tuple[float, float]
    success_rate: float = Field(ge=0.0, le=1.0)
    episodes: int = Field(gt=0)
    #: How the failures broke down (status -> count). A scenario that is
    #: hard because the robot collides is a different scenario from one
    #: that is hard because the planner finds no path, and the difficulty
    #: number alone cannot tell them apart.
    status_counts: dict[str, int] = Field(default_factory=dict)
    #: Identity of what was measured. If the scenario is edited later, the
    #: checksums stop matching and the cached number is stale — see
    #: :meth:`DifficultyLabel.stale`.
    map_checksum: str = Field(min_length=1)
    scenario_checksum: str = Field(min_length=1)
    #: Split at calibration time, for the record only.
    scenario_split: ScenarioSplit = "unassigned"


class DifficultyCalibration(BaseModel):
    """The whole cache: one baseline, one scale, many scenarios."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calibration_version: str = Field(min_length=1)
    baseline: BaselineSpec
    scenarios: dict[str, ScenarioCalibration] = Field(default_factory=dict)
    notes: str | None = None

    @property
    def git_sha(self) -> str:
        return self.baseline.git_sha


class DifficultyLabel(BaseModel):
    """What a caller gets back for one scenario.

    The baseline travels with the value on purpose. A difficulty handed
    out as a bare float invites "this scenario is 0.4 hard"; what was
    measured is "the pinned baseline failed 40% of the time here".
    """

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    value: float
    ci95: tuple[float, float]
    band: DifficultyBand
    calibration_version: str
    baseline_algorithm: str
    seed_count: int
    #: False when fewer seeds than :data:`MIN_CALIBRATION_SEEDS` went into
    #: it — a dry run, typically. The label is still returned; it just
    #: must not be presented as a calibrated scale.
    adequate: bool
    #: True when the scenario no longer hashes to what was measured. The
    #: number is still shown, flagged: hiding it would leave a blank that
    #: looks like "never calibrated", which is a different problem with a
    #: different fix.
    stale: bool = False


class DifficultyCoverage(BaseModel):
    """Whether the calibrated set actually spans a range of difficulty.

    A benchmark whose scenarios all sit at 0.0 measures nothing: every
    stack passes everything and the ranking is noise. All at 1.0 is the
    same failure upside down. This is the check the plan asks for, and it
    is reported rather than fixed — the fix is authoring scenarios, not
    editing numbers.
    """

    model_config = ConfigDict(frozen=True)

    calibration_version: str | None = None
    scenario_count: int = 0
    min_difficulty: float | None = None
    max_difficulty: float | None = None
    spread: float | None = None
    #: Band -> how many scenarios landed in it.
    band_counts: dict[str, int] = Field(default_factory=dict)
    #: How many scenarios sit in :data:`MIDRANGE_DIFFICULTY` — the only
    #: ones that can tell two competent stacks apart. Reported next to
    #: the spread because the two answer different questions and a set
    #: can score perfectly on one while failing the other.
    midrange_count: int = 0
    #: Library scenarios with no entry in the cache.
    uncalibrated: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def parse_calibration(raw: object) -> DifficultyCalibration:
    """Validate raw cache content. Exposed so tests can feed it junk."""
    try:
        return DifficultyCalibration.model_validate(raw)
    except ValidationError as exc:
        raise DifficultyCalibrationError(f"invalid difficulty calibration: {exc}") from exc


@lru_cache(maxsize=1)
def load_calibration() -> DifficultyCalibration | None:
    """Read and validate the cache, or ``None`` when there is no cache.

    A missing file is a normal state — nobody has calibrated yet — and
    resolves to ``None``. A file that exists but is malformed raises: it
    means someone hand-edited a measurement, and silently ignoring that
    would turn a corrupted scale into an uncalibrated one, which looks the
    same from the outside and is much easier to miss.
    """
    if not CALIBRATION_FILE.exists():
        return None
    try:
        raw = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DifficultyCalibrationError(f"calibration cache is not valid JSON: {exc}") from exc
    return parse_calibration(raw)


def calibration_version() -> str | None:
    """Version of the calibration in force, or ``None`` when uncalibrated."""
    calibration = load_calibration()
    return calibration.calibration_version if calibration else None


def _current_checksums(scenario_name: str) -> tuple[str, str] | None:
    """``(map_checksum, scenario_checksum)`` as the code builds it today.

    ``None`` for a scenario that is not in the built-in library: nothing
    to compare against, so nothing can be called stale.
    """
    # Imported here rather than at module scope: ``scenarios`` and
    # ``spec`` both sit above this module in the dependency order, and a
    # top-level import would make the cache lookup drag the whole
    # scenario-building stack in with it.
    from planbench_benchmark.scenarios import SCENARIO_LIBRARY
    from planbench_benchmark.spec import _scenario_checksum

    builder = SCENARIO_LIBRARY.get(scenario_name)
    if builder is None:
        return None
    map_data, scenario = builder()
    return (map_data.checksum(), _scenario_checksum(scenario))


def get_difficulty(
    scenario_name: str,
    calibration_version: str | None = None,
) -> DifficultyLabel | None:
    """Measured difficulty of one scenario, or ``None``.

    ``None`` means "not calibrated under the calibration you asked for" —
    no cache at all, a cache that does not mention this scenario, or a
    version that does not match the one requested. All three are ordinary
    states, and none of them justifies inventing a number or raising at a
    caller that just wanted to render a table.
    """
    calibration = load_calibration()
    if calibration is None:
        return None
    if calibration_version is not None and calibration.calibration_version != calibration_version:
        return None
    entry = calibration.scenarios.get(scenario_name)
    if entry is None:
        return None
    current = _current_checksums(scenario_name)
    stale = current is not None and current != (entry.map_checksum, entry.scenario_checksum)
    return DifficultyLabel(
        scenario_name=scenario_name,
        value=entry.difficulty,
        ci95=entry.ci95,
        band=difficulty_band(entry.difficulty),
        calibration_version=calibration.calibration_version,
        baseline_algorithm=calibration.baseline.algorithm,
        seed_count=len(calibration.baseline.seeds),
        adequate=len(calibration.baseline.seeds) >= MIN_CALIBRATION_SEEDS,
        stale=stale,
    )


def difficulty_coverage(scenario_names: tuple[str, ...] | None = None) -> DifficultyCoverage:
    """How well the calibrated scenarios span the difficulty range.

    ``scenario_names`` defaults to the built-in library, which is the set
    the answer is about: an uncalibrated scenario is a gap in the scale,
    not something to leave out of the count.
    """
    from planbench_benchmark.scenarios import CURRICULUM_ORDER

    names = scenario_names if scenario_names is not None else CURRICULUM_ORDER
    calibration = load_calibration()
    if calibration is None:
        return DifficultyCoverage(
            uncalibrated=tuple(names),
            warnings=("no difficulty calibration has been run; scenario difficulty is unmeasured",),
        )

    values: list[float] = []
    band_counts: dict[str, int] = {}
    uncalibrated: list[str] = []
    for name in names:
        entry = calibration.scenarios.get(name)
        if entry is None:
            uncalibrated.append(name)
            continue
        values.append(entry.difficulty)
        band = difficulty_band(entry.difficulty)
        band_counts[band] = band_counts.get(band, 0) + 1

    warnings: list[str] = []
    if uncalibrated:
        warnings.append(
            f"{len(uncalibrated)} scenario(s) not calibrated under "
            f"{calibration.calibration_version}: {', '.join(uncalibrated)}"
        )
    if not values:
        return DifficultyCoverage(
            calibration_version=calibration.calibration_version,
            uncalibrated=tuple(uncalibrated),
            warnings=tuple(warnings),
        )

    low, high = min(values), max(values)
    spread = high - low
    midrange_low, midrange_high = MIDRANGE_DIFFICULTY
    midrange = sum(1 for value in values if midrange_low < value < midrange_high)
    if midrange < MIN_MIDRANGE_SCENARIOS:
        # Checked before the spread, because this is the failure the
        # spread test cannot see: a set split between 0.0 and 1.0 scores
        # a perfect spread of 1.0 and still separates nothing, since
        # every competent stack passes the same scenarios and fails the
        # same ones.
        warnings.append(
            f"only {midrange} scenario(s) sit between {midrange_low:.1f} and "
            f"{midrange_high:.1f}; outside that range the baseline either always "
            "succeeds or always fails, so the set cannot separate two stacks that "
            "are both competent"
        )
    if spread < MIN_USEFUL_DIFFICULTY_SPREAD:
        warnings.append(
            f"difficulty spans only {spread:.2f} ({low:.2f}-{high:.2f}); the scenario "
            "set does not separate stacks by difficulty, so a difficulty curve drawn "
            "from it says little"
        )
    if high <= BAND_THRESHOLDS[0][0]:
        warnings.append(
            "every calibrated scenario is easy for the baseline; the set has no "
            "headroom to distinguish better stacks"
        )
    if low > BAND_THRESHOLDS[1][0]:
        warnings.append(
            "every calibrated scenario is hard for the baseline; failures dominate "
            "and differences between stacks will be hidden by them"
        )
    if band_counts.get("unsolved"):
        warnings.append(
            f"{band_counts['unsolved']} scenario(s) the baseline never solved; their "
            "difficulty is pinned at 1.0 and cannot be ordered against each other"
        )
    if len(calibration.baseline.seeds) < MIN_CALIBRATION_SEEDS:
        warnings.append(
            f"calibrated over {len(calibration.baseline.seeds)} seed(s), fewer than "
            f"{MIN_CALIBRATION_SEEDS}; treat these as provisional"
        )

    return DifficultyCoverage(
        calibration_version=calibration.calibration_version,
        scenario_count=len(values),
        min_difficulty=low,
        max_difficulty=high,
        spread=spread,
        band_counts=band_counts,
        midrange_count=midrange,
        uncalibrated=tuple(uncalibrated),
        warnings=tuple(warnings),
    )
