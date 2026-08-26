"""A2 — what a round was run with, and what a cache may serve.

The checksums here are the ones a bundle pins at A7. Each test below is
a way two different runs could otherwise end up with one identity, which
is the failure that makes a calibration certify a system that never ran.
"""

from __future__ import annotations

import pytest

from planbench_analyst.cache import ResponseCache, cache_key
from planbench_analyst.identity import (
    SOURCE_GLOBS,
    ConfigRefusal,
    effective_generation_config,
    flatten_config,
    runtime_config_checksum,
    source_manifest_hash,
    validate_generation_config,
)


def checksum(**overrides):  # type: ignore[no-untyped-def]
    fields = {
        "prompt_checksum": "a" * 64,
        "generation_config": {"temperature": 0.0},
        "catalog_version": "3.1.0",
        "source_manifest_hash": "b" * 64,
    }
    fields.update(overrides)
    return runtime_config_checksum(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Flatten
# --------------------------------------------------------------------------


def test_a_dotted_key_and_a_nested_one_do_not_collide() -> None:
    """The collision this escaping exists to prevent, stated as a test.

    Flattened with dots, both of these read ``thinking.type`` and two
    different configurations get one identity.
    """
    dotted = flatten_config({"thinking.type": "enabled"})
    nested = flatten_config({"thinking": {"type": "enabled"}})
    assert dotted != nested
    assert list(dotted) == ["/thinking.type"]
    assert list(nested) == ["/thinking/type"]


def test_a_key_holding_a_slash_is_escaped() -> None:
    assert list(flatten_config({"a/b": 1})) == ["/a~1b"]
    assert list(flatten_config({"a~b": 1})) == ["/a~0b"]


def test_list_order_is_part_of_the_configuration() -> None:
    assert flatten_config({"stop": ["x", "y"]}) != flatten_config({"stop": ["y", "x"]})


def test_two_configurations_cannot_share_a_checksum() -> None:
    assert checksum(generation_config={"thinking.type": "enabled"}) != checksum(
        generation_config={"thinking": {"type": "enabled"}}
    )


# --------------------------------------------------------------------------
# Precedence and capability
# --------------------------------------------------------------------------


def test_later_layers_win_and_mappings_merge() -> None:
    merged = effective_generation_config(
        {"temperature": 0.0, "thinking": {"type": "enabled", "budget": 1024}},
        {"thinking": {"budget": 4096}},
    )
    assert merged == {"temperature": 0.0, "thinking": {"type": "enabled", "budget": 4096}}


def test_a_list_is_replaced_rather_than_appended() -> None:
    merged = effective_generation_config({"stop": ["x"]}, {"stop": ["y"]})
    assert merged == {"stop": ["y"]}


def test_a_setting_the_model_does_not_take_is_refused_before_the_call() -> None:
    """A knob that is silently ignored makes the recorded config a lie,
    and one that 400s reads from the outside as a model with nothing to
    add — which cost the advisor a day."""
    with pytest.raises(ConfigRefusal, match="thinking"):
        validate_generation_config(
            {"temperature": 0.0, "thinking": {"type": "enabled"}},
            supported=["temperature", "top_p"],
        )


def test_a_supported_configuration_passes_quietly() -> None:
    validate_generation_config({"temperature": 0.0}, supported=["temperature"])


# --------------------------------------------------------------------------
# Source manifest
# --------------------------------------------------------------------------


def test_the_source_hash_reads_bytes_and_not_mtime(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    before = source_manifest_hash(tmp_path, globs=["pyproject.toml"])
    (tmp_path / "pyproject.toml").touch()
    assert source_manifest_hash(tmp_path, globs=["pyproject.toml"]) == before
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert source_manifest_hash(tmp_path, globs=["pyproject.toml"]) != before


def test_a_file_that_does_not_exist_is_not_an_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """``docker/Dockerfile.analyst`` arrives at A7, and its arrival is a
    change of identity rather than a repair."""
    assert len(source_manifest_hash(tmp_path, globs=["docker/Dockerfile.analyst"])) == 64


def test_the_globs_cover_both_services_and_the_contract(tmp_path) -> None:  # type: ignore[no-untyped-def]
    joined = " ".join(SOURCE_GLOBS)
    assert "services/analyst_service" in joined
    assert "planbench_agent" in joined
    assert "planbench_explanation" in joined
    assert "schemas/tools" in joined


def test_a_moved_file_changes_the_hash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The path is inside the hash, not only the bytes: the same content
    imported from a different module is different code."""
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    before = source_manifest_hash(tmp_path, globs=["*.py"])
    (tmp_path / "a.py").unlink()
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    assert source_manifest_hash(tmp_path, globs=["*.py"]) != before


# --------------------------------------------------------------------------
# The cache
# --------------------------------------------------------------------------


def test_a_cache_written_under_one_identity_is_not_read_under_another() -> None:
    first = cache_key(runtime_checksum=checksum(), packet_checksum="c" * 64)
    other = cache_key(
        runtime_checksum=checksum(catalog_version="4.0.0"), packet_checksum="c" * 64
    )
    assert first != other


def test_a_hit_is_reported_rather_than_inferred(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Reading the same answer twice says nothing about whether the model
    would say it twice, so the harness has to be able to assert that a
    measured round had zero hits."""
    cache = ResponseCache(root=tmp_path)
    key = cache_key(runtime_checksum=checksum(), packet_checksum="c" * 64)
    assert cache.get(key) is None
    assert cache.stats.misses == 1 and cache.stats.hits == 0
    cache.put(key, {"abstained": False, "hypotheses": []})
    assert cache.get(key) == {"abstained": False, "hypotheses": []}
    assert cache.stats.hits == 1
    assert cache.stats.served_from_cache


def test_a_cache_with_no_root_stores_nothing_and_still_works() -> None:
    """The shape a graded run uses. If storing were the only path, the
    branch that skips it would exist only for grading — and so would
    only ever break there."""
    cache = ResponseCache()
    key = cache_key(runtime_checksum=checksum(), packet_checksum="c" * 64)
    cache.put(key, {"hypotheses": []})
    assert cache.get(key) is None
    assert cache.stats.writes == 0


def test_a_corrupt_entry_is_a_miss_and_not_a_crash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cache = ResponseCache(root=tmp_path)
    key = cache_key(runtime_checksum=checksum(), packet_checksum="c" * 64)
    (tmp_path / f"{key}.json").write_text("{not json", encoding="utf-8")
    assert cache.get(key) is None
    assert cache.stats.misses == 1
