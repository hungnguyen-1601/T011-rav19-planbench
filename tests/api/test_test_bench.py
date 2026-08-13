"""The test bench: one episode of a deployment, watched rather than measured.

Before this existed, the cheapest way to find out that a mission's goal
sat behind a shelf was to spend two hours on a three-hundred-episode
comparison and read a uniform wall of ``no_path`` at the end — which
looks like a platform fault, not a mission fault. Watching one episode
costs seconds.

Two properties carry the whole design, and both are asserted here rather
than argued in a docstring:

1. **What you watch is what the comparison will run.** The scenario comes
   from ``scenario_for`` — the same function ``run_contract_episode``
   calls — so the timeout, the tolerance, the noise and the traffic are
   the deployment's, not a form's. A test bench that quietly ran gentler
   conditions would be worse than none: it would offer confidence for an
   experiment nobody is going to perform.

2. **Nothing it produces is evidence.** HĐ-5 makes the Parquet trace the
   sole input of the Metrics Engine. This endpoint writes none, so no
   gate, metric or card can see the run — which is precisely what lets it
   run outside the context-outer order (HĐ-3.2) and beside a live
   evaluation (HĐ-7.4). The ``episode_context_id`` it reports is real;
   the run behind it is not a sample.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
API = "/api/v1"


def tiny_profile() -> dict:
    """The shipped hall, cut to something one episode finishes inside."""
    profile = yaml.safe_load(
        (REPO_ROOT / "profiles" / "open_hall_v2.yaml").read_text(encoding="utf-8")
    )
    profile["id"] = "bench_hall"
    profile["constraints"]["episode_timeout_s"] = 25
    profile["constraints"]["stuck_threshold_s"] = 4
    return profile


@pytest.fixture
def deployment(client: TestClient, alice_headers: dict[str, str]) -> dict:
    created = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
    assert created.status_code == 201, created.text
    return created.json()["profile"]


def stage(client: TestClient, profile: dict, **overrides) -> dict:
    body = {
        "mission_id": profile["missions"][0]["id"],
        "seed": 0,
        "stack": "astar+dwa",
        "local_config": "dwa_coarse",
    }
    body.update(overrides)
    response = client.post(f"{API}/task-profiles/{profile['id']}/test-bench", json=body)
    assert response.status_code == 201, response.text
    return response.json()


class TestTheEpisodeIsTheDeploymentsOwn:
    """Every condition comes from the contract, none from the request."""

    def test_the_scenario_carries_the_deployments_constraints(
        self, client: TestClient, deployment: dict
    ) -> None:
        """Timeout, tolerance and stuck window are the deployment's.

        These are the three a form would be tempted to expose as "just
        for the preview", and each one changes what you are watching:
        a longer timeout turns a stuck robot into a slow one, a looser
        tolerance turns a near miss into an arrival.
        """
        scenario = stage(client, deployment)["scenario"]
        constraints = deployment["constraints"]
        assert scenario["timeout_seconds"] == constraints["episode_timeout_s"]
        assert scenario["goal_tolerance"] == constraints["goal_tolerance_m"]
        assert scenario["stuck_time_window"] == constraints["stuck_threshold_s"]

    def test_the_noise_is_the_deployments_noise(
        self, client: TestClient, deployment: dict
    ) -> None:
        """A candidate that could soften the noise would choose its exam.

        The same argument as HĐ-3.1's, one layer earlier: the amplitudes
        the robot is watched under have to be the ones it will be
        measured under, or the watching means nothing.
        """
        scenario = stage(client, deployment)["scenario"]
        assert scenario["sensor_noise"] == deployment["environment"]["sensor_noise"]

    def test_the_traffic_is_the_deployments_traffic(
        self, client: TestClient, deployment: dict
    ) -> None:
        scenario = stage(client, deployment)["scenario"]
        assert scenario["dynamic_obstacles"] == deployment["environment"]["dynamic_obstacles"]

    def test_the_physics_step_is_never_coarser_than_the_simulators_default(
        self, client: TestClient, deployment: dict
    ) -> None:
        """A relaxed control period must not buy a coarser world.

        ``control_period`` is G4's threshold — a requirement about the
        target board — while ``simulation_dt`` is a fidelity choice. The
        bridge caps one by the other in exactly one direction, and a
        preview that lost the cap would show a robot moving in jumps it
        never makes in a measured episode.
        """
        scenario = stage(client, deployment)["scenario"]
        assert scenario["simulation_dt"] <= 0.05

    def test_the_context_id_is_the_real_one(self, client: TestClient, deployment: dict) -> None:
        """The hash HĐ-3.1 defines, not a preview-only label.

        Reported honestly because it is the answer to "is this the same
        episode the comparison will run": it is, and this identity is
        what says so. Faking it would break the one claim worth making.
        """
        from planbench_schemas.episode_context import EpisodeContext

        staged = stage(client, deployment, seed=7)
        expected = EpisodeContext(
            task_profile_id=deployment["id"],
            mission_id=deployment["missions"][0]["id"],
            seed=7,
        )
        assert staged["episode_context_id"] == expected.episode_context_id
        # The scenario is named by the context, which is what makes
        # staging the same conditions twice find the same row.
        assert staged["scenario"]["name"] == expected.episode_context_id

    def test_a_different_seed_is_a_different_episode(
        self, client: TestClient, deployment: dict
    ) -> None:
        assert (
            stage(client, deployment, seed=1)["episode_context_id"]
            != stage(client, deployment, seed=2)["episode_context_id"]
        )


class TestNothingItProducesIsEvidence:
    """The safety argument, asserted rather than promised."""

    def test_running_one_writes_no_trace(
        self, client: TestClient, deployment: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """HĐ-5: the Parquet trace is the sole input of the Metrics Engine.

        A test-bench episode that wrote one would inject a sample into
        the evaluation set with a *real* context id — indistinguishable
        downstream from a measured episode, and arriving outside the
        context-outer order (HĐ-3.2) and beside whatever else is running
        (HĐ-7.4). The directory staying empty is the whole defence.
        """
        traces = tmp_path / "bench-traces"
        traces.mkdir()
        monkeypatch.setenv("PLANBENCH_DECISION_TRACE_DIR", str(traces))

        staged = stage(client, deployment)
        run = client.post(f"{API}/simulations/{staged['simulation_id']}/run")
        assert run.status_code == 200, run.text

        assert list(traces.rglob("*.parquet")) == []

    def test_it_files_no_decision_run(self, client: TestClient, deployment: dict) -> None:
        """Nothing appears in the catalogue of comparisons.

        A watched episode that showed up beside real runs would be a row
        somebody could read a conclusion off — the exact confusion the
        no-trace rule exists to prevent, arriving by a different door.
        """
        before = len(client.get(f"{API}/decisions").json())
        client.post(f"{API}/simulations/{stage(client, deployment)['simulation_id']}/run")
        assert len(client.get(f"{API}/decisions").json()) == before

    def test_replanning_stays_off_because_that_is_what_a_measured_episode_runs(
        self, client: TestClient, deployment: dict
    ) -> None:
        """Same stack as the comparison, down to the replanning rule.

        ``run_contract_episode`` calls ``run_stack`` without a replanning
        config, so the measured episode runs with it off. A preview that
        turned it on would be showing a different navigation stack from
        the one about to be judged.
        """
        staged = stage(client, deployment)
        simulation = client.get(f"{API}/simulations/{staged['simulation_id']}").json()
        assert simulation["replanning"]["enabled"] is False


class TestStagingIsIdempotentInWhatItStores:
    def test_watching_twice_leaves_one_map_and_one_scenario(
        self, client: TestClient, deployment: dict
    ) -> None:
        """Twenty replays must not leave twenty rows in the map store.

        The map is matched on its grid and the scenario on its name —
        which is the context hash — so "the same conditions" is decided
        by content rather than by a timestamp.
        """
        first = stage(client, deployment)
        second = stage(client, deployment)
        assert first["map_id"] == second["map_id"]
        assert first["scenario_id"] == second["scenario_id"]
        assert first["simulation_id"] != second["simulation_id"]

    def test_the_map_it_stages_is_the_deployments_map(
        self, client: TestClient, deployment: dict
    ) -> None:
        """The canvas draws the walls the episode actually runs against."""
        staged = stage(client, deployment)
        stored = client.get(f"{API}/maps/{staged['map_id']}").json()
        assert stored["map_data"]["width"] > 0
        assert stored["map_data"]["resolution"] > 0


class TestItRefusesBeforeSpendingAnything:
    def test_a_mission_from_another_deployment(
        self, client: TestClient, deployment: dict
    ) -> None:
        """Naming a mission the profile does not have is not runnable.

        The message says which profile was asked, because the mistake it
        follows from is usually a mission id copied out of a different
        deployment's YAML.
        """
        response = client.post(
            f"{API}/task-profiles/{deployment['id']}/test-bench",
            json={"mission_id": "not_a_mission", "stack": "astar+dwa"},
        )
        assert response.status_code == 422
        assert deployment["id"] in response.json()["error"]["message"]

    def test_an_unknown_controller_configuration_lists_the_known_ones(
        self, client: TestClient, deployment: dict
    ) -> None:
        response = client.post(
            f"{API}/task-profiles/{deployment['id']}/test-bench",
            json={
                "mission_id": deployment["missions"][0]["id"],
                "stack": "astar+dwa",
                "local_config": "dwa_imaginary",
            },
        )
        assert response.status_code == 422
        assert "dwa_coarse" in response.json()["error"]["message"]

    def test_an_unknown_stack(self, client: TestClient, deployment: dict) -> None:
        response = client.post(
            f"{API}/task-profiles/{deployment['id']}/test-bench",
            json={"mission_id": deployment["missions"][0]["id"], "stack": "astar+telepathy"},
        )
        assert response.status_code == 422

    def test_an_unknown_deployment(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/task-profiles/no_such_deployment/test-bench",
            json={"mission_id": "m", "stack": "astar+dwa"},
        )
        assert response.status_code == 404


class TestTheEpisodeActuallyRuns:
    def test_it_streams_a_trajectory(self, client: TestClient, deployment: dict) -> None:
        """The point of the whole feature: something to watch.

        Asserted end to end rather than by inspecting the staged rows,
        because "staged a simulation" and "produced a robot moving" are
        different claims and only the second one is useful.
        """
        staged = stage(client, deployment)
        result = client.post(f"{API}/simulations/{staged['simulation_id']}/run")
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["plan"]["success"] is True
        assert len(body["result"]["trajectory"]) > 1
