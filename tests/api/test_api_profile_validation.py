"""Asking whether a deployment is legal without filing it.

**The rule this endpoint exists to protect.** The deployment form decides
nothing: ``TaskProfile`` on the server is the single statement of HĐ-2,
and a second opinion in the browser would be free to disagree with the
one that actually refuses. But a refusal that only arrives on submit
makes the author guess which of thirty inputs the server disliked — so
the verdict has to be *askable*, not *reimplementable*. That is all this
is: the same check ``create`` runs, reached without storing anything.

Two properties are pinned here because everything upstream leans on them.

The first is that the refusal has **one shape**. Invalid leaves as a 422
carrying the same per-field addresses ``POST /task-profiles`` produces,
so the form has one error path rather than two that drift.

The second is **how coarse those addresses are, honestly**. Every traffic
rule — unique names, a seed head start, a full period, a declared closing
speed — lives in a model validator on ``EnvironmentSpec``, so pydantic
reports it against ``environment`` and not against the obstacle that
caused it. The tests below assert that path rather than a prettier one.
Anyone who wants ``environment.dynamic_obstacles.2.motion.period`` has to
move the check, and these tests are where they will find out.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from payloads import bordered_map_payload

API = "/api/v1"
REPO_ROOT = Path(__file__).resolve().parents[2]


def shipped(name: str) -> dict:
    """A profile as its committed YAML says it.

    The real documents rather than a fixture: what is being checked is
    the contract, and a hand-written stand-in would be a second opinion
    about what a legal deployment looks like.
    """
    return yaml.safe_load((REPO_ROOT / "profiles" / f"{name}.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def crossing() -> dict:
    """A valid deployment with traffic: one waypoint crosser at 0.8 m/s."""
    return shipped("warehouse_crossing_v1")


@pytest.fixture
def patrolling() -> dict:
    """A valid deployment whose traffic is periodic, for the period rule."""
    return shipped("warehouse_a_v2")


def paths(response) -> list[str]:
    return [entry["path"] for entry in response.json()["error"]["details"]]


class TestALegalDocumentPassesQuietly:
    def test_it_answers_204_with_no_body(self, client: TestClient, alice_headers, crossing) -> None:
        response = client.post(
            f"{API}/task-profiles/validate", json=crossing, headers=alice_headers
        )
        assert response.status_code == 204, response.text
        assert response.content == b""

    def test_it_stores_nothing(self, client: TestClient, alice_headers, crossing) -> None:
        """A check that filed something would be a filing with a friendly name."""
        before = client.get(f"{API}/task-profiles").json()

        response = client.post(
            f"{API}/task-profiles/validate", json=crossing, headers=alice_headers
        )
        assert response.status_code == 204, response.text

        assert client.get(f"{API}/task-profiles").json() == before
        assert client.get(f"{API}/task-profiles/{crossing['id']}").status_code == 404

    def test_it_needs_an_account(self, anonymous: TestClient, crossing) -> None:
        """Nothing is written and nothing is owned, but this is the same
        code path ``create`` runs, and a door to it that needs no account
        is a door that drifts away from the one beside it."""
        assert anonymous.post(f"{API}/task-profiles/validate", json=crossing).status_code == 401


class TestTheRefusalLooksLikeFilingsRefusal:
    """One error path for the form, not two."""

    def test_both_endpoints_refuse_the_same_document_the_same_way(
        self, client: TestClient, alice_headers, crossing
    ) -> None:
        broken = deepcopy(crossing)
        broken["constraints"]["goal_tolerance_rad"] = 0.35  # HĐ-6: heading is not judged

        checked = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        filed = client.post(f"{API}/task-profiles", json=broken, headers=alice_headers)

        assert checked.status_code == filed.status_code == 422
        assert paths(checked) == paths(filed)
        assert checked.json()["error"]["message"] == filed.json()["error"]["message"]


class TestTheFourTrafficRules:
    """Every one of them addressed to ``environment``, which is the truth.

    Not a wish: ``EnvironmentSpec`` states these as model validators, so
    the location pydantic computes is the model, not the field. The form
    renders whatever path arrives; these tests are what tells it which
    one that is.
    """

    def test_duplicate_names(self, client: TestClient, alice_headers, crossing) -> None:
        broken = deepcopy(crossing)
        twin = deepcopy(broken["environment"]["dynamic_obstacles"][0])
        broken["environment"]["dynamic_obstacles"].append(twin)

        response = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        assert response.status_code == 422, response.text
        assert paths(response) == ["environment"]
        assert "unique" in response.json()["error"]["message"]

    def test_a_deterministic_motion_with_no_head_start(
        self, client: TestClient, alice_headers, crossing
    ) -> None:
        """The variance-zero trap: 30 seeds replaying one episode."""
        broken = deepcopy(crossing)
        broken["environment"]["dynamic_obstacles"][0]["seed_time_offset"] = 0.0

        response = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        assert response.status_code == 422, response.text
        assert paths(response) == ["environment"]
        assert "seed_time_offset" in response.json()["error"]["message"]

    def test_a_periodic_obstacle_shifted_by_less_than_its_period(
        self, client: TestClient, alice_headers, patrolling
    ) -> None:
        """The same failure, quieter — the reference warehouse's own bug."""
        broken = deepcopy(patrolling)
        obstacle = broken["environment"]["dynamic_obstacles"][0]
        assert obstacle["motion"]["kind"] == "periodic"
        obstacle["seed_time_offset"] = obstacle["motion"]["period"] / 4

        response = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        assert response.status_code == 422, response.text
        assert paths(response) == ["environment"]
        assert "period" in response.json()["error"]["message"]

    def test_two_obstacles_sharing_a_clock(
        self, client: TestClient, alice_headers, crossing
    ) -> None:
        """Unique names never prevented lockstep, and now the key is checked.

        The head start is hashed from ``seed_offset + len(name)``, so two
        names of the same length collide and the two obstacles move as
        one object at every seed. This is the fifth traffic rule and it
        lands on ``environment`` like the other four.
        """
        broken = deepcopy(crossing)
        twin = deepcopy(broken["environment"]["dynamic_obstacles"][0])
        twin["name"] = "x" * len(broken["environment"]["dynamic_obstacles"][0]["name"])
        broken["environment"]["dynamic_obstacles"].append(twin)

        response = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        assert response.status_code == 422, response.text
        assert paths(response) == ["environment"]
        assert "clock key" in response.json()["error"]["message"]

    def test_a_closing_speed_below_what_the_traffic_can_do(
        self, client: TestClient, alice_headers, crossing
    ) -> None:
        """``v_obstacle_max`` is checked against the motion, not trusted."""
        broken = deepcopy(crossing)
        assert broken["environment"]["dynamic_obstacles"][0]["motion"]["speed"] == 0.8
        broken["environment"]["v_obstacle_max"] = 0.5

        response = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        assert response.status_code == 422, response.text
        assert paths(response) == ["environment"]


class TestAFieldLevelRefusalKeepsItsOwnAddress:
    """The contrast that makes the coarse paths above readable.

    Whatever pydantic can address, it addresses. The traffic rules land on
    ``environment`` because of where they are written, not because the
    endpoint flattens anything on the way out.
    """

    def test_a_negative_radius_is_reported_against_the_radius(
        self, client: TestClient, alice_headers, crossing
    ) -> None:
        broken = deepcopy(crossing)
        broken["environment"]["dynamic_obstacles"][0]["radius"] = -1.0

        response = client.post(f"{API}/task-profiles/validate", json=broken, headers=alice_headers)
        assert response.status_code == 422, response.text
        assert paths(response) == ["environment.dynamic_obstacles.0.radius"]


#: Every `Scenario` field the deployment form's preview adapter fills.
#:
#: Kept as a literal beside the same list in
#: ``apps/web/src/lib/__tests__/traffic.test.ts``. The pair is the point:
#: the TypeScript side proves the adapter builds these, and this side
#: proves the real schema accepts exactly them and that ``scenario_for``
#: — what turns a profile into an actual episode — fills the same set. A
#: preview built from a smaller subset would be a second answer to what
#: this deployment runs, and it would show up as traffic in the wrong
#: place at the same instant.
ADAPTER_FIELDS = (
    "name",
    "robot",
    "start_pose",
    "goal_pose",
    "goal_tolerance",
    "timeout_seconds",
    "simulation_dt",
    "dynamic_obstacles",
    "sensor_noise",
    "clearance_preference",
    "stuck_time_window",
    "random_seed",
)


class TestThePreviewAdapterSpeaksTheRealSchema:
    """The form's preview payload, put through the endpoint that takes it.

    A snapshot of the object in a TypeScript test proves the adapter
    builds what its author intended. It cannot prove pydantic accepts it:
    a required field left out, or a value of the wrong shape, only shows
    up as a 422 on somebody's screen. So the payload is assembled here in
    the same shape and posted for real.
    """

    def preview_payload(self, map_id: str) -> dict:
        from planbench_schemas.task_profile import TaskProfile

        # Through the contract rather than off the raw YAML: the form's
        # draft comes from `GET /task-profiles/template`, so it carries
        # the defaults for anything a profile leaves out —
        # `clearance_preference` among them, which the shipped crossing
        # deployment does not declare.
        crossing = TaskProfile.model_validate(shipped("warehouse_crossing_v1")).model_dump(
            mode="json"
        )
        robot = crossing["robot"]
        return {
            "map_id": map_id,
            "time": 4.0,
            "seed": 7,
            "scenario": {
                "name": "deployment-preview",
                "description": "",
                # The vehicle's physics only: `control_period` is a
                # deployment requirement and reaches the simulator as
                # `simulation_dt`, and `type` has no room in this schema.
                "robot": {
                    key: robot[key]
                    for key in (
                        "radius",
                        "max_linear_velocity",
                        "max_angular_velocity",
                        "max_linear_acceleration",
                        "max_angular_acceleration",
                    )
                },
                "start_pose": {"x": 2.0, "y": 2.0, "theta": 0.0},
                "goal_pose": {"x": 9.0, "y": 9.0, "theta": 0.0},
                "goal_tolerance": crossing["constraints"]["goal_tolerance_m"],
                "timeout_seconds": crossing["constraints"]["episode_timeout_s"],
                "simulation_dt": min(0.05, robot["control_period"]),
                "dynamic_obstacles": crossing["environment"]["dynamic_obstacles"],
                "sensor_noise": crossing["environment"]["sensor_noise"],
                "clearance_preference": crossing["clearance_preference"],
                "stuck_time_window": crossing["constraints"]["stuck_threshold_s"],
                "random_seed": 7,
            },
        }

    def test_the_endpoint_accepts_it(self, client: TestClient, alice_headers) -> None:
        stored = client.post(f"{API}/maps", json=bordered_map_payload(width=12, height=12))
        assert stored.status_code in (200, 201), stored.text

        response = client.post(
            f"{API}/scenarios/preview",
            json=self.preview_payload(stored.json()["id"]),
            headers=alice_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["seed"] == 7
        assert [obstacle["name"] for obstacle in body["dynamic_obstacles"]] == ["crossing-amr"]

    def test_the_adapter_fills_what_an_episode_fills(self) -> None:
        """The drift guard: `scenario_for` gaining a field must show here.

        Only the fields a *deployment* decides are compared. `Scenario`
        also carries things no profile speaks to — the static obstacles
        of a hand-drawn scene, the LiDAR the platform fixes, the
        progress-window defaults — and demanding those would be asking
        the preview to invent them.
        """
        from planbench_schemas.scenario import Scenario

        assert set(ADAPTER_FIELDS) <= set(Scenario.model_fields)

        episode_source = (
            REPO_ROOT / "packages" / "benchmark" / "planbench_benchmark" / "episode.py"
        ).read_text(encoding="utf-8")
        body = episode_source[episode_source.index("def scenario_for") :]
        body = body[: body.index("\ndef ")]
        for field in ADAPTER_FIELDS:
            if field == "name":
                continue  # the episode names itself by context id; a preview names nothing
            assert f"{field}=" in body, f"{field} is no longer part of an episode"


class TestWhatAPassDoesNotPromise:
    def test_an_id_already_filed_with_other_content_still_passes(
        self, client: TestClient, alice_headers, crossing
    ) -> None:
        """The documented limit of this endpoint, pinned as behaviour.

        It reads the document and nothing else — no repository, no ids in
        use — so the HĐ-3.1 clash cannot appear until filing. A caller who
        read 204 as "this will file" would be wrong, which is why the
        endpoint's own note says so.
        """
        filed = client.post(f"{API}/task-profiles", json=crossing, headers=alice_headers)
        assert filed.status_code == 201, filed.text

        changed = deepcopy(crossing)
        changed["environment"]["sensor_noise"]["lidar_range_sigma_m"] = 0.05

        checked = client.post(f"{API}/task-profiles/validate", json=changed, headers=alice_headers)
        assert checked.status_code == 204, checked.text

        refiled = client.post(f"{API}/task-profiles", json=changed, headers=alice_headers)
        assert refiled.status_code == 409, refiled.text
