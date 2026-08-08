"""Evaluation-protocol metadata for scenarios: dev / holdout splits (P05).

A split says how a scenario is *used*, not what it *is*. That distinction
decides where the data lives, and it is the whole point of this module:

- It is **not** a field on :class:`~planbench_schemas.scenario.Scenario`.
  ``conditions_checksum`` hashes the scenario, so putting the split there
  would mean re-labelling a scenario changes the identity of every
  benchmark ever run on it, and two reports produced under identical
  physics would stop being comparable because someone edited a policy
  document. Editing this file changes no checksum.
- It is **versioned**, and a report snapshots the version it ran under.
  A scenario promoted from dev to holdout later must not retroactively
  turn old dev numbers into holdout numbers.
- A scenario nobody has classified is ``unassigned``, never ``dev``.
  Defaulting to dev would quietly grow the tuning set every time someone
  adds a scenario, which is exactly the leak a held-out set exists to
  prevent.

The file itself is ``scenario_protocol.json`` beside this module. It is
validated strictly on load: an unknown key or a misspelled split is an
error at import time, not a scenario that silently becomes unassigned.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError

#: ``unassigned`` is a real state, not a missing value: it means nobody
#: has decided yet, and no evaluation claim may be made from it either
#: way.
ScenarioSplit = Literal["dev", "holdout", "unassigned"]

SCENARIO_SPLITS: tuple[ScenarioSplit, ...] = get_args(ScenarioSplit)

PROTOCOL_FILE = Path(__file__).with_name("scenario_protocol.json")


class ScenarioProtocolEntry(BaseModel):
    """One scenario's line in the protocol file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    split: ScenarioSplit
    #: Why this scenario sits where it does. Optional, but the reason a
    #: scenario is held out is the only defence against holding out
    #: whatever happens to be hardest.
    notes: str | None = None


class ScenarioProtocol(BaseModel):
    """The whole protocol file: a version plus the classified scenarios."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: str = Field(min_length=1)
    scenarios: dict[str, ScenarioProtocolEntry] = Field(default_factory=dict)
    notes: str | None = None


class ScenarioProtocolMetadata(BaseModel):
    """What one scenario's protocol status is, resolved for a caller.

    Always answerable: an unknown scenario resolves to ``unassigned``
    under the current protocol version rather than raising, because the
    common caller is a benchmark about to run a scenario somebody just
    created.
    """

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    split: ScenarioSplit
    protocol_version: str
    notes: str | None = None


class ScenarioProtocolError(RuntimeError):
    """The protocol file is unreadable or does not match the schema."""


@lru_cache(maxsize=1)
def load_protocol() -> ScenarioProtocol:
    """Read and validate the protocol file (cached).

    Raises :class:`ScenarioProtocolError` on malformed content. Failing
    loudly is deliberate: a half-parsed protocol would silently downgrade
    held-out scenarios to unassigned, and unassigned scenarios are the
    ones a report is allowed to make no claim about.
    """
    try:
        raw = json.loads(PROTOCOL_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - packaging error
        raise ScenarioProtocolError(f"protocol file missing: {PROTOCOL_FILE}") from exc
    except json.JSONDecodeError as exc:
        raise ScenarioProtocolError(f"protocol file is not valid JSON: {exc}") from exc
    return parse_protocol(raw)


def parse_protocol(raw: object) -> ScenarioProtocol:
    """Validate raw protocol content. Exposed so tests can feed it junk."""
    try:
        return ScenarioProtocol.model_validate(raw)
    except ValidationError as exc:
        raise ScenarioProtocolError(f"invalid scenario protocol: {exc}") from exc


def protocol_version() -> str:
    """Version of the protocol currently in force."""
    return load_protocol().protocol_version


def scenario_protocol_metadata(scenario_name: str) -> ScenarioProtocolMetadata:
    """Protocol status of one scenario; ``unassigned`` when unlisted."""
    protocol = load_protocol()
    entry = protocol.scenarios.get(scenario_name)
    return ScenarioProtocolMetadata(
        scenario_name=scenario_name,
        split=entry.split if entry else "unassigned",
        protocol_version=protocol.protocol_version,
        notes=entry.notes if entry else None,
    )


def scenario_split(scenario_name: str) -> ScenarioSplit:
    """Split of one scenario; ``unassigned`` when unlisted."""
    return scenario_protocol_metadata(scenario_name).split


def scenarios_in_split(split: ScenarioSplit) -> tuple[str, ...]:
    """Scenario names classified into ``split``, sorted.

    ``unassigned`` returns the scenarios explicitly recorded as such —
    not every scenario missing from the file, which is unbounded.
    """
    protocol = load_protocol()
    return tuple(sorted(name for name, entry in protocol.scenarios.items() if entry.split == split))
