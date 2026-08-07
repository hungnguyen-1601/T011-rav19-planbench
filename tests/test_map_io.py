"""Tests for the ROS map_server (PGM + YAML) loader — F01.

Every test builds a real PGM byte string by hand (no fixture file on
disk, no image library) so the exact pixel layout under test is visible
right next to the assertion.
"""

from __future__ import annotations

import pytest

from planbench_schemas.map import CellState
from planbench_schemas.map_io import MapServerFormatError, load_map_server


def make_pgm(rows: list[list[int]], *, maxval: int = 255, ascii_format: bool = False) -> bytes:
    """Build a P5 (binary) or P2 (ASCII) PGM from pixel rows (row 0 = image top)."""
    height = len(rows)
    width = len(rows[0])
    if ascii_format:
        header = f"P2\n{width} {height}\n{maxval}\n"
        body = " ".join(str(v) for row in rows for v in row)
        return (header + body).encode("ascii")
    header = f"P5\n{width} {height}\n{maxval}\n".encode("ascii")
    body = bytes(v for row in rows for v in row)
    return header + body


def make_yaml(
    resolution: float = 0.1,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    negate: int = 0,
    occupied_thresh: float = 0.65,
    free_thresh: float = 0.196,
) -> str:
    ox, oy, otheta = origin
    return (
        f"image: map.pgm\n"
        f"resolution: {resolution}\n"
        f"origin: [{ox}, {oy}, {otheta}]\n"
        f"negate: {negate}\n"
        f"occupied_thresh: {occupied_thresh}\n"
        f"free_thresh: {free_thresh}\n"
    )


def cells_grid(map_data, width: int, height: int) -> list[list[str]]:
    return [
        [CellState(map_data.cells[row * width + col]).name for col in range(width)]
        for row in range(height)
    ]


class TestBasicParsing:
    def test_reads_dimensions_and_resolution(self) -> None:
        pgm = make_pgm([[255, 255], [255, 255]])
        m = load_map_server(pgm, make_yaml(resolution=0.05), name="tiny")
        assert m.name == "tiny"
        assert m.width == 2
        assert m.height == 2
        assert m.resolution == 0.05

    def test_all_white_is_all_free(self) -> None:
        pgm = make_pgm([[255, 255], [255, 255]])
        m = load_map_server(pgm, make_yaml(), name="free")
        assert all(c == CellState.FREE.value for c in m.cells)

    def test_all_black_is_all_occupied(self) -> None:
        pgm = make_pgm([[0, 0], [0, 0]])
        m = load_map_server(pgm, make_yaml(), name="occupied")
        assert all(c == CellState.OCCUPIED.value for c in m.cells)

    def test_midrange_grey_is_unknown(self) -> None:
        # occ = (255 - 128) / 255 ≈ 0.498, between free_thresh (0.196)
        # and occupied_thresh (0.65) — the "we don't know" band.
        pgm = make_pgm([[128, 128]])
        m = load_map_server(pgm, make_yaml(), name="unknown")
        assert all(c == CellState.UNKNOWN.value for c in m.cells)

    def test_ascii_p2_parses_the_same_as_binary_p5(self) -> None:
        rows = [[255, 0, 128], [0, 255, 0]]
        binary = load_map_server(make_pgm(rows), make_yaml(), name="a")
        ascii_ = load_map_server(make_pgm(rows, ascii_format=True), make_yaml(), name="a")
        assert binary.cells == ascii_.cells


class TestRowFlip:
    def test_pgm_top_row_becomes_the_highest_map_row(self) -> None:
        """PGM row 0 is the image top; MapData row 0 is the map origin
        (bottom). An asymmetric image proves the flip direction, not
        just that *a* flip happened."""
        rows = [
            [0, 0, 0],  # PGM top: occupied
            [255, 255, 255],
            [255, 255, 255],  # PGM bottom: free
        ]
        m = load_map_server(make_pgm(rows), make_yaml(), name="asym")
        grid = cells_grid(m, 3, 3)
        assert grid[0] == ["FREE", "FREE", "FREE"]
        assert grid[1] == ["FREE", "FREE", "FREE"]
        assert grid[2] == ["OCCUPIED", "OCCUPIED", "OCCUPIED"]


class TestNegate:
    def test_negate_flips_which_end_is_occupied(self) -> None:
        pgm = make_pgm([[255, 255]])  # white
        normal = load_map_server(pgm, make_yaml(negate=0), name="n0")
        negated = load_map_server(pgm, make_yaml(negate=1), name="n1")
        assert all(c == CellState.FREE.value for c in normal.cells)
        assert all(c == CellState.OCCUPIED.value for c in negated.cells)


class TestOrigin:
    def test_origin_xy_carried_through(self) -> None:
        m = load_map_server(make_pgm([[255]]), make_yaml(origin=(1.5, -2.5, 0.0)), name="o")
        assert m.origin.x == pytest.approx(1.5)
        assert m.origin.y == pytest.approx(-2.5)

    def test_rotated_origin_rejected_with_a_named_error(self) -> None:
        with pytest.raises(MapServerFormatError, match="rotated"):
            load_map_server(make_pgm([[255]]), make_yaml(origin=(0.0, 0.0, 0.3)), name="rot")


class TestMalformedInput:
    def test_missing_resolution_key(self) -> None:
        yaml_text = "origin: [0, 0, 0]\n"
        with pytest.raises(MapServerFormatError, match="missing required key"):
            load_map_server(make_pgm([[255]]), yaml_text, name="bad")

    def test_not_a_mapping(self) -> None:
        with pytest.raises(MapServerFormatError, match="mapping"):
            load_map_server(make_pgm([[255]]), "- just\n- a\n- list\n", name="bad")

    def test_unparseable_yaml_syntax(self) -> None:
        """yaml.YAMLError is not a ValueError — must still surface as
        MapServerFormatError, not leak past this function's contract."""
        with pytest.raises(MapServerFormatError, match="invalid YAML"):
            load_map_server(make_pgm([[255]]), "not: valid: yaml: [", name="bad")

    def test_bad_pgm_magic(self) -> None:
        garbage = b"NOTAPGM\n1 1\n255\n\xff"
        with pytest.raises(MapServerFormatError, match="not a PGM"):
            load_map_server(garbage, make_yaml(), name="bad")

    def test_truncated_pgm_body(self) -> None:
        header = b"P5\n4 4\n255\n"
        with pytest.raises(MapServerFormatError, match="too short"):
            load_map_server(header + b"\xff\xff", make_yaml(), name="bad")

    def test_pgm_with_a_comment_line_in_the_header(self) -> None:
        data = b"P5\n# a comment\n2 2\n255\n" + bytes([255, 255, 0, 0])
        m = load_map_server(data, make_yaml(), name="commented")
        assert m.width == 2
        assert m.height == 2


class TestThresholds:
    def test_custom_thresholds_change_the_boundary(self) -> None:
        # occ(pixel=100) = (255-100)/255 ≈ 0.608. Default occupied_thresh
        # 0.65 -> UNKNOWN; a lower threshold of 0.5 -> OCCUPIED.
        pgm = make_pgm([[100]])
        default = load_map_server(pgm, make_yaml(), name="d")
        assert default.cells[0] == CellState.UNKNOWN.value
        stricter = load_map_server(pgm, make_yaml(occupied_thresh=0.5), name="s")
        assert stricter.cells[0] == CellState.OCCUPIED.value
