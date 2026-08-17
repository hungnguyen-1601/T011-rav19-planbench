"""H0 parity baseline: what the legacy runtime does before AlgorithmHost.

Plan ``docs/antongduy/plans/2026-08-17/algorithm-host-mo-rong-cho-global-
va-local-planner.md`` wraps the current runtime in an AlgorithmHost (H2)
and promises the wrap changes nothing. This file is that promise turned
into a fact, the same way ``test_dwa_core_refactor.py`` was for P2: the
fixture is generated **before** the host exists, committed, and every
run after compares byte-for-byte against it.

**The comparator is stated, not implied** (H0 DoD). Byte-identical:
``candidate_id``, ``execution_conditions_fingerprint``, episode
``status``/``reason``/``steps``, every global plan, the full trajectory
(pose and commands), every event (time, type, message — messages carry
only simulated quantities), and the trace's deterministic metadata,
column set and row count.

**Excluded, preregistered.** Exactly the wall-clock measurements, which
vary with machine load and are not what the host wrap may change:
:data:`EXCLUDED_WALLCLOCK_FIELDS`. Nothing else is excluded, and a test
below pins that the fixture stores none of them, so the exclusion list
cannot silently grow.

**PPO is baselined at identity level only on this machine** — torch is
not installed, so the runtime half is the registry facts and the refusal
path, pinned in :class:`TestPPOBaselineWithoutRuntime`. When a machine
with the RL extras runs H2 parity, PPO gets a golden case of its own.

To regenerate — only ever with a reason, and the reason is never "the
test went red"::

    PLANBENCH_REGEN_HOST_PARITY=1 python -m pytest tests/test_host_parity_golden.py
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    candidate_from_stack,
)
from planbench_benchmark.contexts import build_evaluation_contexts
from planbench_benchmark.episode import run_contract_episode
from planbench_benchmark.fingerprint import CONDITION_ARGUMENTS
from planbench_benchmark.registry import AlgorithmConfigError, algorithm_info
from planbench_benchmark.selection import load_profile, load_task_map
from planbench_simulator.nav_stack import run_policy
from planbench_simulator.trace import read_trace_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE = REPO_ROOT / "profiles" / "warehouse_crossing_v1.yaml"
GOLDEN_PATH = Path(__file__).parent / "golden" / "host_parity.json"

#: Wall-clock measurements, and nothing else. These are the only fields
#: the H0/H2 comparator ignores: they measure the machine the episode ran
#: on, not the episode, and a host wrap that changed *them* would be
#: caught by the latency layers of §5.9 instead.
EXCLUDED_WALLCLOCK_FIELDS: tuple[str, ...] = (
    "planner_latency_ms",  # trace column, per control step
    "latency_seconds",  # LocalPlanResult, per compute
    "planning_time_seconds",  # PlanResult, per global plan
    "global_plan_time_ms",  # TraceMetadata
    "peak_rss_mb",  # TraceMetadata, OS-dependent
    "cpu_time_s",  # TraceMetadata, OS-dependent
)

#: Two stacks × two seeds on the deployment the platform's own regression
#: artefact came from (``warehouse_crossing_v1`` is the profile whose
#: journal exposed the stale-trace hole). RRT* is here so the seeded
#: stochastic path — the thing most likely to drift under a wrap that
#: touches seed plumbing — is pinned alongside the deterministic one.
CASES: tuple[dict[str, Any], ...] = (
    {"name": "astar_dwa_seed0", "stack": "astar+dwa", "config": "dwa_balanced", "context": 0},
    {"name": "astar_dwa_seed1", "stack": "astar+dwa", "config": "dwa_balanced", "context": 1},
    {"name": "rrtstar_dwa_seed0", "stack": "rrtstar+dwa", "config": "dwa_balanced", "context": 0},
    {"name": "rrtstar_dwa_seed1", "stack": "rrtstar+dwa", "config": "dwa_balanced", "context": 1},
)


@pytest.fixture(scope="module")
def deployment():
    profile = load_profile(PROFILE)
    map_data = load_task_map(profile, base_dir=REPO_ROOT)
    contexts = build_evaluation_contexts(profile, seed_count=2)
    return profile, map_data, contexts


def _capture(case: dict[str, Any], deployment, root: Path) -> dict[str, Any]:
    """One episode through the exact production path, reduced to the
    comparator's fields — the wall-clock exclusions never enter."""
    profile, map_data, contexts = deployment
    context = contexts[case["context"]]
    candidate = candidate_from_stack(
        case["stack"], params=dict(LOCAL_CONTROLLER_CONFIGS[case["config"]])
    )
    path, run = run_contract_episode(candidate, profile, context, map_data, root=root)
    metadata = read_trace_metadata(path)
    return {
        "candidate_id": candidate.candidate_id,
        "execution_conditions_fingerprint": metadata.execution_conditions_fingerprint,
        "status": run.result.status.value,
        "reason": run.result.reason,
        "steps": run.result.steps,
        "plans": [[[p.x, p.y] for p in plan.path] for plan in run.plans],
        "trajectory": [
            [pt.time, pt.x, pt.y, pt.theta, pt.linear_velocity, pt.angular_velocity]
            for pt in run.result.trajectory
        ],
        "events": [[event.time, event.type, event.message] for event in run.result.events],
        "trace": {
            "relative_path": path.relative_to(root).as_posix(),
            "columns": pq.read_schema(path).names,
            "rows": pq.ParquetFile(path).metadata.num_rows,
            "metadata": {
                "episode_context_id": metadata.episode_context_id,
                "candidate_id": metadata.candidate_id,
                "task_profile_id": metadata.task_profile_id,
                "sample_set": metadata.sample_set,
                "global_plan_length_m": metadata.global_plan_length_m,
                "peak_search_nodes": metadata.peak_search_nodes,
                "peak_tree_nodes": metadata.peak_tree_nodes,
                "costmap_cells": metadata.costmap_cells,
            },
        },
    }


def _generate(deployment, root: Path) -> dict[str, Any]:
    return {case["name"]: _capture(case, deployment, root) for case in CASES}


@pytest.fixture(scope="module")
def measured(deployment, tmp_path_factory) -> dict[str, Any]:
    """Every case, run once through ``run_contract_episode``."""
    return _generate(deployment, tmp_path_factory.mktemp("host_parity_traces"))


@pytest.fixture(scope="module")
def golden(deployment, tmp_path_factory) -> dict[str, Any]:
    if os.environ.get("PLANBENCH_REGEN_HOST_PARITY"):
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = _generate(deployment, tmp_path_factory.mktemp("host_parity_regen"))
        GOLDEN_PATH.write_text(json.dumps(record, indent=1), encoding="utf-8")
        pytest.skip("regenerated the host parity fixture; re-run without the flag to check it")
    if not GOLDEN_PATH.exists():
        raise AssertionError(
            f"{GOLDEN_PATH} is missing. It records how the legacy runtime behaved "
            "before the AlgorithmHost existed, so it cannot be rebuilt from the code "
            "it exists to check. Restore it from git rather than regenerating it"
        )
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


class TestTheLegacyRuntimeIsPinned:
    """One byte-compare, then per-case assertions that name the culprit."""

    def test_the_serialised_form_is_byte_identical(
        self, golden: dict[str, Any], measured: dict[str, Any]
    ) -> None:
        """Formatted exactly as the fixture was written, compared as text —
        ``repr`` distinguishes ``0``, ``0.0`` and ``-0.0``, so a type flip
        or a sign flip on zero cannot hide behind ``==``.

        ``golden`` is requested even though the bytes are read directly:
        the regen path lives in that fixture, so depending on it is what
        makes ``PLANBENCH_REGEN_HOST_PARITY=1`` write the file before this
        test would try to read it.
        """
        del golden
        assert json.dumps(measured, indent=1) == GOLDEN_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", [case["name"] for case in CASES])
    def test_identity_is_identical(self, name, golden, measured) -> None:
        """Candidate id and conditions fingerprint first: if these moved,
        every downstream diff is a consequence, not a finding."""
        assert name in golden, f"no golden record for {name}; the case list grew"
        assert measured[name]["candidate_id"] == golden[name]["candidate_id"]
        assert (
            measured[name]["execution_conditions_fingerprint"]
            == golden[name]["execution_conditions_fingerprint"]
        )

    @pytest.mark.parametrize("name", [case["name"] for case in CASES])
    def test_the_episode_is_identical(self, name, golden, measured) -> None:
        assert measured[name]["plans"] == golden[name]["plans"]
        assert measured[name]["trajectory"] == golden[name]["trajectory"]
        assert measured[name]["events"] == golden[name]["events"]
        assert measured[name]["status"] == golden[name]["status"]
        assert measured[name]["reason"] == golden[name]["reason"]
        assert measured[name]["steps"] == golden[name]["steps"]

    @pytest.mark.parametrize("name", [case["name"] for case in CASES])
    def test_the_trace_is_identical(self, name, golden, measured) -> None:
        assert measured[name]["trace"] == golden[name]["trace"]

    def test_the_fixture_covers_every_case(self, golden) -> None:
        assert sorted(golden) == sorted(case["name"] for case in CASES)

    def test_the_episodes_actually_did_something(self, golden) -> None:
        """Four robots that never moved would pass everything above and
        pin nothing."""
        for name, record in golden.items():
            assert record["steps"] > 100, f"{name} barely ran"
            moved = {tuple(point[1:3]) for point in record["trajectory"]}
            assert len(moved) > 20, f"{name} did not go anywhere"

    def test_the_two_seeds_are_really_two_episodes(self, golden) -> None:
        """Seed plumbing is half of what H2 must not break; two seeds that
        produced one trajectory would mean the fixture never tested it."""
        for stack in ("astar_dwa", "rrtstar_dwa"):
            first = golden[f"{stack}_seed0"]
            second = golden[f"{stack}_seed1"]
            assert (
                first["trace"]["metadata"]["episode_context_id"]
                != second["trace"]["metadata"]["episode_context_id"]
            )
            assert first["trajectory"] != second["trajectory"], (
                f"{stack}: two seeds, one trajectory — the seed is not reaching the episode"
            )

    def test_the_fixture_stores_no_wallclock_field(self) -> None:
        """The exclusion list is preregistered; the fixture proves it was
        honoured. A regen that started storing a latency would make every
        future parity run flaky, and this catches it at commit time."""
        text = GOLDEN_PATH.read_text(encoding="utf-8")
        for field in EXCLUDED_WALLCLOCK_FIELDS:
            # As a JSON key — ``"field":`` — which is how a stored value
            # would appear. The bare name is allowed: ``trace.columns``
            # rightly lists ``planner_latency_ms`` as a column the trace
            # schema has; it is the *values* that are wall-clock.
            assert f'"{field}":' not in text, f"fixture stores excluded wall-clock field {field!r}"


class TestConditionArgumentsStayGuarded:
    """H0 DoD: every new runtime condition must flow through the shared
    fingerprint. ``run_stack`` is guarded in ``test_execution_conditions``;
    this closes the same door for the monolithic entry point."""

    def test_run_policy_has_not_grown_a_condition(self) -> None:
        parameters = set(inspect.signature(run_policy).parameters)
        not_conditions = {"policy", "recorder", "legacy_metrics"}
        conditions = parameters - not_conditions
        assert conditions <= set(CONDITION_ARGUMENTS), (
            "run_policy grew an argument that describes the world; decide whether it "
            "belongs in execution_conditions_fingerprint, then update CONDITION_ARGUMENTS "
            "and the run_stack guard together"
        )


class TestPPOBaselineWithoutRuntime:
    """The half of the PPO baseline that does not need torch.

    The registry facts and the refusal path are what H2's legacy adapter
    must preserve on a machine without the RL extras; the runtime golden
    case is added on a machine that has them.
    """

    def test_the_registry_facts_are_pinned(self) -> None:
        info = algorithm_info("astar+ppo")
        assert info.id == "astar+ppo"
        assert info.local_controller == "ppo"
        assert info.benchmarkable is True
        assert info.requires_model is True
        assert info.requires_global_path is True
        assert info.global_observation_class == "full_static_map"
        assert info.local_observation_class == "lidar_only"

    def test_building_without_a_model_is_refused(self) -> None:
        """The refusal is part of the baseline: a host adapter that
        silently built a PPO candidate without a chosen model would be
        inventing the choice the spec forbids inventing."""
        with pytest.raises(AlgorithmConfigError, match="no PPO model was chosen"):
            candidate_from_stack("astar+ppo", params={})
