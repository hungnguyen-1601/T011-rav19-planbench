"""P6 — the two debts registering a second controller made real.

Both were harmless while ``dwa`` was the only controller, and both stop
being harmless the moment there are two.

**Debt 1 — a configuration name that belongs to somebody else.**
Configuration names live in one flat namespace and nothing checked the
pairing. ``dwa_coarse`` names sampling densities, and every one of its
keys is also a valid ``DWAPredictiveConfig`` field, so
``astar+dwa_predictive:dwa_coarse`` **runs** and the stored report says
``local_controller_config: dwa_coarse`` beside a candidate that is not
``dwa``. The episodes are fine; the record is wrong.

**Debt 2 — every candidate was ``v1`` for ever.**
``candidate_from_stack`` took ``local_version: str = "v1"`` and no caller
ever passed one, while ``StackComponent``'s own docstring promised that
*the same DWA after a bug fix is a different candidate*. With two
controllers sharing ``dwa_core``, a fix in the shared file changes what
**both** do — and both ids would have stayed put.
"""

from __future__ import annotations

import pytest

from planbench_benchmark.candidates import (
    CONTROLLER_CONFIGS,
    CONTROLLER_OF_CONFIG,
    LOCAL_CONTROLLER_CONFIGS,
    ConfigControllerMismatch,
    NotBenchmarkableError,
    candidate_from_stack,
    controller_version,
    validate_config_names,
)
from planbench_benchmark.registry import ALGORITHMS, algorithm_info

#: Every stack a comparison may actually use.
BENCHMARKABLE = tuple(stack for stack, entry in ALGORITHMS.items() if entry.info.benchmarkable)


class TestTheNewStacksAreReachable:
    """Registration, checked as a property rather than by eye."""

    @pytest.mark.parametrize("stack", ["astar+dwa_predictive", "rrtstar+dwa_predictive"])
    def test_the_stack_is_still_registered_but_withdrawn(self, stack: str) -> None:
        """**Registered, reachable, and not a candidate.**

        Withdrawn on 2026-08-16 after the perception feeding it was
        measured: on a static warehouse the tracker reports obstacles
        moving at up to 1.9 m/s, and finer LiDAR makes that worse rather
        than better. Keeping the entry is deliberate — the oracle, the
        diagnostics and these tests are how the negative result stays
        reproducible — but a candidate is something the platform may
        *recommend*, and this is not one.
        """
        info = algorithm_info(stack)
        assert info is not None
        assert info.local_controller == "dwa_predictive"
        assert not info.benchmarkable
        assert info.withdrawn, "a withdrawal has to say why, or the refusal misinforms"

    @pytest.mark.parametrize("stack", ["astar+dwa_predictive", "rrtstar+dwa_predictive"])
    def test_it_cannot_be_built_as_a_candidate(self, stack: str) -> None:
        """The withdrawal has to bite where candidates are made, not only
        in a flag somebody may forget to read."""
        with pytest.raises(NotBenchmarkableError, match="perception"):
            candidate_from_stack(
                stack, params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_predictive_balanced"])
            )

    @pytest.mark.parametrize("stack", ["astar+dwa_predictive", "rrtstar+dwa_predictive"])
    def test_it_stays_a_lidar_only_candidate(self, stack: str) -> None:
        """**The whole comparison depends on this line.** Taking obstacle
        velocities from the engine would make it ``lidar+human_states``,
        which the ranking refuses to compare against ``dwa`` by default —
        and rightly: a candidate told where everything is would win for a
        reason that has nothing to do with prediction."""
        assert algorithm_info(stack).local_observation_class == "lidar_only"

    @pytest.mark.parametrize("stack", ["astar+dwa_predictive", "rrtstar+dwa_predictive"])
    def test_the_description_admits_what_it_does_not_know(self, stack: str) -> None:
        """It reaches ``/candidates`` verbatim, so the two properties a
        reader would otherwise assume away have to be in it: the velocity
        is **estimated**, and the model is **constant velocity**."""
        description = algorithm_info(stack).description.lower()
        assert "estimated" in description
        assert "constant velocity" in description

    def test_the_three_configurations_match_dwa_for_sampling_density(self) -> None:
        """Same density, so the G4 latency axis stays comparable. A
        predictive stack that also sampled more coarsely would fold two
        changes into one reading."""
        for level in ("coarse", "balanced", "default"):
            plain = LOCAL_CONTROLLER_CONFIGS[f"dwa_{level}"]
            predictive = LOCAL_CONTROLLER_CONFIGS[f"dwa_predictive_{level}"]
            assert predictive["velocity_samples"] == plain["velocity_samples"]
            assert predictive["omega_samples"] == plain["omega_samples"]
            assert predictive["control_period"] == plain["control_period"]


class TestAConfigurationMayNotBeBorrowed:
    """Debt 1. ``CONTROLLER_OF_CONFIG`` existed all along; this reads it."""

    def test_a_matching_pair_is_accepted(self) -> None:
        validate_config_names(
            [
                ("astar+dwa", "dwa_balanced"),
                ("astar+dwa_predictive", "dwa_predictive_balanced"),
            ]
        )

    @pytest.mark.parametrize(
        ("stack", "config"),
        [
            ("astar+dwa_predictive", "dwa_coarse"),
            ("rrtstar+dwa_predictive", "dwa_default"),
            ("astar+dwa", "dwa_predictive_balanced"),
        ],
    )
    def test_a_borrowed_configuration_is_refused(self, stack: str, config: str) -> None:
        """**These all run today if nothing stops them**, which is what
        makes the check necessary rather than pedantic: the parameters
        validate, the episodes are sound, and only the label is a lie."""
        with pytest.raises(ConfigControllerMismatch, match="pairs a"):
            validate_config_names([(stack, config)])

    def test_the_message_says_what_to_use_instead(self) -> None:
        with pytest.raises(ConfigControllerMismatch) as raised:
            validate_config_names([("astar+dwa_predictive", "dwa_coarse")])
        assert "dwa_predictive_balanced" in str(raised.value)

    def test_a_name_that_exists_nowhere_is_refused_too(self) -> None:
        with pytest.raises(ConfigControllerMismatch, match="does not exist"):
            validate_config_names([("astar+dwa", "dwa_speedy")])

    def test_the_borrowed_pair_really_would_have_run(self) -> None:
        """The premise of this whole class, checked rather than asserted.
        If ``dwa_coarse`` did not validate against the predictive config,
        the pairing would already fail for a different reason and the new
        check would be dead code."""
        from planbench_benchmark.registry import build_local_planner

        planner = build_local_planner(
            "astar+dwa_predictive", LOCAL_CONTROLLER_CONFIGS["dwa_coarse"]
        )
        assert planner.name == "dwa_predictive"

    def test_every_shipped_configuration_knows_its_owner(self) -> None:
        for name in LOCAL_CONTROLLER_CONFIGS:
            assert name in CONTROLLER_OF_CONFIG
        for controller, configs in CONTROLLER_CONFIGS.items():
            for name in configs:
                assert CONTROLLER_OF_CONFIG[name] == controller


class TestACandidateIdTracksItsCode:
    """Debt 2. ``v1`` for ever was a promise the id could not keep."""

    def test_the_version_is_no_longer_a_literal(self) -> None:
        candidate = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])
        )
        assert candidate.local_controller.version != "v1"

    def test_two_controllers_have_two_versions(self) -> None:
        assert controller_version("dwa") != controller_version("dwa_predictive")

    def test_the_shared_core_is_hashed_into_both(self) -> None:
        """**The reason this debt got worse rather than older.** Since P2
        the two controllers call the same ``dwa_core`` functions, so a fix
        there changes what both of them do. Hashing only each
        controller's own file would let that happen with both recorded
        ids unmoved — the precise failure ``StackComponent.version``
        exists to prevent.
        """
        import inspect

        from planbench_benchmark.candidates import _CONTROLLER_SOURCES
        from planbench_planning.common import dwa_core

        core = inspect.getsource(dwa_core)
        for controller, modules in _CONTROLLER_SOURCES.items():
            assert "planbench_planning.common.dwa_core" in modules, controller
        assert core, "the shared core is empty, so hashing it proves nothing"

    def test_it_is_stable_across_calls(self) -> None:
        """An id that moved between two calls in one process would make
        every paired comparison incomparable."""
        first = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])
        )
        second = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"])
        )
        assert first.candidate_id == second.candidate_id

    def test_parameters_still_separate_candidates(self) -> None:
        """The checksum is added to the id, not substituted for the
        parameters: two sampling densities of one controller stay two
        candidates."""
        coarse = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_coarse"])
        )
        default = candidate_from_stack(
            "astar+dwa", params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_default"])
        )
        assert coarse.candidate_id != default.candidate_id
        assert coarse.local_controller.version == default.local_controller.version

    def test_an_explicit_version_still_wins(self) -> None:
        """A caller reconstructing a historical candidate has to be able
        to say which code it ran — the ids stored before this change are
        the reason the argument survives."""
        candidate = candidate_from_stack(
            "astar+dwa",
            params=dict(LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]),
            local_version="v1",
        )
        assert candidate.local_controller.version == "v1"

    def test_a_controller_without_hashed_sources_falls_back(self) -> None:
        """``ppo`` carries its checkpoint checksum already and
        ``pure_pursuit`` is not benchmarkable, so neither needs one."""
        assert controller_version("pure_pursuit") == "v1"
        assert controller_version("ppo") == "v1"

    @pytest.mark.parametrize("stack", BENCHMARKABLE)
    def test_every_benchmarkable_stack_builds_a_candidate(self, stack: str) -> None:
        """Including the new pair — a registry entry that cannot become a
        candidate would fail at the start of a comparison instead of
        here."""
        info = algorithm_info(stack)
        if info.requires_model:
            pytest.skip("needs a model checkpoint, covered by the PPO suite")
        config = f"{info.local_controller}_balanced"
        assert candidate_from_stack(
            stack, params=dict(LOCAL_CONTROLLER_CONFIGS[config])
        ).candidate_id
