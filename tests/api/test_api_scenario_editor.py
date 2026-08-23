"""API tests for the scenario editor (plan 2.3).

The editor is a way to author benchmark conditions, so the tests are
mostly about the boundaries around it rather than the CRUD:

- what the author is *not* allowed to decide (the evaluation split, the
  difficulty),
- that the browser is never the thing that approves geometry,
- that editing a scenario cannot rewrite what an already-stored
  benchmark ran under,
- and that the preview shows the same motion the simulator will run.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from payloads import bordered_map_payload, scenario_payload

from planbench_benchmark import get_difficulty, scenario_split
from planbench_schemas.dynamic import DynamicObstacle, WaypointMotion, position_at
from planbench_schemas.geometry import Point2D


def _walker(name: str = "walker", seed_time_offset: float = 10.0) -> dict:
    return DynamicObstacle(
        name=name,
        radius=0.35,
        motion=WaypointMotion(
            waypoints=(Point2D(x=6.0, y=2.0), Point2D(x=6.0, y=9.0)),
            speed=0.6,
            ping_pong=True,
        ),
        seed_time_offset=seed_time_offset,
    ).model_dump(mode="json")


def _create(client: TestClient, map_id: str, **overrides) -> dict:
    response = client.post(
        "/api/v1/scenarios",
        json={"map_id": map_id, "scenario": scenario_payload(**overrides)},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestWhatTheAuthorMayNotDecide:
    def test_a_new_scenario_is_unassigned(self, client: TestClient, created_map: dict) -> None:
        """Authoring a scenario must not quietly grow the dev set (P05)."""
        created = _create(client, created_map["id"], name="editor_made_this")
        assert created["split"] == "unassigned"
        assert scenario_split("editor_made_this") == "unassigned"

    def test_split_cannot_be_set_through_the_scenario_body(
        self, client: TestClient, created_map: dict
    ) -> None:
        """Even if a client sends one. The split is not part of a scenario.

        This is the request an author unhappy with a result would make,
        and it must not work: the split is resolved from the reviewed
        protocol file, never from the payload.
        """
        payload = scenario_payload(name="wants_to_be_dev")
        payload["split"] = "dev"
        response = client.post(
            "/api/v1/scenarios", json={"map_id": created_map["id"], "scenario": payload}
        )
        assert response.status_code == 201, response.text
        assert response.json()["split"] == "unassigned"
        assert "split" not in response.json()["scenario"]

    def test_a_new_scenario_has_no_difficulty(self, client: TestClient, created_map: dict) -> None:
        """Uncalibrated is the truth about a scenario nobody has run (P03)."""
        _create(client, created_map["id"], name="brand_new_scenario")
        assert get_difficulty("brand_new_scenario") is None

    def test_editing_does_not_rewrite_a_stored_benchmark(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        """A stored result keeps the conditions it ran under.

        The editor changes what *future* benchmarks run. If editing a
        scenario also moved the fairness record of results already
        produced, two reports would silently stop being comparable.
        """
        imported = client.post(
            "/api/v1/scenario-library/open_space/import", headers=alice_headers
        ).json()
        created = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "before-edit",
                "map_id": imported["map_id"],
                "scenario_id": imported["scenario_id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=alice_headers,
        ).json()
        run = client.post(f"/api/v1/benchmarks/{created['id']}/run", headers=alice_headers).json()
        checksum = run["report"]["fairness"]["conditions_checksum"]

        scenario = imported["scenario"]
        scenario["goal_pose"] = {"x": 9.0, "y": 4.5, "theta": 0.0}
        updated = client.put(
            f"/api/v1/scenarios/{imported['scenario_id']}",
            json={"map_id": imported["map_id"], "scenario": scenario},
        )
        assert updated.status_code == 200, updated.text

        stored = client.get(
            f"/api/v1/benchmarks/{created['id']}/results", headers=alice_headers
        ).json()
        assert stored["report"]["fairness"]["conditions_checksum"] == checksum
        # And the edit did land: the test is about the stored result being
        # frozen, not about the update quietly failing.
        assert updated.json()["scenario"]["goal_pose"]["x"] == 9.0


class TestValidationIsTheEnginesJob:
    def test_validate_accepts_a_workable_scenario(
        self, client: TestClient, created_map: dict
    ) -> None:
        response = client.post(
            "/api/v1/scenarios/validate",
            json={"map_id": created_map["id"], "scenario": scenario_payload()},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"valid": True, "errors": []}

    def test_validate_rejects_a_start_inside_a_wall(
        self, client: TestClient, created_map: dict
    ) -> None:
        response = client.post(
            "/api/v1/scenarios/validate",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(start_pose={"x": 0.5, "y": 0.5, "theta": 0.0}),
            },
        )
        body = response.json()
        assert body["valid"] is False
        assert body["errors"], "a rejection with no reason is not usable in an editor"
        assert "start" in body["errors"][0]

    def test_validate_rejects_a_start_inside_an_authored_obstacle(
        self, client: TestClient, created_map: dict
    ) -> None:
        """Obstacles the author just drew count, not only the map's walls."""
        response = client.post(
            "/api/v1/scenarios/validate",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(
                    static_obstacles=[
                        {"type": "circle", "center": {"x": 2.5, "y": 2.5}, "radius": 0.5}
                    ]
                ),
            },
        )
        assert response.json()["valid"] is False

    def test_validate_and_save_agree(self, client: TestClient, created_map: dict) -> None:
        """The editor's check is the same check the save performs.

        If they could disagree, an author would be told their scenario is
        fine and then be refused on save for a rule nobody showed them.
        """
        payload = scenario_payload(start_pose={"x": 0.5, "y": 0.5, "theta": 0.0})
        verdict = client.post(
            "/api/v1/scenarios/validate", json={"map_id": created_map["id"], "scenario": payload}
        ).json()
        saved = client.post(
            "/api/v1/scenarios", json={"map_id": created_map["id"], "scenario": payload}
        )
        assert verdict["valid"] is False
        assert saved.status_code == 422, saved.text

    def test_a_scenario_that_validates_can_be_saved(
        self, client: TestClient, created_map: dict
    ) -> None:
        payload = scenario_payload(name="drawn_in_the_editor", dynamic_obstacles=[_walker()])
        verdict = client.post(
            "/api/v1/scenarios/validate", json={"map_id": created_map["id"], "scenario": payload}
        ).json()
        assert verdict["valid"] is True
        saved = client.post(
            "/api/v1/scenarios", json={"map_id": created_map["id"], "scenario": payload}
        )
        assert saved.status_code == 201, saved.text
        assert len(saved.json()["scenario"]["dynamic_obstacles"]) == 1


class TestPreviewShowsWhatWillRun:
    def test_positions_match_the_simulators_own_motion(
        self, client: TestClient, created_map: dict
    ) -> None:
        """The whole reason the preview is a backend call.

        A second implementation of the motion laws in the browser would
        drift from this one, and the author would place a start pose
        clear of an obstacle that is somewhere else when the episode runs.
        """
        obstacle = _walker()
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(dynamic_obstacles=[obstacle]),
                "time": 4.0,
                "seed": 7,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        expected = position_at(DynamicObstacle.model_validate(obstacle), 4.0, 7)
        drawn = body["dynamic_obstacles"][0]["position"]
        assert drawn["x"] == pytest.approx(expected.x)
        assert drawn["y"] == pytest.approx(expected.y)
        assert body["time"] == 4.0
        assert body["seed"] == 7

    def test_asking_for_a_duration_returns_the_whole_route(
        self, client: TestClient, created_map: dict
    ) -> None:
        """**One call, not one per frame.**

        A still frame answers "is the cart in my way at t = 12" and not
        "where is it heading", which is the question an author placing a
        start pose actually has. Animating by calling this endpoint per
        frame would be a round trip every 40 ms; sampling the same pure
        `position_at` here is one reply and cannot drift from it.
        """
        obstacle = _walker()
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(dynamic_obstacles=[obstacle]),
                "duration": 4.0,
                "step": 1.0,
                "seed": 7,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        track = body["dynamic_obstacles"][0]["track"]
        # t = 0, 1, 2, 3, 4: five positions, not four. The sample at zero
        # is a position, not a fencepost.
        assert len(track) == 5
        assert body["duration"] == pytest.approx(4.0)
        assert body["step"] == pytest.approx(1.0)

    def test_every_sampled_point_is_the_simulators_own(
        self, client: TestClient, created_map: dict
    ) -> None:
        """The track has to be the same law as the still frame, or the
        preview animates one world and stops on another."""
        obstacle = _walker()
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(dynamic_obstacles=[obstacle]),
                "duration": 3.0,
                "step": 1.5,
                "seed": 7,
            },
        )
        track = response.json()["dynamic_obstacles"][0]["track"]
        parsed = DynamicObstacle.model_validate(obstacle)
        for index, point in enumerate(track):
            expected = position_at(parsed, index * 1.5, 7)
            assert point["x"] == pytest.approx(expected.x)
            assert point["y"] == pytest.approx(expected.y)

    def test_the_track_starts_at_zero_not_at_the_requested_instant(
        self, client: TestClient, created_map: dict
    ) -> None:
        """`time` is where the scrubber is parked; the track is the whole
        episode. Starting it at `time` would make a preview scrubbed to
        t = 40 unable to show anything before t = 40."""
        obstacle = _walker()
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(dynamic_obstacles=[obstacle]),
                "time": 4.0,
                "duration": 2.0,
                "step": 1.0,
                "seed": 7,
            },
        )
        track = response.json()["dynamic_obstacles"][0]["track"]
        parsed = DynamicObstacle.model_validate(obstacle)
        at_zero = position_at(parsed, 0.0, 7)
        assert track[0]["x"] == pytest.approx(at_zero.x)
        assert track[0]["y"] == pytest.approx(at_zero.y)

    def test_no_duration_still_answers_with_one_frame(
        self, client: TestClient, created_map: dict
    ) -> None:
        """The shape this endpoint had before playback existed. A caller
        that wants one instant should not pay for a track."""
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(dynamic_obstacles=[_walker()]),
                "time": 2.0,
                "seed": 7,
            },
        )
        body = response.json()
        assert body["dynamic_obstacles"][0]["track"] == []
        assert body["duration"] == 0.0

    def test_refuses_a_duration_long_enough_to_be_a_mistake(
        self, client: TestClient, created_map: dict
    ) -> None:
        """Ten minutes at the finest step is a hundred and eighty
        thousand points per obstacle. The cap is a refusal rather than a
        silent clamp: a reply covering less than what was asked for,
        with nothing saying so, is the same lie as a canvas labelled
        t = 40 showing t = 0."""
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(dynamic_obstacles=[_walker()]),
                "duration": 6000.0,
                "seed": 7,
            },
        )
        assert response.status_code == 422

    def test_the_obstacle_actually_moves_between_instants(
        self, client: TestClient, created_map: dict
    ) -> None:
        def at(time: float) -> dict:
            return client.post(
                "/api/v1/scenarios/preview",
                json={
                    "map_id": created_map["id"],
                    "scenario": scenario_payload(dynamic_obstacles=[_walker()]),
                    "time": time,
                },
            ).json()["dynamic_obstacles"][0]["position"]

        assert at(0.0) != at(5.0)

    def test_the_seed_changes_the_timing(self, client: TestClient, created_map: dict) -> None:
        """Traffic timing is seeded, so one preview is one episode.

        A preview that looked identical for every seed would invite the
        author to treat it as the whole story.
        """

        def at(seed: int) -> dict:
            return client.post(
                "/api/v1/scenarios/preview",
                json={
                    "map_id": created_map["id"],
                    "scenario": scenario_payload(dynamic_obstacles=[_walker()]),
                    "time": 3.0,
                    "seed": seed,
                },
            ).json()["dynamic_obstacles"][0]["position"]

        assert at(0) != at(11)

    def test_zero_seed_spread_replays_identically(
        self, client: TestClient, created_map: dict
    ) -> None:
        """The artefact the editor warns about, pinned down here."""

        def at(seed: int) -> dict:
            return client.post(
                "/api/v1/scenarios/preview",
                json={
                    "map_id": created_map["id"],
                    "scenario": scenario_payload(dynamic_obstacles=[_walker(seed_time_offset=0.0)]),
                    "time": 3.0,
                    "seed": seed,
                },
            ).json()["dynamic_obstacles"][0]["position"]

        assert at(0) == at(11)

    def test_preview_reports_invalidity_without_refusing_to_draw(
        self, client: TestClient, created_map: dict
    ) -> None:
        """An author fixing a bad layout still needs to see the layout."""
        response = client.post(
            "/api/v1/scenarios/preview",
            json={
                "map_id": created_map["id"],
                "scenario": scenario_payload(
                    start_pose={"x": 0.5, "y": 0.5, "theta": 0.0},
                    dynamic_obstacles=[_walker()],
                ),
                "time": 1.0,
            },
        )
        body = response.json()
        assert body["valid"] is False
        assert body["errors"]
        assert len(body["dynamic_obstacles"]) == 1

    def test_a_scenario_without_traffic_previews_empty(
        self, client: TestClient, created_map: dict
    ) -> None:
        body = client.post(
            "/api/v1/scenarios/preview",
            json={"map_id": created_map["id"], "scenario": scenario_payload(), "time": 2.0},
        ).json()
        assert body["dynamic_obstacles"] == []
        assert body["valid"] is True

    def test_negative_time_is_refused(self, client: TestClient, created_map: dict) -> None:
        response = client.post(
            "/api/v1/scenarios/preview",
            json={"map_id": created_map["id"], "scenario": scenario_payload(), "time": -1.0},
        )
        assert response.status_code == 422


class TestEditingLifecycle:
    def test_update_replaces_the_layout_and_keeps_the_id(
        self, client: TestClient, created_map: dict
    ) -> None:
        created = _create(client, created_map["id"], name="draft_one")
        scenario = scenario_payload(
            name="draft_one",
            static_obstacles=[{"type": "circle", "center": {"x": 6.0, "y": 6.0}, "radius": 0.5}],
        )
        updated = client.put(
            f"/api/v1/scenarios/{created['id']}",
            json={"map_id": created_map["id"], "scenario": scenario},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["id"] == created["id"]
        assert len(updated.json()["scenario"]["static_obstacles"]) == 1
        assert updated.json()["split"] == "unassigned"

    def test_update_runs_the_same_validation(self, client: TestClient, created_map: dict) -> None:
        created = _create(client, created_map["id"], name="draft_two")
        broken = scenario_payload(name="draft_two", start_pose={"x": 0.5, "y": 0.5, "theta": 0.0})
        response = client.put(
            f"/api/v1/scenarios/{created['id']}",
            json={"map_id": created_map["id"], "scenario": broken},
        )
        assert response.status_code == 422

    def test_delete_removes_it_from_the_list(self, client: TestClient, created_map: dict) -> None:
        created = _create(client, created_map["id"], name="temporary")
        assert client.delete(f"/api/v1/scenarios/{created['id']}").status_code == 204
        listed = {item["id"] for item in client.get("/api/v1/scenarios").json()}
        assert created["id"] not in listed

    def test_an_authored_scenario_can_be_benchmarked(
        self, client: TestClient, alice_headers: dict
    ) -> None:
        """The point of the editor: a scenario drawn here is a real one.

        It runs through the same benchmark path as a library scenario,
        and the report records it as unassigned — so it contributes no
        generalization claim until someone classifies it.
        """
        stored_map = client.post("/api/v1/maps", json=bordered_map_payload()).json()
        scenario = _create(
            client,
            stored_map["id"],
            name="authored_for_benchmark",
            dynamic_obstacles=[_walker()],
        )
        created = client.post(
            "/api/v1/benchmarks",
            json={
                "name": "authored-run",
                "map_id": stored_map["id"],
                "scenario_id": scenario["id"],
                "algorithms": [{"id": "astar+dwa"}],
                "seeds": [1],
            },
            headers=alice_headers,
        )
        assert created.status_code == 201, created.text
        run = client.post(f"/api/v1/benchmarks/{created.json()['id']}/run", headers=alice_headers)
        assert run.status_code == 200, run.text
        assert run.json()["report"]["scenario_split"] == "unassigned"
