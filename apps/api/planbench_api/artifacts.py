"""Artifact storage for large episode payloads and benchmark reports.

Decision D15: the database keeps metadata (URI, checksum, size); the
payload itself lives in artifact storage. This local filesystem backend
implements the interface that an object-store backend will satisfy
later, so callers never change.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from planbench_benchmark import BenchmarkReport
from planbench_simulator.nav_stack import StackRun


class ArtifactRef(BaseModel):
    """Where an artifact lives and how to verify it."""

    model_config = ConfigDict(frozen=True)

    uri: str
    checksum: str
    size_bytes: int
    content_type: str = "application/json"


class ArtifactStore(ABC):
    """Persist JSON payloads and return a verifiable reference."""

    @abstractmethod
    def write(self, key: str, payload: dict) -> ArtifactRef: ...

    @abstractmethod
    def read(self, uri: str) -> dict: ...

    def write_episode(self, benchmark_id: str, episode_id: str, run: StackRun) -> ArtifactRef:
        """Store one episode's plan, trajectory and events."""
        return self.write(
            f"benchmarks/{benchmark_id}/episodes/{episode_id}.json",
            {
                "algorithm": run.algorithm,
                "plan": run.plan.model_dump(mode="json"),
                "result": run.result.model_dump(mode="json"),
                "metrics": run.metrics.model_dump(mode="json"),
            },
        )

    def write_report(self, benchmark_id: str, report: BenchmarkReport) -> ArtifactRef:
        return self.write(f"benchmarks/{benchmark_id}/report.json", report.model_dump(mode="json"))


class FileSystemArtifactStore(ArtifactStore):
    """Store artifacts under a root directory, one JSON file per key."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"artifact key {key!r} escapes the storage root")
        return path

    def write(self, key: str, payload: dict) -> ArtifactRef:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        path.write_bytes(encoded)
        return ArtifactRef(
            uri=f"file://{path}",
            checksum=hashlib.sha256(encoded).hexdigest(),
            size_bytes=len(encoded),
        )

    def read(self, uri: str) -> dict:
        if not uri.startswith("file://"):
            raise ValueError(f"unsupported artifact URI scheme: {uri!r}")
        path = Path(uri.removeprefix("file://"))
        if not path.is_relative_to(self._root):
            raise ValueError(f"artifact URI {uri!r} escapes the storage root")
        return json.loads(path.read_text())


class InMemoryArtifactStore(ArtifactStore):
    """Test double: keeps payloads in a dict, same reference contract."""

    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}

    def write(self, key: str, payload: dict) -> ArtifactRef:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        uri = f"memory://{key}"
        self._items[uri] = encoded
        return ArtifactRef(
            uri=uri, checksum=hashlib.sha256(encoded).hexdigest(), size_bytes=len(encoded)
        )

    def read(self, uri: str) -> dict:
        try:
            return json.loads(self._items[uri])
        except KeyError:
            raise ValueError(f"unknown artifact {uri!r}") from None
