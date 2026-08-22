"""H12: one flag that meant two things, and the PPO claim it exposed.

``benchmarkable=False`` said *D12 pipeline adapter* from the beginning
and then also said *withdrawn on measured evidence* from 2026-08-16, at
which point a refusal quoting it could not say which one it meant — the
report on the withdrawal says exactly that, and added ``withdrawn`` as a
patch. H12 finishes the job: each fact says its own, and the flag that
carried both is derived from them.

The PPO half is different in kind. DoD #1 claims all four stacks run
through the host without drift, and PPO was only ever checked at
identity level because this machine has no RL extras. That is a
**partial** claim, and the test below keeps it partial out loud rather
than letting an absent dependency read as a pass.
"""

from __future__ import annotations

import subprocess
from importlib.util import find_spec

import pytest
from pydantic import ValidationError

from planbench_benchmark.registry import ALGORITHMS, AlgorithmInfo, algorithm_info, list_algorithms

#: The commit immediately before H2 introduced the AlgorithmHost. A
#: pre-host baseline can only come from here — building one from HEAD
#: would compare the host against itself.
PRE_HOST_COMMIT = "239132e"

RL_INSTALLED = find_spec("stable_baselines3") is not None


class TestTheFlagThatMeantTwoThingsNowMeansNone:
    def test_a_reference_adapter_says_so(self) -> None:
        info = algorithm_info("astar+pure_pursuit")
        assert info.reference is True
        assert info.withdrawn == ""
        assert info.production_eligible is False

    def test_a_withdrawn_stack_says_something_else(self) -> None:
        """Both are ineligible; they are ineligible for different reasons,
        and an operator reading one must not be told the other's."""
        info = algorithm_info("astar+dwa_predictive")
        assert info.reference is False
        assert info.withdrawn != ""
        assert info.production_eligible is False

    def test_an_ordinary_stack_is_neither(self) -> None:
        info = algorithm_info("astar+dwa")
        assert info.reference is False
        assert info.withdrawn == ""
        assert info.production_eligible is True

    def test_the_two_reasons_are_distinguishable_across_the_registry(self) -> None:
        """The property the old boolean could not express: for every
        ineligible entry, exactly one of the two reasons applies."""
        ineligible = [info for info in list_algorithms() if not info.production_eligible]
        assert ineligible, "the registry has no ineligible entries left to distinguish"
        for info in ineligible:
            assert info.reference != bool(info.withdrawn), (
                f"{info.id} is ineligible for both reasons or for neither; the split "
                "exists so a refusal can name one"
            )


class TestTheAliasStaysOnTheWire:
    def test_benchmarkable_still_reads_and_agrees(self) -> None:
        """``/algorithms`` serialises it and the web candidate picker
        filters on it. Derived rather than stored, so the two cannot
        drift apart."""
        for info in list_algorithms():
            assert info.benchmarkable == info.production_eligible

    def test_it_survives_serialisation(self) -> None:
        dumped = algorithm_info("astar+dwa").model_dump(mode="json")
        assert dumped["benchmarkable"] is True
        assert dumped["production_eligible"] is True

    def test_passing_the_old_flag_is_refused_rather_than_ignored(self) -> None:
        """The direction that must never fail silently. This model does
        not forbid extras, so an entry still passing ``benchmarkable``
        would be accepted with no effect — and a stack meant to be
        withheld would quietly become a contender."""
        with pytest.raises(ValidationError, match="derived from reference and withdrawn"):
            AlgorithmInfo(
                id="x+y",
                kind="stack",
                description="d",
                benchmarkable=False,
                config_schema={},
                global_observation_class="full_static_map",
                local_observation_class="lidar_only",
                requires_global_path=True,
            )

    def test_the_offered_set_is_unchanged_by_the_rename(self) -> None:
        """The exact-set guard that caught two undecided stacks in the P6
        session, pointed at the new field."""
        offered = sorted(
            stack for stack, entry in ALGORITHMS.items() if entry.info.production_eligible
        )
        assert offered == ["astar+dwa", "astar+ppo", "rrtstar+dwa"]


class TestPPORuntimeParityStaysPartial:
    """DoD #1 is **not** met for PPO, and this file says so in code.

    The recovery procedure, for whoever has the extras:

    1. install the RL extras and pin a PPO checkpoint;
    2. ``git worktree add <dir> 239132e`` — the commit before H2;
    3. run one profile, seed and checkpoint through both trees;
    4. compare outcome, trajectory, events, candidate id, fingerprint and
       the deterministic trace fields with the H0 comparator;
    5. record both SHAs and the checkpoint digest in the report.

    Building the baseline from HEAD is not an option: H2 is already in
    it, so the comparison would be the host against itself.
    """

    def test_the_registry_still_marks_ppo_as_needing_a_chosen_model(self) -> None:
        info = algorithm_info("astar+ppo")
        assert info.requires_model is True
        assert info.production_eligible is True

    @pytest.mark.skipif(
        not RL_INSTALLED,
        reason=(
            "PPO runtime parity is unproven on a machine without the RL extras. "
            "DoD #1 stays partial: identity-level checks do not show the host wrap "
            "leaves a PPO episode unchanged. See this class's docstring for the "
            f"procedure, which starts from {PRE_HOST_COMMIT}"
        ),
    )
    def test_a_pre_host_baseline_is_reachable(self) -> None:
        """Only the *precondition* the procedure needs, checked cheaply:
        that the pre-host commit is still in this repository. The episode
        comparison itself needs a checkpoint nobody has pinned yet."""
        completed = subprocess.run(
            ["git", "cat-file", "-t", PRE_HOST_COMMIT],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.stdout.strip() == "commit", (
            f"{PRE_HOST_COMMIT} is not reachable; the pre-host baseline cannot be "
            "rebuilt from HEAD, so PPO parity would have nothing to compare against"
        )
