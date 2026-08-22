"""TaskProfile meets a real map_server map (CONTRACTS HĐ-2, HĐ-4).

The loader is the cheap half. The half that matters is the refusal: a
profile whose goal sits inside a shelf produces 0% success for every
candidate, and a comparison then reports a four-way tie on a question
none of them was asked — every number well-formed, every number
meaningless.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from task_profile_fakes import make_profile

from planbench_benchmark.task_map import (
    MapLoadError,
    MapProfileMismatch,
    clear_map_cache,
    load_environment_map,
    load_task_map,
    validate_missions_on_map,
)
from planbench_schemas.map import CellState
from planbench_schemas.task_profile import EnvironmentSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPS = REPO_ROOT / "maps"

#: The contract's own deployment (HĐ-2.1): 40 x 25 m at 0.05 m.
WAREHOUSE = {"map": "maps/warehouse_a.pgm", "map_yaml": "maps/warehouse_a.yaml"}


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_map_cache()
    yield
    clear_map_cache()


def warehouse_profile(**overrides: object):
    """The contract's warehouse profile, pointed at the real map files."""
    return make_profile(environment={**WAREHOUSE, "dynamic_obstacles": []}, **overrides)


def mission(start: tuple[float, float], goal: tuple[float, float], mission_id: str = "m1"):
    return [
        {
            "id": mission_id,
            "start": [start[0], start[1], 0.0],
            "goal": [goal[0], goal[1], 0.0],
            "probability": 1.0,
        }
    ]


class TestLoading:
    def test_reference_map_matches_the_contract_example(self) -> None:
        """40 x 25 m at 0.05 m is 400 000 cells — the number HĐ-7.3's
        memory estimate is worked out against."""
        map_data = load_environment_map(
            EnvironmentSpec(**WAREHOUSE),  # type: ignore[arg-type]
            base_dir=REPO_ROOT,
        )
        assert (map_data.width, map_data.height) == (800, 500)
        assert map_data.resolution == 0.05
        assert map_data.width * map_data.height == 400_000
        assert len(map_data.cells) == 400_000
        assert map_data.name == "warehouse_a"

    def test_walls_and_floor_both_survive_the_round_trip(self) -> None:
        map_data = load_environment_map(
            EnvironmentSpec(**WAREHOUSE),  # type: ignore[arg-type]
            base_dir=REPO_ROOT,
        )
        states = set(map_data.cells)
        assert states == {CellState.FREE.value, CellState.OCCUPIED.value}

    def test_relative_paths_resolve_against_base_dir(self, tmp_path: Path) -> None:
        """A profile must mean the same thing regardless of the working
        directory it happens to be run from."""
        bundle = tmp_path / "deployment"
        (bundle / "maps").mkdir(parents=True)
        for name in ("warehouse_a.pgm", "warehouse_a.yaml"):
            (bundle / "maps" / name).write_bytes((MAPS / name).read_bytes())
        map_data = load_environment_map(
            EnvironmentSpec(**WAREHOUSE),  # type: ignore[arg-type]
            base_dir=bundle,
        )
        assert map_data.width == 800

    def test_missing_file_names_the_field(self) -> None:
        env = EnvironmentSpec(map="maps/nope.pgm", map_yaml="maps/warehouse_a.yaml")
        with pytest.raises(MapLoadError, match="field map points at"):
            load_environment_map(env, base_dir=REPO_ROOT)

    def test_missing_yaml_names_the_field(self) -> None:
        env = EnvironmentSpec(map="maps/warehouse_a.pgm", map_yaml="maps/nope.yaml")
        with pytest.raises(MapLoadError, match="field map_yaml points at"):
            load_environment_map(env, base_dir=REPO_ROOT)


class TestCache:
    def test_second_load_is_served_from_cache(self) -> None:
        env = EnvironmentSpec(**WAREHOUSE)  # type: ignore[arg-type]
        first = load_environment_map(env, base_dir=REPO_ROOT)
        assert load_environment_map(env, base_dir=REPO_ROOT) is first

    def test_editing_the_map_invalidates_it(self, tmp_path: Path) -> None:
        """A long session that reloads a profile after the map was
        regenerated must not keep planning on the previous walls."""
        (tmp_path / "maps").mkdir()
        image = tmp_path / "maps" / "warehouse_a.pgm"
        meta = tmp_path / "maps" / "warehouse_a.yaml"
        meta.write_text((MAPS / "warehouse_a.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        image.write_bytes(b"P5\n2 2\n255\n" + bytes([254, 254, 254, 254]))
        env = EnvironmentSpec(**WAREHOUSE)  # type: ignore[arg-type]
        assert load_environment_map(env, base_dir=tmp_path).cells == (0, 0, 0, 0)

        image.write_bytes(b"P5\n2 2\n255\n" + bytes([0, 0, 0, 0]))
        reloaded = load_environment_map(env, base_dir=tmp_path)
        assert set(reloaded.cells) == {CellState.OCCUPIED.value}


class TestSidecarAgreement:
    def test_yaml_naming_another_image_is_refused(self, tmp_path: Path) -> None:
        """Pixels from one map with the resolution and origin of another
        offsets every coordinate in the run, and nothing looks wrong."""
        (tmp_path / "maps").mkdir()
        (tmp_path / "maps" / "warehouse_a.pgm").write_bytes(
            b"P5\n2 2\n255\n" + bytes([254, 254, 254, 254])
        )
        (tmp_path / "maps" / "warehouse_a.yaml").write_text(
            "image: warehouse_b.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\n",
            encoding="utf-8",
        )
        env = EnvironmentSpec(**WAREHOUSE)  # type: ignore[arg-type]
        with pytest.raises(MapProfileMismatch, match="declares image"):
            load_environment_map(env, base_dir=tmp_path)

    def test_yaml_without_an_image_key_is_accepted(self, tmp_path: Path) -> None:
        """map_server allows the key to be absent; there is then nothing
        to disagree with."""
        (tmp_path / "maps").mkdir()
        (tmp_path / "maps" / "warehouse_a.pgm").write_bytes(
            b"P5\n2 2\n255\n" + bytes([254, 254, 254, 254])
        )
        (tmp_path / "maps" / "warehouse_a.yaml").write_text(
            "resolution: 0.05\norigin: [0.0, 0.0, 0.0]\n", encoding="utf-8"
        )
        env = EnvironmentSpec(**WAREHOUSE)  # type: ignore[arg-type]
        assert load_environment_map(env, base_dir=tmp_path).width == 2


class TestMissionsFitTheMap:
    def test_contract_profile_is_accepted(self) -> None:
        profile = warehouse_profile()
        load_task_map(profile, base_dir=REPO_ROOT)

    def test_goal_outside_the_map(self) -> None:
        profile = warehouse_profile(missions=mission((2.0, 3.0), (60.0, 21.0)))
        with pytest.raises(MapProfileMismatch, match="outside the map"):
            load_task_map(profile, base_dir=REPO_ROOT)

    def test_goal_inside_a_shelf(self) -> None:
        """The failure this module exists for: 0% success for every
        candidate, reported as a tie."""
        profile = warehouse_profile(missions=mission((2.0, 3.0), (8.0, 8.0)))
        with pytest.raises(MapProfileMismatch, match="occupied or unknown cell"):
            load_task_map(profile, base_dir=REPO_ROOT)

    def test_start_in_a_wall(self) -> None:
        profile = warehouse_profile(missions=mission((0.1, 0.1), (20.0, 21.0)))
        with pytest.raises(MapProfileMismatch, match="occupied or unknown cell"):
            load_task_map(profile, base_dir=REPO_ROOT)

    def test_pose_where_the_centre_fits_but_the_robot_does_not(self) -> None:
        """A goal 10 cm from a wall is reachable for a point and
        unreachable for a 0.26 m robot; the difference decides whether a
        no-path rate describes the candidate or the profile."""
        profile = warehouse_profile(missions=mission((2.0, 3.0), (20.0, 0.40)))
        with pytest.raises(MapProfileMismatch, match="less than the robot's radius"):
            load_task_map(profile, base_dir=REPO_ROOT)

    def test_goal_walled_off_from_the_start(self, tmp_path: Path) -> None:
        """A route that exists for a point but not for a 0.26 m robot:
        every candidate returns no_path, and G1 would reject the whole
        field for a property of the map."""
        (tmp_path / "maps").mkdir()
        # 4 x 2 m at 0.05 m, split by a wall with a 0.30 m doorway — wide
        # enough for the centre, too narrow for the robot.
        width, height = 80, 40
        rows = [[254] * width for _ in range(height)]
        for row in range(height):
            if not (19 <= row <= 21):
                rows[row][40] = 0
        header = f"P5\n{width} {height}\n255\n".encode("ascii")
        (tmp_path / "maps" / "warehouse_a.pgm").write_bytes(
            header + bytes(v for row in rows for v in row)
        )
        (tmp_path / "maps" / "warehouse_a.yaml").write_text(
            "image: warehouse_a.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\n",
            encoding="utf-8",
        )
        profile = warehouse_profile(missions=mission((0.5, 1.0), (3.5, 1.0)))
        with pytest.raises(MapProfileMismatch, match="no route from start to goal"):
            load_task_map(profile, base_dir=tmp_path)

    def test_reference_map_is_actually_traversable(self) -> None:
        """The check that makes the asset worth committing: the aisles
        of warehouse_a connect start to goal for this robot."""
        load_task_map(warehouse_profile(), base_dir=REPO_ROOT)

    def test_start_already_at_the_goal(self) -> None:
        profile = warehouse_profile(missions=mission((2.0, 3.0), (2.05, 3.05)))
        with pytest.raises(MapProfileMismatch, match="succeed at t=0"):
            load_task_map(profile, base_dir=REPO_ROOT)

    def test_every_problem_is_reported_at_once(self) -> None:
        """Fixing profiles one error per run is how a session gets spent
        on a map that was never going to work."""
        profile = warehouse_profile(
            missions=[
                {**mission((60.0, 3.0), (8.0, 8.0), mission_id="m1")[0], "probability": 0.5},
                {**mission((2.0, 3.0), (70.0, 21.0), mission_id="m2")[0], "probability": 0.5},
            ],
        )
        with pytest.raises(MapProfileMismatch) as excinfo:
            load_task_map(profile, base_dir=REPO_ROOT)
        message = str(excinfo.value)
        assert message.count("m1") == 2
        assert "m2" in message

    def test_validation_can_be_skipped_for_a_map_only_load(self) -> None:
        profile = warehouse_profile(missions=mission((2.0, 3.0), (8.0, 8.0)))
        assert load_task_map(profile, base_dir=REPO_ROOT, validate=False).width == 800

    def test_validate_accepts_a_map_passed_in(self) -> None:
        map_data = load_environment_map(
            EnvironmentSpec(**WAREHOUSE),  # type: ignore[arg-type]
            base_dir=REPO_ROOT,
        )
        validate_missions_on_map(warehouse_profile(), map_data)


class TestReferenceAssetStaysInSyncWithItsGenerator:
    def test_committed_pgm_is_what_the_script_produces(self, tmp_path: Path) -> None:
        """The map is committed so nothing needs a build step, and it is
        generated so the walls stay auditable. If the two drift, the map
        being benchmarked stops being the map that was described."""
        import sys

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            import make_warehouse_map as generator
        finally:
            sys.path.pop(0)

        regenerated = tmp_path / "warehouse_a.pgm"
        generator.write_pgm(regenerated, generator.build_pixels())
        assert (MAPS / "warehouse_a.pgm").read_bytes() == regenerated.read_bytes()
