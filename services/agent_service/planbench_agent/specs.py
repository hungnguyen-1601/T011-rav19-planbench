"""Natural language mission -> validated benchmark specification.

The LLM proposes; Pydantic disposes. A model answer is only ever a
*draft*: it is parsed with ``extra="forbid"``, then checked against the
real scenario library and algorithm registry. Anything that does not
survive both steps is refused, and nothing runs.

This is the concrete form of "the LLM must not fabricate scenarios"
(spec section 25). A model cannot invent a map, a scenario, or an
algorithm here, because the only accepted values are keys that already
exist in the registries.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from planbench_benchmark import CURRICULUM_ORDER, SCENARIO_LIBRARY, list_algorithms

# Default seed list when a mission does not name one. Three seeds is the
# smallest set that shows variance at all while staying quick enough for
# an interactive request.
DEFAULT_SEEDS: tuple[int, ...] = (1, 2, 3)
MAX_SEEDS = 50


class MissionDraft(BaseModel):
    """A benchmark the agent proposes. Not yet trusted, not yet stored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    scenario: str = Field(min_length=1)
    algorithms: tuple[str, ...] = Field(min_length=1)
    seeds: tuple[int, ...] = Field(min_length=1)

    @property
    def episode_count(self) -> int:
        return len(self.algorithms) * len(self.seeds)


class MissionRefusal(BaseModel):
    """Why a mission was not turned into a spec."""

    model_config = ConfigDict(frozen=True)

    reason: str
    errors: tuple[str, ...] = ()


# JSON Schema handed to the provider for structured output. Enumerating
# the valid scenarios and algorithms in the schema itself is the cheapest
# possible guardrail: a compliant provider cannot emit an unknown name,
# and a non-compliant one is caught by validate_draft below.
def mission_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short benchmark name."},
            "description": {"type": "string"},
            "scenario": {
                "type": "string",
                "enum": list(CURRICULUM_ORDER),
                "description": "Scenario from the built-in library.",
            },
            "algorithms": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": sorted(agent_selectable_algorithms())},
                "description": (
                    "Full navigation stacks to compare. Stacks needing a trained "
                    "checkpoint are absent: a human must configure those."
                ),
            },
            "seeds": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "integer"},
            },
        },
        "required": ["name", "description", "scenario", "algorithms", "seeds"],
        "additionalProperties": False,
    }


def benchmarkable_algorithms() -> set[str]:
    """Stack ids that may appear in a benchmark at all.

    ``astar+pure_pursuit`` is a reference adapter, not a contender
    (decision D12), so it is excluded here — which means the exclusion
    holds for both the structured-output schema and the validator.
    """
    return {info.id for info in list_algorithms() if info.benchmarkable}


def agent_selectable_algorithms() -> set[str]:
    """Stacks the agent may propose on its own.

    Narrower than :func:`benchmarkable_algorithms`, and for a reason
    that goes to the heart of M8: ``astar+ppo`` needs a ``model_path``
    pointing at a trained checkpoint. The agent has no way to know which
    checkpoint is the right one, and inventing a path is exactly the
    fabrication the spec forbids — so any stack with required
    configuration is off the agent's menu. A human names the checkpoint
    and creates that benchmark through the ordinary endpoints.
    """
    return {
        info.id
        for info in list_algorithms()
        if info.benchmarkable and not info.config_schema.get("required")
    }


def required_config_fields(algorithm: str) -> tuple[str, ...]:
    """Config fields a human must supply for this stack, if any."""
    for info in list_algorithms():
        if info.id == algorithm:
            return tuple(info.config_schema.get("required", ()))
    return ()


def parse_structured(payload: Any) -> tuple[MissionDraft | None, tuple[str, ...]]:
    """Parse a provider's structured output into a draft.

    Returns ``(None, errors)`` on any mismatch — a malformed answer is a
    refusal, never a best-effort guess at what the model meant.
    """
    if not isinstance(payload, dict):
        return None, (f"expected a JSON object, got {type(payload).__name__}",)
    try:
        draft = MissionDraft.model_validate(payload)
    except ValidationError as exc:
        return None, tuple(_format_error(error) for error in exc.errors())
    return draft, ()


def _format_error(error: dict) -> str:
    location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
    return f"{location}: {error.get('msg', 'invalid')}"


def validate_draft(draft: MissionDraft) -> tuple[str, ...]:
    """Check a draft against the live registries. Empty tuple means OK."""
    errors: list[str] = []
    if draft.scenario not in SCENARIO_LIBRARY:
        errors.append(f"unknown scenario {draft.scenario!r}; available: {sorted(SCENARIO_LIBRARY)}")
    allowed = agent_selectable_algorithms()
    known = {info.id for info in list_algorithms()}
    benchmarkable = benchmarkable_algorithms()
    for algorithm in draft.algorithms:
        if algorithm not in known:
            errors.append(f"unknown algorithm {algorithm!r}; available: {sorted(allowed)}")
        elif algorithm not in benchmarkable:
            errors.append(
                f"algorithm {algorithm!r} is a reference adapter, not benchmarkable; "
                "it may not be compared against other stacks"
            )
        elif algorithm not in allowed:
            fields = ", ".join(required_config_fields(algorithm))
            errors.append(
                f"algorithm {algorithm!r} requires configuration the agent must not "
                f"invent ({fields}); a human has to create this benchmark and supply it"
            )
    if len(set(draft.algorithms)) != len(draft.algorithms):
        errors.append("duplicate algorithms in the draft")
    if len(set(draft.seeds)) != len(draft.seeds):
        errors.append("seeds must be unique")
    if len(draft.seeds) > MAX_SEEDS:
        errors.append(f"at most {MAX_SEEDS} seeds per benchmark, got {len(draft.seeds)}")
    if any(seed < 0 for seed in draft.seeds):
        errors.append("seeds must be non-negative")
    return tuple(errors)


# -- deterministic fallback parser -------------------------------------
#
# Used by the mock provider, and available on its own when no model is
# configured. It is keyword matching, not comprehension: it recognises
# the names that already exist in the registries and nothing else. When
# it cannot find a scenario it returns None rather than guessing.

_ALGORITHM_ALIASES: dict[str, str] = {
    "dwa": "astar+dwa",
    "a*+dwa": "astar+dwa",
    "astar+dwa": "astar+dwa",
    "ppo": "astar+ppo",
    "rl": "astar+ppo",
    "a*+ppo": "astar+ppo",
    "astar+ppo": "astar+ppo",
}

_SEED_LIST = re.compile(r"seeds?\s*[:=]?\s*((?:\d+\s*[, ]\s*)*\d+)", re.IGNORECASE)
_SEED_COUNT = re.compile(r"(\d+)\s*seeds?", re.IGNORECASE)


def parse_mission_text(text: str) -> MissionDraft | None:
    """Best-effort keyword parse of a mission sentence.

    Deterministic by construction: the same sentence always yields the
    same draft, which is what makes it usable inside the mock provider.
    """
    lowered = text.lower()

    scenario = _first_scenario(lowered)
    if scenario is None:
        return None

    algorithms = _find_algorithms(lowered)
    if not algorithms:
        algorithms = tuple(sorted(agent_selectable_algorithms()))

    return MissionDraft(
        name=f"{scenario}: {' vs '.join(algorithms)}",
        description=text.strip(),
        scenario=scenario,
        algorithms=algorithms,
        seeds=_find_seeds(text),
    )


def _first_scenario(lowered: str) -> str | None:
    """Longest name first, so 'narrow_corridor' beats 'corridor'."""
    matches = [
        (name, lowered.index(needle))
        for name in SCENARIO_LIBRARY
        for needle in (name, name.replace("_", " "))
        if needle in lowered
    ]
    if not matches:
        return None
    # Earliest mention wins; ties break on the longer (more specific) name.
    matches.sort(key=lambda item: (item[1], -len(item[0])))
    return matches[0][0]


def _find_algorithms(lowered: str) -> tuple[str, ...]:
    found: list[str] = []
    for alias, algorithm in _ALGORITHM_ALIASES.items():
        if alias in lowered and algorithm not in found:
            found.append(algorithm)
    return tuple(sorted(found))


def _find_seeds(text: str) -> tuple[int, ...]:
    explicit = _SEED_LIST.search(text)
    if explicit:
        seeds = tuple(dict.fromkeys(int(value) for value in re.findall(r"\d+", explicit.group(1))))
        if seeds:
            return seeds[:MAX_SEEDS]
    counted = _SEED_COUNT.search(text)
    if counted:
        count = min(int(counted.group(1)), MAX_SEEDS)
        if count > 0:
            return tuple(range(1, count + 1))
    return DEFAULT_SEEDS


__all__ = [
    "DEFAULT_SEEDS",
    "MAX_SEEDS",
    "MissionDraft",
    "MissionRefusal",
    "agent_selectable_algorithms",
    "benchmarkable_algorithms",
    "mission_schema",
    "parse_mission_text",
    "parse_structured",
    "required_config_fields",
    "validate_draft",
]
