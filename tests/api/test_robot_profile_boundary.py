"""Where a *vehicle* ends and a *deployment* begins.

`RobotProfile` is the platform's record of a robot. `TaskRobotSpec` is a
deployment's robot. They overlap almost entirely, and the temptation to
collapse them is constant — which is exactly why the one field that must
never cross has a test rather than a comment.

**`control_period` belongs to the deployment.** It is T_cycle: the
wall-clock budget one control step has on the target board, and therefore
gate G4's threshold and the source of the latency anchors. The same
vehicle at two sites can be held to two different cycles — a hall that
tolerates 20 Hz and a warehouse aisle that does not are two
*requirements* on one robot, not two robots. If it lived on the profile,
editing one row would widen a gate for every deployment using that
vehicle, with no new `task_profile_id` to record that the standard moved.
Nothing would warn; the runs would simply start passing.

**The accelerations belong to the vehicle**, and until now the profile
could not state them — so anybody filling a deployment form typed them
from memory, which is how one site ends up measured on a robot that
accelerates twice as hard as another site's copy of the same robot.

**Absent is not zero.** A profile written before the columns existed
never declared an acceleration, and the platform does not invent one. The
same answer HĐ-1.6 gives for an undeclared tuning: silence is a state.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from planbench_api.model_registry import RobotProfile
from planbench_schemas.robot import RobotConfig
from planbench_schemas.task_profile import TaskProfile, TaskRobotSpec

API = "/api/v1"

REPO_ROOT = Path(__file__).resolve().parents[2]


def tiny_profile() -> dict:
    """The shipped hall, as its YAML document says it."""
    return yaml.safe_load(
        (REPO_ROOT / "profiles" / "open_hall_v2.yaml").read_text(encoding="utf-8")
    )


VEHICLE = {
    "name": "Boundary AMR",
    "radius": 0.26,
    "max_linear_velocity": 0.8,
    "max_angular_velocity": 1.2,
    "max_linear_acceleration": 0.5,
    "max_angular_acceleration": 1.0,
}


class TestTheOneFieldThatMustNotCross:
    def test_control_period_is_not_on_the_robot_profile(self) -> None:
        """A gate threshold on a vehicle row is a gate anybody can widen.

        Editing one profile would move G4 for every deployment using that
        vehicle, and `episode_context_id` does not hash the robot — so
        stored runs would keep their ids while describing a standard
        nobody agreed to.
        """
        assert "control_period" not in RobotProfile.model_fields

    def test_the_deployment_robot_keeps_it(self) -> None:
        assert "control_period" in TaskRobotSpec.model_fields

    def test_the_api_will_not_accept_one_either(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        """Refused at the edge, not merely dropped on the way in.

        A request body carrying `control_period` is somebody expecting it
        to take effect. Silently ignoring it would leave them believing
        they had set a cycle time, which is worse than an error.
        """
        response = client.post(
            f"{API}/robot-profiles",
            json={**VEHICLE, "control_period": 0.05},
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_the_two_shipped_deployments_declare_their_own_cycles(self) -> None:
        """The reason the field cannot be shared, stated as data.

        One vehicle, two sites. If either profile could inherit a cycle
        from the vehicle, the pair below would have to agree — and they
        are allowed not to.
        """
        from pathlib import Path

        import yaml

        root = Path(__file__).resolve().parents[2] / "profiles"
        hall = yaml.safe_load((root / "open_hall_v2.yaml").read_text(encoding="utf-8"))
        warehouse = yaml.safe_load((root / "warehouse_a_v2.yaml").read_text(encoding="utf-8"))
        for profile in (hall, warehouse):
            assert profile["robot"]["control_period"] > 0
        # Same vehicle, stated in both files rather than referenced.
        assert hall["robot"]["radius"] == warehouse["robot"]["radius"]


class TestTheVehicleCanNowDescribeItselfCompletely:
    def test_the_profile_carries_both_accelerations(self) -> None:
        """Without them the vehicle record could not fill a deployment.

        `RobotConfig` requires both, so a form fed only from a profile
        was always going to need two numbers typed from memory.
        """
        for field in ("max_linear_acceleration", "max_angular_acceleration"):
            assert field in RobotProfile.model_fields
            assert field in RobotConfig.model_fields

    def test_a_complete_profile_fills_the_simulator_robot(self) -> None:
        """The point of the whole change, checked end to end.

        Every field `RobotConfig` needs is now available from a profile,
        so the only thing a deployment has left to declare about its
        robot is the one thing that is not about the robot.
        """
        vehicle = {key: value for key, value in VEHICLE.items() if key != "name"}
        profile = RobotProfile(id="x", name="AMR", **vehicle)
        robot = RobotConfig.model_validate(
            {name: getattr(profile, name) for name in RobotConfig.model_fields}
        )
        assert robot.max_linear_acceleration == 0.5
        assert robot.max_angular_acceleration == 1.0

    def test_round_trips_through_the_api(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        created = client.post(f"{API}/robot-profiles", json=VEHICLE, headers=alice_headers)
        assert created.status_code == 201, created.text
        fetched = client.get(
            f"{API}/robot-profiles/{created.json()['id']}", headers=alice_headers
        ).json()
        assert fetched["max_linear_acceleration"] == 0.5
        assert fetched["max_angular_acceleration"] == 1.0


class TestAbsentIsNotZero:
    def test_a_profile_may_leave_them_undeclared(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        """A vehicle whose datasheet nobody has to hand is still a vehicle.

        Refusing to record it would push people back to typing limits
        into a form, which is the habit this table exists to end.
        """
        undeclared = {k: v for k, v in VEHICLE.items() if "acceleration" not in k}
        created = client.post(f"{API}/robot-profiles", json=undeclared, headers=alice_headers)
        assert created.status_code == 201, created.text
        assert created.json()["max_linear_acceleration"] is None

    def test_undeclared_never_becomes_a_number(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        """Null must survive storage, or the silence turns into a claim.

        A zero read back would say the robot cannot accelerate; any other
        substituted value would say something the author never said and
        would then be measured as fact.
        """
        undeclared = {k: v for k, v in VEHICLE.items() if "acceleration" not in k}
        created = client.post(f"{API}/robot-profiles", json=undeclared, headers=alice_headers)
        listed = client.get(f"{API}/robot-profiles", headers=alice_headers).json()
        stored = next(entry for entry in listed if entry["id"] == created.json()["id"])
        assert stored["max_linear_acceleration"] is None
        assert stored["max_angular_acceleration"] is None

    def test_zero_is_refused_rather_than_stored(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        """The two states stay distinguishable at the edge.

        If 0 were storable it would be indistinguishable on screen from
        "not declared" for anybody reading a rendered blank — and one of
        those is a robot that cannot move.
        """
        response = client.post(
            f"{API}/robot-profiles",
            json={**VEHICLE, "max_linear_acceleration": 0},
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_the_seeded_default_declares_its_own(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        """The one profile nobody authored must not be the one that cannot deploy.

        It is the platform's own invention, and these are the numbers the
        simulator's default robot has always been driven with — so
        stating them is recording a fact, not inventing one.
        """
        listed = client.get(f"{API}/robot-profiles", headers=alice_headers).json()
        default = next(entry for entry in listed if entry["name"] == "Default AMR")
        assert default["max_linear_acceleration"] == 1.0
        assert default["max_angular_acceleration"] == 3.0


@pytest.mark.parametrize("field", sorted(RobotConfig.model_fields))
def test_every_simulator_robot_field_has_a_home_on_the_profile(field: str) -> None:
    """No silent gap between the vehicle record and what the engine needs.

    Parametrised so adding a field to `RobotConfig` fails here by name
    rather than surfacing later as a form asking for something the
    profile cannot supply.
    """
    assert field in RobotProfile.model_fields


class TestOneDeploymentIsNotTwoBecauseOfHowItWasWritten:
    """The redefinition guard compares worlds, not dictionaries.

    HĐ-2 has two legal encodings of a pose — the document form
    ``[x, y, theta]`` and the dumped form ``{"x": .., "y": ..}`` — and
    the store holds both: the API dumps a validated model, while
    ``scripts/import_runs.py`` used to file the YAML as written. A guard
    comparing raw dicts therefore called one deployment two, and re-filing
    an unchanged profile was refused with *"already exists with different
    content"* while nothing about the world had changed.

    Found by scanning for the same fault that crashed `/simulate`, not by
    hitting it: same root cause, different symptom.
    """

    def test_the_two_encodings_of_one_pose_are_one_deployment(self) -> None:
        from planbench_api.decisions import same_deployment

        document = tiny_profile()
        document["missions"] = [{"id": "m", "start": [2.0, 8.0, 0.0], "goal": [22.0, 8.0, 0.0]}]
        dumped = TaskProfile.model_validate(document).model_dump(mode="json")
        assert document["missions"][0]["start"] != dumped["missions"][0]["start"]
        assert same_deployment(document, dumped)

    def test_a_moved_goal_is_still_a_different_deployment(self) -> None:
        """The guard must not have been loosened into uselessness."""
        from planbench_api.decisions import same_deployment

        one = tiny_profile()
        other = tiny_profile()
        other["missions"] = [{"id": "m", "start": [2.0, 8.0, 0.0], "goal": [21.0, 8.0, 0.0]}]
        assert not same_deployment(one, other)

    def test_a_changed_noise_amplitude_is_a_different_world(self) -> None:
        """`episode_context_id` does not hash sensor noise (HĐ-3.1).

        Re-filing this under the same id is the exact trap the guard
        exists for, so validating both sides must not let it through.
        """
        from planbench_api.decisions import same_deployment

        one = tiny_profile()
        other = tiny_profile()
        other["environment"]["sensor_noise"] = {
            **other["environment"].get("sensor_noise", {}),
            "lidar_range_sigma_m": 0.5,
        }
        assert not same_deployment(one, other)

    def test_an_unvalidatable_document_falls_back_to_bytes(self) -> None:
        """An unanswerable question must not resolve to "same".

        The guard stops one id meaning two worlds; when neither side can
        be read as a world, refusing unless the bytes match is the safe
        direction.
        """
        from planbench_api.decisions import same_deployment

        broken = {"id": "x", "missions": "not a list"}
        assert same_deployment(broken, dict(broken))
        assert not same_deployment(broken, {"id": "x", "missions": "something else"})

    def test_refiling_an_imported_deployment_is_accepted_over_http(
        self, client: TestClient, alice_headers: dict[str, str]
    ) -> None:
        """End to end: file the document form, then the dumped form.

        This is what a user does after `scripts/import_runs.py` has
        already filed the shipped profiles — and before the fix it was a
        409 telling them their unchanged deployment had changed.
        """
        document = tiny_profile()
        document["id"] = "encoding_check"
        document["missions"] = [{"id": "m", "start": [2.0, 8.0, 0.0], "goal": [22.0, 8.0, 0.0]}]
        first = client.post(f"{API}/task-profiles", json=document, headers=alice_headers)
        assert first.status_code == 201, first.text

        dumped = TaskProfile.model_validate(document).model_dump(mode="json")
        second = client.post(f"{API}/task-profiles", json=dumped, headers=alice_headers)
        assert second.status_code == 201, second.text
        assert second.json()["id"] == "encoding_check"
