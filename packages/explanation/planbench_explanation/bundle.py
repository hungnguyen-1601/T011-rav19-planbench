"""The analyst as a frozen artifact, and the gate that lets one be shown — E5.

**The unit under evaluation is a bundle, not an endpoint.** An endpoint
the AI team operates can log the hidden packets it is given, change its
prompt between cases, deploy new code halfway through a gate run, or
recognise that it is being graded and behave differently for the
occasion. A report produced from one is not reproducible, and a
reproducible number is the entire point of a gate. So what is submitted
is a description of a frozen configuration — code digest, container
digest, model and revision, prompt checksum, retrieval index and config,
catalog version, generation parameters — and the platform runs *that*,
in an environment the platform controls, with credentials the platform
holds.

:attr:`AnalystBundle.identity_checksum` is what a gate decision is
recorded against. Change the prompt by one character and the checksum
moves, so the decision no longer refers to the thing now running. That
is the whole mechanism behind "a new version needs a new gate": nothing
has to notice the change, because the old decision simply stops
matching.

**Residual risks, stated rather than implied away.** Two survive this
design and pretending otherwise would be worse than the risks:

*The hidden packets still leave the platform.* The model is an external
API, so whatever the platform sends, the vendor receives. Freezing the
bundle does not change that. The mitigation is rotation — a hidden
subset is opened once and never reused — not secrecy.

*A bundle does not make an API model deterministic.* Same prompt, same
parameters, different sampling. The bundle freezes everything the
platform can freeze; the part it cannot is measured with repeated runs
rather than assumed away.

**The feature flag is downstream of the decision, not beside it.**
:func:`analyst_visible` takes the bundle, the decision and the
**preregistered targets** and answers whether the button may appear.
There is no boolean anybody can set: an analyst with no decision, a
decision for a different build, a decision that did not pass, or a
decision graded against a different bar is not shown. Written as one
function so there is one answer and not one per call site.

**A decision must carry the whole bar, and may not choose it.** The
first version derived ``passed`` from "every metric present has cleared",
which meant a decision holding one flattering metric passed — the five
that would have failed were simply absent, and the flag came on. Two
rules close it. :data:`REQUIRED_GATE_METRICS` must all be present, so a
decision cannot be silent about a metric. And the threshold and
direction of each are re-derived from a :class:`MetricTargets` the
caller supplies, so a decision cannot come with a bar of its own
choosing: :func:`verify_gate_decision` rebuilds every row from the
measured values and refuses the file if what it rebuilds differs. Same
lesson as the claim ledger — a self-describing artifact judged by its
own description is not judged.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.budget import AnalysisBudget
from planbench_explanation.versioning import (
    CHECKSUM_PATTERN,
    CODE_REF_PATTERN,
    artifact_checksum,
    validate_code_ref,
)

#: A container digest, the one shape an image is named by.
CONTAINER_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"

#: RFC 3339 UTC, seconds precision. Timestamps are strings here because
#: the bundle is a wire artifact and a parsed datetime would serialise
#: back differently on different platforms — which would move the
#: identity checksum without anything changing.
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


#: Every metric a gate decision must report. Not "the ones that were
#: measured" — a gate is the whole bar or it is a selection somebody
#: made after seeing the numbers.
REQUIRED_GATE_METRICS: tuple[str, ...] = (
    "structural_violations",
    "precision",
    "recall_at_3",
    "abstention",
    "component_attribution",
    "checker_selection",
)


class BundleRefusal(ValueError):
    """A bundle that cannot be run, or a gate decision that cannot be trusted."""


class AnalystBundle(BaseModel):
    """A frozen analyst configuration the platform can run and re-run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str = Field(min_length=1)
    #: ``git:<40 hex>`` or ``sha256:<64 hex>`` — the analyst's own code.
    agent_code_digest: str = Field(pattern=CODE_REF_PATTERN)
    #: The image it runs in. Code without an image is code whose
    #: dependencies moved between the calibration run and the gate.
    container_digest: str = Field(pattern=CONTAINER_DIGEST_PATTERN)
    model_id: str = Field(min_length=1)
    #: The provider's own build string. ``model_id`` alone is a moving
    #: target: providers re-point an alias and the same name answers
    #: differently.
    model_revision: str = Field(min_length=1)
    prompt_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    rag_index_version: str = Field(min_length=1)
    retrieval_config_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    tool_catalog_version: str = Field(min_length=1)
    #: Temperature, top-p, seed if the provider honours one. Part of the
    #: identity: the same prompt at temperature 1.0 is a different
    #: system from the same prompt at 0.0.
    generation_parameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    #: Wire protocol between the platform's runner and the analyst it
    #: drives. Part of the identity: a bundle built against one frame
    #: set and run against another is a different system, and the
    #: symptom of getting it wrong is a round that dies half way with a
    #: frame nobody recognises.
    runner_protocol_version: str = Field(min_length=1)
    #: **The object, not a checksum of it.** A bundle carrying only a
    #: digest of its limits cannot be re-run from itself: somebody has
    #: to find the budget that hashes to that value, and that somebody
    #: is the party being graded. Embedded, the bundle describes itself
    #: completely — and the checksum below still identifies it.
    requested_budget: AnalysisBudget
    created_at: str = Field(pattern=TIMESTAMP_PATTERN)

    #: Which revision of the algorithm-trait catalog this bundle was
    #: graded against, and where the document is. **Three fields, not
    #: one** (W1.8): a checksum alone pins a value nobody can produce a
    #: document for once the table's current pointer has moved, which
    #: reads as pinned and cannot be replayed. Empty on a bundle that
    #: was graded with the traits input off — absent rather than blank,
    #: since "no traits" and "traits nobody recorded" differ.
    traits_revision_id: str = ""
    traits_snapshot_checksum: str = ""
    #: Content-addressed: the checksum is in the path, so an artifact
    #: edited in place stops being findable instead of quietly standing
    #: in for the one that was graded.
    traits_snapshot_ref: str = ""

    @model_validator(mode="after")
    def _check(self) -> AnalystBundle:
        validate_code_ref(self.agent_code_digest, field="agent_code_digest")
        triple = (
            self.traits_revision_id,
            self.traits_snapshot_checksum,
            self.traits_snapshot_ref,
        )
        if any(triple) and not all(triple):
            raise BundleRefusal(
                "a trait snapshot is a revision id, a content checksum and a ref, "
                f"and this bundle carries {sum(1 for item in triple if item)} of the "
                "three. Each one alone can be true while the pair is wrong: a ref "
                "that resolves to another revision, a checksum matching a document "
                "the bundle does not name, an id that was reused."
            )
        if self.traits_snapshot_checksum and not re.fullmatch(
            CHECKSUM_PATTERN, self.traits_snapshot_checksum
        ):
            raise BundleRefusal(
                f"traits_snapshot_checksum {self.traits_snapshot_checksum!r} is not a "
                "sha-256 hex digest"
            )
        return self

    @property
    def identity(self) -> dict[str, object]:
        """Everything that makes this bundle the system it is.

        ``bundle_id`` and ``created_at`` are deliberately outside: they
        are labels for a configuration, and two submissions of the same
        configuration under different ids are the same system and should
        checksum the same.
        """
        return {
            "agent_code_digest": self.agent_code_digest,
            "container_digest": self.container_digest,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "prompt_checksum": self.prompt_checksum,
            "rag_index_version": self.rag_index_version,
            "retrieval_config_checksum": self.retrieval_config_checksum,
            "tool_catalog_version": self.tool_catalog_version,
            "generation_parameters": self.generation_parameters,
            "runner_protocol_version": self.runner_protocol_version,
            "requested_budget": self.requested_budget.checksum,
            # All three, because the gate checks all three. A bundle
            # that pinned only the checksum would be replayable exactly
            # as long as nobody edited the table.
            "traits_revision_id": self.traits_revision_id,
            "traits_snapshot_checksum": self.traits_snapshot_checksum,
            "traits_snapshot_ref": self.traits_snapshot_ref,
        }

    @property
    def identity_checksum(self) -> str:
        """What a gate decision is recorded against."""
        return artifact_checksum(self.identity)

    def runs_catalog(self, catalog_version: str) -> bool:
        """Whether this bundle was frozen against the menu now being served."""
        return self.tool_catalog_version == catalog_version


class MetricResult(BaseModel):
    """One measured number and the threshold it was judged against."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: str = Field(min_length=1)
    value: float
    threshold: float
    #: ``at_least`` for a rate to clear, ``at_most`` for a count to stay
    #: under. Spelled out because a bare number plus a name is a
    #: comparison direction somebody has to remember.
    direction: str = Field(pattern=r"^(at_least|at_most)$")

    @property
    def met(self) -> bool:
        if self.direction == "at_least":
            return self.value >= self.threshold
        return self.value <= self.threshold


class MetricTargets(BaseModel):
    """The bar: which metrics, at what level, in which direction.

    Lives beside the gate rather than beside the scorer because it is
    what a decision is checked against, and because
    :meth:`evaluate` takes a plain mapping of measured values — the
    scorer produces one, and this module does not need to know what a
    scoreboard is.

    Structural invariants are absolute; the rest are the design's
    calibration targets, written down so the negotiation starts from a
    number that predates anybody's score.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    precision: float = 0.90
    recall_at_3: float = 0.70
    abstention: float = 0.90
    component_attribution: float = 0.85
    checker_selection: float = 0.90
    max_structural_violations: int = 0

    @property
    def checksum(self) -> str:
        """Identifies the bar. A decision names the one it was judged by."""
        return artifact_checksum(self.model_dump(mode="json"))

    def threshold_for(self, metric: str) -> tuple[float, str]:
        if metric == "structural_violations":
            return (float(self.max_structural_violations), "at_most")
        if metric not in REQUIRED_GATE_METRICS:
            raise BundleRefusal(f"{metric!r} is not a gate metric")
        return (float(getattr(self, metric)), "at_least")

    def evaluate(self, values: Mapping[str, float | None]) -> tuple[MetricResult, ...]:
        """Rows for every required metric, in the canonical order.

        A statistical metric the run did not measure scores ``0.0``
        against its threshold rather than being skipped. A gate that
        quietly drops what it could not measure is a gate passed by
        submitting a suite that measures nothing.

        **A counted invariant is the opposite case and must be
        supplied.** ``structural_violations`` is judged ``at_most`` zero,
        so substituting ``0.0`` for "nobody measured this" produces
        "there were no violations" — the harness never looked and the
        gate records a clean sheet. The direction of the comparison
        decides which way an absence should fail, and for this one an
        absence must fail loudly rather than pass silently.
        """
        missing = [
            metric
            for metric in REQUIRED_GATE_METRICS
            if self.threshold_for(metric)[1] == "at_most" and values.get(metric) is None
        ]
        if missing:
            raise BundleRefusal(
                f"{missing} were not measured. They are counted invariants judged "
                "at_most, so treating an absence as zero would record 'no violations' "
                "for a run nobody checked. Measure them or do not run the gate."
            )
        rows = []
        for metric in REQUIRED_GATE_METRICS:
            threshold, direction = self.threshold_for(metric)
            measured = values.get(metric)
            rows.append(
                MetricResult(
                    metric=metric,
                    value=0.0 if measured is None else float(measured),
                    threshold=threshold,
                    direction=direction,  # type: ignore[arg-type]
                )
            )
        return tuple(rows)


#: The design's calibration targets. Not frozen until the platform
#: preregisters them against a hidden suite version.
CALIBRATION_TARGETS = MetricTargets()


class GateDecision(BaseModel):
    """The platform's record of running one bundle against a hidden suite.

    Pass is not a field anybody sets, and it is not a property either:
    :meth:`passes` takes the preregistered targets and re-derives the
    comparison, because a decision's own account of the bar it cleared
    is the part under suspicion. :attr:`internally_passed` exists for
    the narrow question "is this file self-consistent" and is named so a
    caller reaching for it by mistake notices.

    The preregistration reference is required because a threshold agreed
    after the numbers were seen is not a threshold.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    bundle_id: str = Field(min_length=1)
    #: The identity the decision is about. Compared against a live
    #: bundle's :attr:`AnalystBundle.identity_checksum`; a mismatch means
    #: the thing that was graded is not the thing about to run.
    bundle_identity_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    hidden_suite_version: str = Field(min_length=1)
    preregistration_ref: str = Field(min_length=1)
    #: Which bar this was judged against. Checked against the targets a
    #: caller supplies, so a decision cannot arrive carrying thresholds
    #: of its own and be believed.
    targets_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    decided_at: str = Field(pattern=TIMESTAMP_PATTERN)
    #: The budget the graded round actually ran under — the field-wise
    #: minimum of what the bundle asked for and what the platform pays
    #: for. Recorded because calibration, gate and production must all
    #: run under the same one: an analyst graded with twice the tool
    #: calls it gets in production was graded as a system that does not
    #: exist.
    effective_budget_checksum: str = Field(pattern=CHECKSUM_PATTERN)
    metrics: tuple[MetricResult, ...]
    #: Free text for the person reading the decision later. Never read
    #: by :func:`analyst_visible`.
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> GateDecision:
        names = [metric.metric for metric in self.metrics]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise BundleRefusal(f"metric(s) {duplicates} recorded twice in one decision")
        missing = sorted(set(REQUIRED_GATE_METRICS) - set(names))
        if missing:
            raise BundleRefusal(
                f"gate decision is silent about {missing}. A decision reporting only "
                "the metrics that cleared is a selection made after the numbers were "
                "seen, and it would pass on the strength of what it left out."
            )
        extra = sorted(set(names) - set(REQUIRED_GATE_METRICS))
        if extra:
            raise BundleRefusal(
                f"gate decision reports {extra}, which the preregistered bar does not "
                "define; a metric invented at grading time is a metric chosen to be met"
            )
        return self

    @property
    def failed_metrics(self) -> tuple[str, ...]:
        return tuple(metric.metric for metric in self.metrics if not metric.met)

    @property
    def internally_passed(self) -> bool:
        """Whether the decision's own arithmetic agrees with itself.

        **Not the answer to "did this analyst pass".** It compares each
        recorded value against the threshold recorded beside it, and a
        decision carrying a threshold of its own choosing agrees with
        itself perfectly. Named to be awkward: a caller reaching for it
        where :meth:`passes` belongs should notice.
        """
        return not self.failed_metrics

    def passes(self, targets: MetricTargets) -> bool:
        """Did this analyst clear the preregistered bar. The public answer.

        Verifies first — thresholds and directions re-derived from
        ``targets`` — and only then reads the comparison.
        """
        try:
            verify_gate_decision(self, targets=targets)
        except BundleRefusal:
            return False
        return self.internally_passed


def verify_gate_decision(
    decision: GateDecision,
    *,
    targets: MetricTargets,
    effective_budget: AnalysisBudget | None = None,
) -> None:
    """Re-derive every row from the measured values and the caller's bar.

    The trust boundary is the ``targets`` argument. A decision states
    what it measured *and* what it measured against, and only the first
    of those is evidence: thresholds and directions are rebuilt here, so
    a decision whose ``precision`` row quietly carries a threshold of
    0.10 fails rather than passes.

    Raises rather than returning a bool because there is nothing a
    caller should do with a decision that fails this except refuse it.
    """
    if effective_budget is not None and decision.effective_budget_checksum != (
        effective_budget.checksum
    ):
        raise BundleRefusal(
            "the gate decision was earned under a different effective budget than the "
            "one now in force; a bundle graded with more tool calls, more model calls "
            "or a longer deadline than production gives it was graded as a system "
            "that does not exist. Re-run the gate under the budget production uses."
        )
    if decision.targets_checksum != targets.checksum:
        raise BundleRefusal(
            "the gate decision was judged against a different bar than the one "
            "supplied; thresholds are preregistered and a decision cannot bring its own"
        )
    measured = {metric.metric: metric.value for metric in decision.metrics}
    rebuilt = {row.metric: row for row in targets.evaluate(measured)}
    for stored in decision.metrics:
        fresh = rebuilt[stored.metric]
        if (stored.threshold, stored.direction) != (fresh.threshold, fresh.direction):
            raise BundleRefusal(
                f"{stored.metric}: the decision applied {stored.direction} "
                f"{stored.threshold} but the preregistered bar is {fresh.direction} "
                f"{fresh.threshold}"
            )


def analyst_visible(
    bundle: AnalystBundle,
    decision: GateDecision | None,
    *,
    catalog_version: str,
    targets: MetricTargets,
    production_budget: AnalysisBudget | None = None,
) -> bool:
    """Whether the "explain why" affordance may appear for this analyst.

    Five ways to be invisible and one way to be visible. The default is
    invisible: an analyst nobody has graded does not appear on a
    decision card, and neither does one graded in a configuration that
    has since changed or against a bar nobody preregistered.
    """
    return (
        why_not_visible(
            bundle,
            decision,
            catalog_version=catalog_version,
            targets=targets,
            production_budget=production_budget,
        )
        is None
    )


def why_not_visible(
    bundle: AnalystBundle,
    decision: GateDecision | None,
    *,
    catalog_version: str,
    targets: MetricTargets,
    production_budget: AnalysisBudget | None = None,
) -> str | None:
    """The reason the flag is off, for an operator. ``None`` when it is on.

    The single place the rule lives; :func:`analyst_visible` is this
    function with the reason thrown away, so the two cannot drift into
    disagreeing about whether a given analyst is shown.
    """
    if decision is None:
        return "no gate decision exists for this analyst"
    if decision.bundle_identity_checksum != bundle.identity_checksum:
        return (
            "the gate decision was made about a different configuration; re-run the "
            "gate against the bundle now deployed"
        )
    try:
        verify_gate_decision(decision, targets=targets, effective_budget=production_budget)
    except BundleRefusal as error:
        return str(error)
    if not decision.passes(targets):
        return f"the gate decision did not pass: {list(decision.failed_metrics)}"
    if not bundle.runs_catalog(catalog_version):
        return (
            f"the bundle was frozen against tool catalog "
            f"{bundle.tool_catalog_version!r} but the platform now serves "
            f"{catalog_version!r}"
        )
    return None


def canonical_timestamp(value: str) -> str:
    """Check a bundle timestamp, or say what shape was expected."""
    if not re.fullmatch(TIMESTAMP_PATTERN, value):
        raise BundleRefusal(
            f"{value!r} is not an RFC 3339 UTC timestamp to the second "
            "(2026-08-19T09:30:00Z). Bundle timestamps are part of a wire artifact, "
            "so one written a second way is a different string for the same moment."
        )
    return value
