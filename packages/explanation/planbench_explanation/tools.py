"""Tool cards: what a checker is allowed to establish, in typed form.

E0 owns the **shape** of a card and the catalog that holds them; E5
fills the catalog with a card per tool across the four classes, and E6
implements the checkers themselves. The shape is here because the
promotion matrix reads it, and a matrix reading an undefined shape is a
matrix whose rules live in whoever wrote the last card.

**Prose and code path are separated by construction, not by review.**
The design note asks for a human-readable ``verifies`` /
``does_not_verify`` block *and* a typed policy, plus a test that every
prose line has a typed counterpart. A test like that passes on the day
it is written and then rots quietly. So the prose is stored **keyed by
the typed value it explains**: ``verifies`` maps each supported
proposition type to a sentence, ``does_not_verify`` maps each forbidden
inference type to a sentence, and the validator requires the key sets to
equal the typed policy. A sentence with no typed counterpart cannot be
written, and a typed entry with no sentence cannot either. Free prose
with no proposition behind it goes in ``notes``, which nothing reads.

**What the matrix actually consults**, and nothing else:
``proposition_policy`` (which propositions this tool can support, which
over-readings it must never be used for, its maximum claim level) and
``evidence_policy`` (which input provenances it accepts). Everything
outside those two blocks is documentation.

The card is also where deterministic stops meaning causal:
``latency_vs_expanded_nodes`` is a perfectly deterministic computation
whose maximum claim level is ``associated``, because correlating node
expansions with latency does not demonstrate that the expansions caused
it.

**And the card closes the data shape, not only the conclusions.** A
catalog that says which tools exist and what they may establish, while
leaving arguments as a free-form mapping, locks the wrong half: every
checker written against it invents its own argument names and its own
measurement keys, and the contract becomes whatever the first
implementation happened to do. :class:`ToolIO` is the other half —
which arguments a request must and may carry, and which measurement
keys a result may return — enforced at admission and at recording.

The JSON Schema files the design section names
(``schemas/tools/<tool_id>.request.json``) are **generated from**
:class:`ToolIO` rather than written beside it. Two hand-maintained
descriptions of one contract disagree eventually, and the one nobody
runs is the one that rots; here the typed spec is the source and the
file is an export of it, with a test that regenerating changes nothing.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.levels import ClaimLevel
from planbench_explanation.propositions import (
    INFERENCE_ONLY_PROPOSITIONS,
    PropositionType,
    canonical_propositions,
)
from planbench_explanation.provenance import InputProvenance

#: Which of the four catalog classes a tool belongs to (design section 3.3).
ToolClass = Literal["fact_query", "evidence_navigation", "mechanism_check", "research_proposal"]

#: Which lane a tool's execution belongs to. ``diagnostic`` reads
#: recorded data; ``research`` would produce a new run, which no tool is
#: allowed to start — research tools emit specifications only.
ExecutionLane = Literal["diagnostic", "research"]


class ToolPurpose(BaseModel):
    """Prose for humans, keyed by the typed value it explains."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verifies: dict[PropositionType, str] = Field(default_factory=dict)
    does_not_verify: dict[PropositionType, str] = Field(default_factory=dict)
    #: Sentences with no proposition behind them. Never read by code.
    notes: tuple[str, ...] = ()


class PropositionPolicy(BaseModel):
    """The typed half — the only half the promotion matrix reads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supported_proposition_types: tuple[PropositionType, ...] = ()
    forbidden_inference_types: tuple[PropositionType, ...] = ()
    maximum_claim_level: ClaimLevel

    @model_validator(mode="after")
    def _check(self) -> PropositionPolicy:
        canonical_propositions(
            self.supported_proposition_types, field="supported_proposition_types"
        )
        canonical_propositions(self.forbidden_inference_types, field="forbidden_inference_types")
        overlap = set(self.supported_proposition_types) & set(self.forbidden_inference_types)
        if overlap:
            raise ValueError(
                f"tool policy both supports and forbids {sorted(overlap)}; "
                "one card cannot answer both ways about the same proposition"
            )
        unassertable = set(self.supported_proposition_types) & set(INFERENCE_ONLY_PROPOSITIONS)
        if unassertable:
            raise ValueError(
                f"{sorted(unassertable)} are inference-only types and cannot be "
                "supported by any tool; list them under forbidden_inference_types"
            )
        if self.maximum_claim_level == "intervention_supported":
            raise ValueError(
                "no tool card may declare maximum_claim_level "
                "'intervention_supported': that level requires a preregistered "
                "intervention in the research lane, which no checker performs"
            )
        return self


class EvidencePolicy(BaseModel):
    """Which input pedigrees this tool's result may be trusted on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_input_provenance: tuple[InputProvenance, ...]

    @model_validator(mode="after")
    def _check(self) -> EvidencePolicy:
        if not self.allowed_input_provenance:
            raise ValueError("allowed_input_provenance may not be empty")
        if "missing" in self.allowed_input_provenance:
            raise ValueError(
                "'missing' is never an allowed input provenance; a tool without "
                "its inputs reports execution_status 'not_checkable'"
            )
        return self


#: JSON-Schema-expressible argument kinds. Deliberately four: an
#: argument that needs a richer type is an argument that wants to be two
#: arguments, and a free-form object here would reopen exactly the hole
#: this class closes.
ArgumentKind = Literal["string", "integer", "number", "boolean"]

_JSON_TYPES: dict[ArgumentKind, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
}


class ArgumentSpec(BaseModel):
    """One argument a tool takes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    kind: ArgumentKind
    required: bool = True
    description: str = Field(min_length=1)


#: Physical units a measurement can carry, plus the two dimensionless
#: kinds. Closed so ``0.68`` cannot mean metres in one checker and
#: centimetres in another, which is the classic way two correct
#: implementations disagree.
MeasurementUnit = Literal["m", "s", "ms", "count", "ratio", "correlation", "flag"]

#: What an evidence-navigation tool points at. A pointer has a kind:
#: "episode ep-004" and "the window 12.5–18.0 s of ep-004" are different
#: things to open, and a caller that cannot tell them apart cannot open
#: either.
ReferenceKind = Literal[
    "episode",
    "replay_window",
    "trajectory_segment",
    "trace_rows",
    "map_region",
]


class MeasurementSpec(BaseModel):
    """One number a tool may report, with its unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    unit: MeasurementUnit
    #: Whether a **completed** result must carry it. Optional
    #: measurements exist for genuinely conditional quantities — a lower
    #: bound that only appears where the map is one-sided — not as a
    #: default for anything inconvenient.
    required: bool = True
    description: str = Field(min_length=1)


class ReferenceSpec(BaseModel):
    """One kind of pointer a tool may return."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ReferenceKind
    required: bool = True
    description: str = Field(min_length=1)


class ToolIO(BaseModel):
    """What a tool takes and what it may report.

    Three closed sets rather than one. ``arguments`` is the request
    shape. ``measurements`` is the numbers, each with a unit and a
    required flag — a key list alone stops a checker inventing
    ``width``, but it does not stop one returning nothing at all and
    calling it a completed check. ``references`` is the pointers, which
    are not numbers and were being smuggled through as counts: a
    navigation tool that reports ``n_exemplars: 4`` has told the caller
    how many episodes to open and not which.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    arguments: tuple[ArgumentSpec, ...] = ()
    measurements: tuple[MeasurementSpec, ...] = ()
    references: tuple[ReferenceSpec, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> ToolIO:
        names = [argument.name for argument in self.arguments]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"argument(s) {duplicates} declared twice on one tool")
        keys = [measurement.name for measurement in self.measurements]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            raise ValueError(f"measurement(s) {repeated} declared twice on one tool")
        kinds = [reference.kind for reference in self.references]
        twice = sorted({kind for kind in kinds if kinds.count(kind) > 1})
        if twice:
            raise ValueError(f"reference kind(s) {twice} declared twice on one tool")
        return self

    @property
    def required_arguments(self) -> tuple[str, ...]:
        return tuple(argument.name for argument in self.arguments if argument.required)

    @property
    def known_arguments(self) -> tuple[str, ...]:
        return tuple(argument.name for argument in self.arguments)

    @property
    def measurement_keys(self) -> tuple[str, ...]:
        return tuple(measurement.name for measurement in self.measurements)

    @property
    def required_measurement_keys(self) -> tuple[str, ...]:
        return tuple(measurement.name for measurement in self.measurements if measurement.required)

    @property
    def reference_kinds(self) -> tuple[str, ...]:
        return tuple(reference.kind for reference in self.references)

    @property
    def required_reference_kinds(self) -> tuple[str, ...]:
        return tuple(reference.kind for reference in self.references if reference.required)

    def check_arguments(self, arguments: Mapping[str, object]) -> tuple[str, ...]:
        """Everything wrong with a request's arguments, as sentences.

        Returns a list rather than raising so a caller can report every
        problem at once: an analyst told about one missing argument at a
        time spends its round rediscovering the signature.
        """
        problems: list[str] = []
        missing = sorted(set(self.required_arguments) - set(arguments))
        if missing:
            problems.append(f"missing required argument(s) {missing}")
        unknown = sorted(set(arguments) - set(self.known_arguments))
        if unknown:
            problems.append(
                f"unknown argument(s) {unknown}; the tool takes {list(self.known_arguments)}"
            )
        by_name = {argument.name: argument for argument in self.arguments}
        for name, value in sorted(arguments.items()):
            spec = by_name.get(name)
            if spec is None:
                continue
            if not _kind_matches(spec.kind, value):
                problems.append(
                    f"argument {name!r} is {type(value).__name__}, expected {spec.kind}"
                )
        return tuple(problems)

    def check_measurements(
        self, measurements: Mapping[str, float], *, completed: bool
    ) -> tuple[str, ...]:
        """Unknown keys always; missing required keys only when completed.

        A check that did not run reports no numbers, and demanding them
        would force a failing checker to invent some.
        """
        problems: list[str] = []
        unknown = sorted(set(measurements) - set(self.measurement_keys))
        if unknown:
            problems.append(
                f"measurement key(s) {unknown} are not on this tool's card; the card "
                f"declares {list(self.measurement_keys)}"
            )
        if completed:
            missing = sorted(set(self.required_measurement_keys) - set(measurements))
            if missing:
                problems.append(
                    f"completed result omits required measurement(s) {missing}; a "
                    "check that reports nothing is not a check that found nothing"
                )
        return tuple(problems)

    def check_references(self, kinds: Iterable[str], *, completed: bool) -> tuple[str, ...]:
        present = set(kinds)
        problems: list[str] = []
        unknown = sorted(present - set(self.reference_kinds))
        if unknown:
            problems.append(
                f"reference kind(s) {unknown} are not on this tool's card; the card "
                f"declares {list(self.reference_kinds)}"
            )
        if completed:
            missing = sorted(set(self.required_reference_kinds) - present)
            if missing:
                problems.append(
                    f"completed result carries no {missing} reference; a navigation "
                    "tool that returns a count and no pointer has said how many "
                    "things to open without saying which"
                )
        return tuple(problems)

    def request_schema(self, *, tool_id: str, tool_version: str) -> dict[str, object]:
        """The JSON Schema the design section points at, generated."""
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"schemas/tools/{tool_id}.request.json",
            "title": f"{tool_id}@{tool_version} arguments",
            "type": "object",
            "additionalProperties": False,
            "required": list(self.required_arguments),
            "properties": {
                argument.name: {
                    "type": _JSON_TYPES[argument.kind],
                    "description": argument.description,
                }
                for argument in self.arguments
            },
        }

    def result_schema(self, *, tool_id: str, tool_version: str) -> dict[str, object]:
        """The output half: measurements with units, and typed pointers.

        Written to be **as strict as the host**, which the first version
        was not: it required ``measurements`` and left ``references``
        optional, so a navigation payload with no episode pointer
        validated against the published schema and was then refused at
        recording. A schema weaker than the runtime is worse than no
        schema — it tells an integrator their payload is fine.

        Required reference kinds become a ``contains`` apiece rather
        than one blanket ``minItems``: a tool needing an episode *and* a
        window is not satisfied by two episodes.
        """
        required: list[str] = []
        if self.required_measurement_keys:
            required.append("measurements")
        references: dict[str, object] = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "ref"],
                "properties": {
                    "kind": {"enum": list(self.reference_kinds)},
                    "ref": {"type": "string", "minLength": 1},
                    "label": {"type": ["string", "null"]},
                },
            },
        }
        if self.required_reference_kinds:
            required.append("references")
            references["minItems"] = 1
            references["allOf"] = [
                {
                    "contains": {
                        "type": "object",
                        "required": ["kind"],
                        "properties": {"kind": {"const": kind}},
                    }
                }
                for kind in self.required_reference_kinds
            ]
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"schemas/tools/{tool_id}.result.json",
            "title": f"{tool_id}@{tool_version} output",
            "type": "object",
            "additionalProperties": False,
            "required": required,
            "properties": {
                "measurements": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(self.required_measurement_keys),
                    "properties": {
                        measurement.name: {
                            "type": "number",
                            "unit": measurement.unit,
                            "description": measurement.description,
                        }
                        for measurement in self.measurements
                    },
                },
                "references": references,
            },
        }


def _kind_matches(kind: ArgumentKind, value: object) -> bool:
    """Type check with the two JSON traps closed.

    ``bool`` is a subclass of ``int`` in Python, so a naive check accepts
    ``True`` where an integer was asked for. And an integer is a
    perfectly good ``number``, so that direction is allowed on purpose.
    """
    if isinstance(value, bool):
        return kind == "boolean"
    if kind == "integer":
        return isinstance(value, int)
    if kind == "number":
        return isinstance(value, (int, float))
    if kind == "string":
        return isinstance(value, str)
    return False


class ToolCard(BaseModel):
    """One entry of the tool catalog."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    tool_class: ToolClass
    lane: ExecutionLane = "diagnostic"
    #: Research-proposal tools emit a specification and nothing else. The
    #: flag sits on the card so a host can refuse to execute one without
    #: knowing what the tool does.
    execution_authorized: bool = True
    purpose: ToolPurpose = ToolPurpose()
    proposition_policy: PropositionPolicy
    evidence_policy: EvidencePolicy
    #: Evidence the packet must carry before the tool may be requested.
    required_evidence: tuple[str, ...] = ()
    #: The arguments this tool takes and the measurement keys it may
    #: return. Enforced at admission and at recording, not documented.
    io: ToolIO = ToolIO()
    #: Failure codes specific to this tool. A **closed** list: the host
    #: contributes its own generic codes, and anything outside the union
    #: is refused, because a failure code nobody enumerated is a failure
    #: mode nobody designed for.
    failure_modes: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        """``(tool_id, tool_version)`` — how a result names its card."""
        return (self.tool_id, self.tool_version)

    @property
    def input_schema_ref(self) -> str:
        """Where the generated request schema lives. Derived, not stored.

        Stored, it would be a string somebody could point anywhere. The
        path follows from the tool id, and
        :func:`write_tool_schemas` is what puts a file there.
        """
        return f"schemas/tools/{self.tool_id}.request.json"

    @property
    def output_schema_ref(self) -> str:
        return f"schemas/tools/{self.tool_id}.result.json"

    @model_validator(mode="after")
    def _check(self) -> ToolCard:
        prose_keys = set(self.purpose.verifies)
        typed_keys = set(self.proposition_policy.supported_proposition_types)
        if prose_keys != typed_keys:
            raise ValueError(
                f"purpose.verifies covers {sorted(prose_keys)} but the typed policy "
                f"supports {sorted(typed_keys)}; every supported proposition needs a "
                "sentence and every sentence needs a supported proposition. Prose "
                "without a typed counterpart belongs in purpose.notes."
            )
        forbidden_prose = set(self.purpose.does_not_verify)
        forbidden_typed = set(self.proposition_policy.forbidden_inference_types)
        if forbidden_prose != forbidden_typed:
            raise ValueError(
                f"purpose.does_not_verify covers {sorted(forbidden_prose)} but the "
                f"typed policy forbids {sorted(forbidden_typed)}; the two halves must "
                "name the same over-readings."
            )
        if self.tool_class == "evidence_navigation" and typed_keys:
            raise ValueError(
                "evidence-navigation tools return evidence references and promote "
                "nothing; leave supported_proposition_types empty"
            )
        if self.tool_class == "research_proposal" and typed_keys:
            raise ValueError(
                "research-proposal tools emit a specification for an experiment "
                "nobody has run; a specification establishes nothing, so leave "
                "supported_proposition_types empty"
            )
        if self.tool_class == "research_proposal" and self.execution_authorized:
            raise ValueError(
                "research-proposal tools emit specifications only; set "
                "execution_authorized=False so no host can run one"
            )
        if self.tool_class == "research_proposal" and self.lane != "research":
            raise ValueError("research-proposal tools declare lane='research'")
        return self


class ToolNotInCatalog(KeyError):
    """A result named a tool card the catalog does not hold."""


class ToolCatalog(BaseModel):
    """The closed menu, at a version.

    The version is declared rather than derived from the contents so a
    result can name the menu it chose from. A hypothesis adjudicated
    under catalog ``1.2.0`` is not silently re-adjudicated by ``1.3.0``:
    the artifact header records which menu ran.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_version: str = Field(min_length=1)
    cards: tuple[ToolCard, ...] = ()

    @model_validator(mode="after")
    def _unique(self) -> ToolCatalog:
        keys = [card.key for card in self.cards]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate tool card(s) {duplicates} in one catalog")
        return self

    def card(self, tool_id: str, tool_version: str) -> ToolCard:
        for candidate in self.cards:
            if candidate.key == (tool_id, tool_version):
                return candidate
        raise ToolNotInCatalog(
            f"catalog {self.catalog_version} has no card for {tool_id}@{tool_version}; "
            "a result from a tool nobody declared cannot be scored"
        )


def tool_schemas(catalog: ToolCatalog) -> dict[str, dict[str, object]]:
    """Every card's request and result schema, keyed by path.

    One function so the exporter and the drift test read the same thing;
    a test that re-implements the export is a test that can agree with
    itself while disagreeing with what ships.
    """
    documents: dict[str, dict[str, object]] = {}
    for card in catalog.cards:
        documents[card.input_schema_ref] = card.io.request_schema(
            tool_id=card.tool_id, tool_version=card.tool_version
        )
        documents[card.output_schema_ref] = card.io.result_schema(
            tool_id=card.tool_id, tool_version=card.tool_version
        )
    return documents


def write_tool_schemas(catalog: ToolCatalog, root: Path) -> tuple[Path, ...]:
    """Write the generated schemas under ``root``. Returns what it wrote."""
    written = []
    for ref, document in sorted(tool_schemas(catalog).items()):
        path = root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return tuple(written)
