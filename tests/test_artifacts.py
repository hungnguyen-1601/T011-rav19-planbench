"""Tests for artifact storage (metadata + checksum contract, D15)."""

from __future__ import annotations

import json

import pytest

from planbench_api.artifacts import FileSystemArtifactStore, InMemoryArtifactStore


class TestFileSystemStore:
    def test_write_returns_verifiable_reference(self, tmp_path) -> None:
        store = FileSystemArtifactStore(tmp_path)
        ref = store.write("a/b.json", {"hello": "world"})
        assert ref.uri.startswith("file://")
        assert len(ref.checksum) == 64
        assert ref.size_bytes > 0
        assert store.read(ref.uri) == {"hello": "world"}

    def test_checksum_matches_the_bytes_on_disk(self, tmp_path) -> None:
        import hashlib

        store = FileSystemArtifactStore(tmp_path)
        ref = store.write("x.json", {"k": [1, 2, 3]})
        path = ref.uri.removeprefix("file://")
        with open(path, "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == ref.checksum

    def test_serialization_is_canonical(self, tmp_path) -> None:
        """Same content, different key order -> identical checksum."""
        store = FileSystemArtifactStore(tmp_path)
        first = store.write("one.json", {"a": 1, "b": 2})
        second = store.write("two.json", {"b": 2, "a": 1})
        assert first.checksum == second.checksum

    def test_key_cannot_escape_the_root(self, tmp_path) -> None:
        store = FileSystemArtifactStore(tmp_path / "root")
        with pytest.raises(ValueError, match="escapes the storage root"):
            store.write("../outside.json", {})

    def test_read_rejects_foreign_uri(self, tmp_path) -> None:
        store = FileSystemArtifactStore(tmp_path)
        with pytest.raises(ValueError, match="unsupported artifact URI"):
            store.read("s3://bucket/key")

    def test_nested_directories_are_created(self, tmp_path) -> None:
        store = FileSystemArtifactStore(tmp_path)
        ref = store.write("benchmarks/b1/episodes/e1.json", {"n": 1})
        with open(ref.uri.removeprefix("file://")) as handle:
            assert json.load(handle) == {"n": 1}


class TestInMemoryStore:
    def test_round_trip(self) -> None:
        store = InMemoryArtifactStore()
        ref = store.write("k.json", {"v": 1})
        assert store.read(ref.uri) == {"v": 1}

    def test_unknown_uri_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown artifact"):
            InMemoryArtifactStore().read("memory://nope")

    def test_same_reference_contract_as_filesystem(self, tmp_path) -> None:
        payload = {"a": [1, 2], "b": "x"}
        memory = InMemoryArtifactStore().write("k.json", payload)
        disk = FileSystemArtifactStore(tmp_path).write("k.json", payload)
        assert memory.checksum == disk.checksum
        assert memory.size_bytes == disk.size_bytes
