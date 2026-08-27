"""What a case is supposed to produce — kept where only the scorer reads it.

``VISIBLE_SUITE`` already carries the structural answer for each case:
the mechanism, the component, the checkers a competent analyst asks for,
and whether silence is the right answer. Three things it does not carry,
and W0 adds them here rather than there:

**Which citations count.** A ref written into a label as one exact
string is a label that fails a citation that is different and correct.
So refs are **predicates** — "any fact the packet attributes to this
subject", "any ref under this prefix" — and a proposal passes the
evidence check when at least one of its refs satisfies at least one
predicate.

**Which class the case is in before anybody runs it.**
``expected_check_required`` says whether a competent analyst has to ask
for a checker on this case. It is the stratum cost is reported by, and
it is decided from the fixture rather than from what the model chose,
because a stratum chosen after seeing the model's branch is a
post-treatment comparison.

**What the eval itself was.** ``EvalSpec.checksum`` hashes the labels'
*content* — not a version string somebody may forget to bump — plus the
distractor seed and rate and the scoring semantics. Two reports with
different checksums were not scored the same way, and no reader should
have to notice that by hand.

**And where none of this may go.** Labels are data under
``fixtures/golden/labels/``, which the analyst image does not copy, and
:func:`assert_no_label_in` is the test that a packet view — the bytes
the model sees — carries none of them. A label that reaches the prompt
is an answer key in the exam paper.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from planbench_analyst.packet_view import PacketView
from planbench_explanation.ledger import EvidenceRef
from planbench_explanation.propositions import PropositionType
from planbench_explanation.subjects import Subject
from planbench_explanation.versioning import artifact_checksum

__all__ = [
    "SCORING_SEMANTICS_VERSION",
    "CaseLabels",
    "EvalSpec",
    "EvalSpecRefusal",
    "RefPredicate",
    "assert_no_label_in",
    "load_eval_spec",
    "refs_satisfy",
]

#: Bumped when the way labels are *read* changes — what counts as a
#: mechanism match, how a predicate is applied. Inside the checksum so
#: two reports scored under different readings cannot share one.
SCORING_SEMANTICS_VERSION = "w0.1.0"

Partition = Literal["development", "confirmatory"]


class EvalSpecRefusal(ValueError):
    """Labels this harness will not score with."""


class RefPredicate(BaseModel):
    """One way a citation may count. Any-of across a label's predicates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The fact must be attributed to this component by the packet.
    subject: Subject | None = None
    #: The ref must start with this — ``obs:stuck_cluster:`` names every
    #: stuck-cluster observation whichever candidate it is on.
    ref_prefix: str = ""
    #: The fact's scope must start with this — ``candidate:`` for
    #: anything about one stack.
    scope_prefix: str = ""

    def matches(self, ref: EvidenceRef, view: PacketView) -> bool:
        fact = view.fact(ref.ref)
        if fact is None:
            return False
        if self.subject is not None and fact.subject != self.subject:
            return False
        if self.ref_prefix and not ref.ref.startswith(self.ref_prefix):
            return False
        return not self.scope_prefix or fact.scope.startswith(self.scope_prefix)


class CaseLabels(BaseModel):
    """The answer for one case. Scorer-side only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    expected_mechanism: PropositionType | None = None
    expected_subject: Subject | None = None
    #: Any-of. Empty means the label makes no claim about citations.
    acceptable_refs: tuple[RefPredicate, ...] = ()
    #: Tools a competent analyst may ask for. A request outside this set
    #: is not wrong by itself; it is what ``checker_selection`` counts.
    acceptable_tools: tuple[str, ...] = ()
    expect_abstention: bool = False
    #: Decided from the fixture, before any run: does this case need a
    #: checker to reach a verdict, or is the packet's own evidence enough?
    expected_check_required: bool = False
    #: Prose ceiling. ``associated`` for every proposal-stage label; kept
    #: on the record so a reviewer can see what wording was allowed.
    wording_ceiling: str = "associated"
    rationale: str = ""


class EvalSpec(BaseModel):
    """Every label the harness scores with, and the identity of the eval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suite_version: str = Field(min_length=1)
    partition: Partition = "development"
    labels: tuple[CaseLabels, ...]
    #: Eval-mode knobs. Zero rate means no distractor is injected, which
    #: is the production shape and the only shape a gate may run.
    distractor_seed: int = 0
    distractor_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    scoring_semantics_version: str = SCORING_SEMANTICS_VERSION

    def label_for(self, case_id: str) -> CaseLabels | None:
        return next((item for item in self.labels if item.case_id == case_id), None)

    @property
    def checksum(self) -> str:
        """Content, not version. A version string somebody forgot to bump
        would let two different label sets share one identity."""
        return artifact_checksum(
            {
                "suite_version": self.suite_version,
                "partition": self.partition,
                "labels": [item.model_dump(mode="json") for item in self.labels],
                "distractor_seed": self.distractor_seed,
                "distractor_rate": self.distractor_rate,
                "scoring_semantics_version": self.scoring_semantics_version,
            }
        )

    @property
    def strata(self) -> dict[str, tuple[str, ...]]:
        """Case ids by the class decided before any run."""
        return {
            "check_required": tuple(
                item.case_id for item in self.labels if item.expected_check_required
            ),
            "no_check_required": tuple(
                item.case_id for item in self.labels if not item.expected_check_required
            ),
        }


def refs_satisfy(refs: Iterable[EvidenceRef], label: CaseLabels, view: PacketView) -> bool:
    """Whether at least one citation meets at least one predicate.

    A label with no predicates makes no claim and is satisfied by any
    refs — including none — so a fixture that has not said what counts
    does not silently fail every proposal.
    """
    if not label.acceptable_refs:
        return True
    return any(predicate.matches(ref, view) for ref in refs for predicate in label.acceptable_refs)


def load_eval_spec(path: Path) -> EvalSpec:
    """Read labels from a file the analyst image never receives.

    Refuses a confirmatory partition outright: the confirmatory set is
    the hidden suite behind ``run_gate``, and a label file that claimed
    to be it would be an answer key for a set nobody is meant to see.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as broken:
        raise EvalSpecRefusal(f"{path}: {broken}") from broken
    spec = EvalSpec.model_validate(payload)
    if spec.partition != "development":
        raise EvalSpecRefusal(
            f"{path} claims partition {spec.partition!r}; labels for the confirmatory "
            "set live behind the hidden gate, not in a file this harness reads"
        )
    return spec


def assert_no_label_in(view: PacketView, spec: EvalSpec) -> None:
    """The bytes the model sees carry no answer.

    Checks the strings a label would leak as — the expected mechanism
    and subject as a pair, the rationale — against the packet view's
    serialisation. Mechanism names alone appear legitimately in the
    catalog text, so the pair is what is looked for.
    """
    text = view.serialize()
    label = spec.label_for(view.packet.run_id)
    if label is None:
        return
    if label.rationale and label.rationale in text:
        raise EvalSpecRefusal(
            f"{label.case_id}: the label's rationale is inside the packet view; the "
            "model would be reading the answer key"
        )
    if label.expected_mechanism and label.expected_subject:
        pair = json.dumps(
            {
                "expected_mechanism": label.expected_mechanism,
                "expected_subject": label.expected_subject,
            }
        )
        if pair in text:
            raise EvalSpecRefusal(
                f"{label.case_id}: the expected finding is inside the packet view"
            )


def spec_from_mapping(payload: Mapping[str, Any]) -> EvalSpec:
    """For tests and builders: the same validation, no file."""
    return EvalSpec.model_validate(dict(payload))
