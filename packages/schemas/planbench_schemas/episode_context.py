"""Episode context: the conditions one episode runs under (HĐ-3).

An episode context is *what varies between episodes* with the candidate
held out of it: which deployment, which mission, which environment
variant, which seed. It exists so a comparison can be paired.

> Every candidate in one comparison must run on exactly the same set of
> ``episode_context_id``.

That rule is the reason paired bootstrap works at all (HĐ-11.2): because
the candidates faced identical conditions, most of the variance is shared
and cancels in the difference. Break the rule and the difference is
measuring the conditions, not the candidates — so the Decision Engine
refuses to compute ΔU rather than computing a wrong one (see
:mod:`planbench_decision.pairing`).

**The seed is the whole source of randomness.** Everything stochastic in
an episode — dynamic-obstacle placement and trajectories, and any sensor
or odometry noise added later — must derive from
:attr:`EpisodeContext.seed`, never from process-global randomness. Today
this holds by construction: the only randomised components are
``position_at`` (seeded from ``Scenario.random_seed``) and
``RRTStarPlanner`` (seeded from its config plus the episode seed). No
module in the simulator or planners draws from ``random`` or an unseeded
``np.random``, so replaying a context id reproduces the episode.

This is one of the three identities frozen after week 1 (CONTRACTS §0):
trace files, paired statistics and manifests all key on it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from planbench_schemas.identity import canonical_json, sha256_short

#: Length of the hex digest kept as an id (HĐ-3.1).
EPISODE_CONTEXT_ID_LENGTH = 12

#: Which of the two sample sets an episode belongs to (HĐ-3.3).
#:
#: - ``evaluation``: independent draws over mission × obstacle realisation
#:   × seed. The *only* set that may estimate success rate, the collision
#:   upper bound and any performance distribution.
#: - ``neighborhood``: structured perturbations around the nominal
#:   profile. Measures whether the *recommendation* holds up, nothing
#:   else. Runs within one variant are correlated, so pooling them into a
#:   rule-of-three bound would make ``3/N`` far too optimistic (HĐ-11.4).
SampleSet = Literal["evaluation", "neighborhood"]

#: The unperturbed environment. Evaluation episodes always run here.
NOMINAL_VARIANT = "nominal"


class EpisodeContext(BaseModel):
    """One set of episode conditions, identified by its hash (HĐ-3.1).

    ``sample_set`` is *not* part of the hash: HĐ-3.1 fixes the hashed
    payload as task profile, mission, environment variant and seed, and an
    id computed from anything else would not match one computed by
    another implementation of the same contract. The set stays reachable
    as a field — HĐ-5 records it in trace metadata — and it cannot
    disagree with the variant, because the two are constrained to move
    together (see :meth:`_validate_sample_set`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_profile_id: str = Field(min_length=1)
    mission_id: str = Field(min_length=1)
    seed: int = Field(ge=0)
    environment_variant: str = Field(default=NOMINAL_VARIANT, min_length=1)
    sample_set: SampleSet = "evaluation"

    @model_validator(mode="before")
    @classmethod
    def _drop_declared_identity(cls, value: object) -> object:
        """Accept and discard a serialised id so dumps reload unchanged."""
        if isinstance(value, dict) and "episode_context_id" in value:
            return {k: v for k, v in value.items() if k != "episode_context_id"}
        return value

    @model_validator(mode="after")
    def _validate_sample_set(self) -> EpisodeContext:
        """Evaluation runs on the nominal environment, and only there.

        Without this the two sets could collide: a neighborhood context
        whose variant was left at ``nominal`` would hash identically to
        the evaluation context for the same mission and seed, and the ban
        on pooling them (HĐ-11.4) would become unenforceable — the ids
        alone could no longer tell you which set a row came from.
        """
        nominal = self.environment_variant == NOMINAL_VARIANT
        if self.sample_set == "evaluation" and not nominal:
            raise ValueError(
                f"evaluation episodes run on the nominal environment, got variant "
                f"{self.environment_variant!r}; label this context sample_set='neighborhood'"
            )
        if self.sample_set == "neighborhood" and nominal:
            raise ValueError(
                "a neighborhood episode must name the variant it perturbs; "
                f"{NOMINAL_VARIANT!r} is the unperturbed environment"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def episode_context_id(self) -> str:
        """Hash of the conditions, exactly as HĐ-3.1 defines the payload."""
        return sha256_short(
            canonical_json(
                {
                    "task_profile_id": self.task_profile_id,
                    "mission_id": self.mission_id,
                    "environment_variant": self.environment_variant,
                    "seed": self.seed,
                }
            ),
            length=EPISODE_CONTEXT_ID_LENGTH,
        )
