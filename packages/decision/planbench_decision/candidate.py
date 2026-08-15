"""Candidate: the unit that gets benchmarked (CONTRACTS HĐ-1).

> The unit under test is a complete navigation configuration, not "an
> algorithm".

A\\* and RRT\\* are global planners; DWA is a local controller. They solve
different problems, do not substitute for one another, and must never
share a ranking table — "DWA beats A\\*" is a methodological error, not a
result. So the thing this platform ranks is a *stack*: global planner +
local controller + parameters + code version + observation requirements.
End-to-end policies are the second legal shape: no layers, one policy.

Two properties of this module carry the whole comparison downstream.

**Identity is derived, never assigned.** ``candidate_id`` is a hash of
everything that changes behaviour. Two candidates differing in *any*
parameter are two independent candidates — ``A* + DWA(config_A)`` and
``A* + DWA(config_B)`` may both reach the final. This is one of the three
contracts frozen after week 1 (CONTRACTS §0): every trace, every paired
ΔU and every Decision Card references this id, so changing how it is
computed orphans all recorded data.

**Experiment scope is checked, not trusted.** Declaring
``global_planner_selection`` while the candidates differ in their DWA
parameters would let a report conclude something about A\\* from evidence
that also varied the controller. :func:`validate_experiment_scope` fails
at startup on that, as HĐ-1.4 requires — a warning would be read as
noise by exactly the person who needs to stop.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from planbench_schemas.identity import canonical_json, sha256_short
from planbench_schemas.observations import ObservationToken, canonical_observations

#: Length of the hex digest kept as an id (HĐ-1.3).
CANDIDATE_ID_LENGTH = 12

CandidateType = Literal["modular", "monolithic"]

#: What a run is allowed to conclude (HĐ-1.4). Printed on every Decision
#: Card, because the same numbers support different sentences depending
#: on what was held fixed.
ExperimentScope = Literal[
    "global_planner_selection",
    "local_controller_selection",
    "full_stack_selection",
]


class CandidateSchemaError(ValueError):
    """A candidate that does not describe a runnable configuration."""


class ExperimentScopeViolation(ValueError):
    """The candidate set cannot support the declared scope.

    Raised at startup rather than reported at the end: by the time the
    numbers exist, the wrong comparison has already been paid for.
    """


class StackComponent(BaseModel):
    """One layer of a modular stack: which implementation, which version.

    ``version`` is part of the identity on purpose. The same DWA after a
    bug fix is a different candidate, and a report that cannot tell the
    two apart cannot be reproduced.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(default="v1", min_length=1)


class StructuralResourceProfile(BaseModel):
    """Memory declared as *counts × sizes* — the classical-planner case.

    What decides a classical planner's memory is how many nodes and cells
    it holds, and that is algorithm behaviour: the simulator counts it
    exactly, in any language. The per-item sizes are declared for the
    *target* implementation (C++/ROS2), never for Python — which is the
    whole reason this profile exists instead of measuring RSS (HĐ-7.3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["structural"]
    target_implementation: str = Field(
        min_length=1,
        description="Implementation the byte sizes describe, e.g. cpp_ros2.",
    )
    bytes_per_search_node: int = Field(gt=0)
    bytes_per_tree_node: int = Field(gt=0)
    bytes_per_costmap_cell: int = Field(gt=0)
    costmap_layers: int = Field(gt=0)
    fixed_overhead_mb: float = Field(ge=0)


class ArtifactResourceProfile(BaseModel):
    """Memory declared as *weights + runtime* — the learned-policy case.

    A simulator cannot count this: the footprint is the checkpoint plus
    whatever the inference runtime allocates. It is, however, knowable in
    advance, so the author declares it at registration. ``source`` keeps
    the epistemic status attached to the number — with ``declared`` the
    G5 result may only *reject*, never certify (HĐ-7.3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["artifact"]
    model_artifact_mb: float = Field(gt=0)
    runtime_footprint_mb: float = Field(gt=0)
    source: Literal["declared", "measured_on_target"] = "declared"


#: HĐ-1.5. Tagged by ``kind`` so a malformed profile fails at parse with
#: the field named, rather than matching the other shape by accident.
ResourceProfile = Annotated[
    StructuralResourceProfile | ArtifactResourceProfile,
    Field(discriminator="kind"),
]


class TuningDeclaration(BaseModel):
    """What this configuration cost to find (HĐ-1.6).

    These three numbers are the only inputs to the system that are
    *self-reported* and go straight into a score: ``tuning_wall_clock_h``
    is ``engineering_cost`` in O4's technical mode, and
    ``n_tunable_params`` is the third tie-break of HĐ-11.3. That is why
    ``evidence_log`` is required rather than optional — a candidate
    claiming zero tuning hours is claiming an advantage, and a claim with
    no log behind it is a claim nobody can check.

    Nothing here enters ``candidate_id``: the hours spent searching for a
    parameter set do not change how the robot drives. The parameter set
    found does, and it is already hashed through ``params``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tuning_trials_used: int = Field(ge=0)
    tuning_wall_clock_h: float = Field(ge=0)
    n_tunable_params: int = Field(ge=0)
    evidence_log: str = Field(
        min_length=1,
        description="Path or URI of the log that backs these figures.",
    )


class PolicyComponent(BaseModel):
    """The single layer of a monolithic candidate (RL end-to-end)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    checkpoint: str = Field(min_length=1, description="Which trained weights ran.")
    version: str = Field(default="v1", min_length=1)


class Candidate(BaseModel):
    """A complete navigation configuration under test (HĐ-1.2).

    Identity is :attr:`candidate_id` and nothing else. The contract's YAML
    carries ``id: null`` as a reminder of that, so both ``id`` and a
    serialised ``candidate_id`` are accepted on input and discarded —
    which keeps ``model_validate(candidate.model_dump())`` working, the
    round trip every stored candidate and manifest depends on. Verifying
    an id somebody wrote down is :func:`load_candidate`'s job.

    Unknown fields are refused: ``global_plannr`` would otherwise parse as
    a monolithic-shaped candidate with a missing layer, and the error
    would point at the wrong thing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: CandidateType
    global_planner: StackComponent | None = None
    local_controller: StackComponent | None = None
    policy: PolicyComponent | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    observation_requirements: tuple[ObservationToken, ...] = ()
    resource_profile: ResourceProfile
    #: HĐ-1.6. Defaults to undeclared: a candidate without it still runs
    #: episodes and still passes gates. It cannot be *scored* on O4, and
    #: the objective layer refuses rather than substituting zero —
    #: treating "not declared" as "cost nothing" would let the candidate
    #: that skipped the paperwork win the cheapest-to-own objective.
    tuning: TuningDeclaration | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_declared_identity(cls, value: object) -> object:
        """Discard author-written identity; the hash is the identity."""
        if isinstance(value, dict) and ("id" in value or "candidate_id" in value):
            return {k: v for k, v in value.items() if k not in {"id", "candidate_id"}}
        return value

    @field_validator("observation_requirements", mode="before")
    @classmethod
    def _canonical_requirements(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return canonical_observations(
                (entry for entry in value if isinstance(entry, str)),
                field="observation_requirements",
            )
        return value

    @model_validator(mode="after")
    def _validate_shape(self) -> Candidate:
        """Enforce the two legal shapes; reject the mixtures.

        HĐ-1.2 states the rejection direction explicitly: a monolithic
        candidate has no global planner or local controller, and the
        loader must refuse one that declares them. The reverse case
        matters just as much — a modular candidate missing a layer is not
        runnable, and finding that out at episode 1 of 300 wastes the run.
        """
        if self.type == "monolithic":
            declared = [
                name
                for name, value in (
                    ("global_planner", self.global_planner),
                    ("local_controller", self.local_controller),
                )
                if value is not None
            ]
            if declared:
                raise CandidateSchemaError(
                    f"monolithic candidate must not declare {declared}: an end-to-end "
                    "policy has no layers to configure separately"
                )
            if self.policy is None:
                raise CandidateSchemaError("monolithic candidate requires a policy")
            if self.resource_profile.kind != "artifact":
                raise CandidateSchemaError(
                    "monolithic candidate needs resource_profile.kind='artifact': its "
                    "memory is model weights plus an inference runtime, which the "
                    "simulator cannot count from data-structure sizes (HĐ-7.3)"
                )
        else:
            if self.policy is not None:
                raise CandidateSchemaError(
                    "modular candidate must not declare a policy; use type=monolithic "
                    "for an end-to-end policy"
                )
            missing = [
                name
                for name, value in (
                    ("global_planner", self.global_planner),
                    ("local_controller", self.local_controller),
                )
                if value is None
            ]
            if missing:
                raise CandidateSchemaError(f"modular candidate requires {missing}")
            if self.resource_profile.kind != "structural":
                raise CandidateSchemaError(
                    "modular candidate needs resource_profile.kind='structural': the "
                    "simulator counts its nodes and cells exactly, so declaring a "
                    "footprint instead would skip a measurement that exists (HĐ-7.3)"
                )
            self._validate_modular_params()
        return self

    def _validate_modular_params(self) -> None:
        """Every parameter block must belong to a declared layer.

        A ``params.dwa`` block on a stack whose controller is ``mppi`` is
        never read, yet it changes the candidate id: two candidates that
        behave identically would be scored, compared and reported as
        rivals. Silent no-ops are worse here than a refusal to start.
        """
        assert self.global_planner is not None and self.local_controller is not None
        known = {self.global_planner.name, self.local_controller.name}
        unknown = sorted(set(self.params) - known)
        if unknown:
            raise CandidateSchemaError(
                f"params block(s) {unknown} match no layer of this stack "
                f"(layers: {sorted(known)}); a block nothing reads would still change "
                "the candidate id"
            )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def candidate_id(self) -> str:
        """Hash of everything that changes behaviour (HĐ-1.3).

        Included: type, stack (names and versions), parameters,
        observation requirements. Excluded: the author-supplied ``id``
        itself, which would make the hash self-referential, and the two
        accounting blocks ``resource_profile`` (HĐ-1.5) and ``tuning``
        (HĐ-1.6) — restating ``bytes_per_search_node`` for a different
        target implementation, or attaching the tuning log afterwards,
        changes no robot behaviour, and hashing either would split one
        candidate that already ran 300 episodes into two orphans over a
        bookkeeping edit.
        """
        return sha256_short(
            canonical_json(
                {
                    "type": self.type,
                    "stack": self._stack_payload(),
                    "params": self.params,
                    "observation_requirements": list(self.observation_requirements),
                }
            ),
            length=CANDIDATE_ID_LENGTH,
        )

    def _stack_payload(self) -> dict[str, Any]:
        if self.type == "monolithic":
            assert self.policy is not None
            return {"policy": self.policy.model_dump(mode="json")}
        assert self.global_planner is not None and self.local_controller is not None
        return {
            "global_planner": self.global_planner.model_dump(mode="json"),
            "local_controller": self.local_controller.model_dump(mode="json"),
        }

    @property
    def stack_label(self) -> str:
        """Human-readable stack, for cards and logs — never an identity.

        Two candidates differing only in parameters share this label,
        which is exactly why identity is the hash and not this string.
        """
        if self.type == "monolithic":
            assert self.policy is not None
            return f"{self.policy.name}@{self.policy.checkpoint}"
        assert self.global_planner is not None and self.local_controller is not None
        return f"{self.global_planner.name}+{self.local_controller.name}"

    def layer_params(self, layer: str) -> dict[str, Any]:
        """Parameter block for one layer; empty dict when defaulted."""
        value = self.params.get(layer, {})
        return dict(value) if isinstance(value, dict) else {}


def load_candidate(payload: Mapping[str, Any]) -> Candidate:
    """Parse a candidate and verify any id the author wrote down.

    :class:`Candidate` itself discards ``id``/``candidate_id`` so that a
    dumped model reloads unchanged. That leaves one gap worth closing at
    the edge: a YAML file carrying a hash copied from an earlier version
    of the configuration. Loading it silently would label the new
    configuration with the old id, and every trace, ΔU and Decision Card
    written afterwards would point at a candidate that never ran.

    ``id: null`` — the form the contract's own example uses — is fine.
    """
    candidate = Candidate.model_validate(payload)
    for key in ("id", "candidate_id"):
        declared = payload.get(key)
        if declared is not None and declared != candidate.candidate_id:
            raise CandidateSchemaError(
                f"declared {key} {declared!r} does not match this configuration "
                f"(computed {candidate.candidate_id!r}); leave it null and let it be derived"
            )
    return candidate


def _layer_fingerprint(candidate: Candidate, layer: Literal["global", "local"]) -> str:
    """Canonical text for one layer plus the parameters that drive it.

    Scope checking compares layers, so it needs a comparison that
    includes the parameters: two candidates both running ``dwa`` are not
    holding the controller fixed if one of them retuned it.
    """
    component = candidate.global_planner if layer == "global" else candidate.local_controller
    assert component is not None
    return canonical_json(
        {
            "component": component.model_dump(mode="json"),
            "params": candidate.layer_params(component.name),
        }
    )


def validate_experiment_scope(scope: ExperimentScope, candidates: Sequence[Candidate]) -> None:
    """Refuse a candidate set that cannot support the declared scope.

    HĐ-1.4: ``global_planner_selection`` requires the local controller
    *and its parameters* to be identical everywhere; the mirror rule
    holds for ``local_controller_selection``. ``full_stack_selection``
    constrains nothing — it also licenses no conclusion about any single
    layer, which is enforced by what the Decision Card is allowed to
    print rather than here.

    A monolithic candidate cannot take part in a layer-scoped run: it has
    no layer to hold fixed, so no sentence about "the global planner"
    could cover it.

    Raises :class:`ExperimentScopeViolation`; callers must not downgrade
    this to a warning.
    """
    if not candidates:
        raise ExperimentScopeViolation("a comparison needs at least one candidate")

    seen: dict[str, int] = {}
    for index, candidate in enumerate(candidates):
        previous = seen.setdefault(candidate.candidate_id, index)
        if previous != index:
            raise ExperimentScopeViolation(
                f"candidate {candidate.candidate_id} appears twice "
                f"(positions {previous} and {index}); the same configuration cannot "
                "be its own rival"
            )

    if scope == "full_stack_selection":
        return

    fixed_layer: Literal["global", "local"] = (
        "local" if scope == "global_planner_selection" else "global"
    )
    monolithic = [c.candidate_id for c in candidates if c.type == "monolithic"]
    if monolithic:
        raise ExperimentScopeViolation(
            f"scope {scope} holds the {fixed_layer} layer fixed, but monolithic "
            f"candidate(s) {monolithic} have no layers; run these under "
            "full_stack_selection"
        )

    fingerprints = {_layer_fingerprint(c, fixed_layer): c.candidate_id for c in candidates}
    if len(fingerprints) > 1:
        raise ExperimentScopeViolation(
            f"scope {scope} requires an identical {fixed_layer} layer (component, "
            f"version and parameters) in every candidate, found "
            f"{len(fingerprints)} variants across {sorted(fingerprints.values())}"
        )
