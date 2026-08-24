"""In-memory repositories for robot profiles, models and conversations.

The counterpart of the SQL versions, and the default: a checkout with no
database still runs the whole API and the whole test suite.
"""

from __future__ import annotations

import threading

from planbench_api.accounts import now_iso
from planbench_api.errors import NotFoundError
from planbench_api.model_registry import (
    ModelDocument,
    ModelRecord,
    RegistryError,
    RobotProfile,
)
from planbench_api.plugin_registry import PluginBundleRecord
from planbench_api.repositories import new_id


class InMemoryRobotProfileRepository:
    def __init__(self) -> None:
        self._items: dict[str, RobotProfile] = {}
        self._lock = threading.RLock()

    def create(self, profile: RobotProfile) -> RobotProfile:
        with self._lock:
            stamp = now_iso()
            stored = profile.model_copy(
                update={
                    "id": profile.id or new_id(),
                    "created_at": profile.created_at or stamp,
                    "updated_at": stamp,
                }
            )
            self._items[stored.id] = stored
            return stored

    def get(self, profile_id: str) -> RobotProfile:
        profile = self._items.get(profile_id)
        if profile is None:
            raise NotFoundError("robot profile", profile_id)
        return profile

    def save(self, profile: RobotProfile) -> RobotProfile:
        with self._lock:
            self.get(profile.id)
            stored = profile.model_copy(update={"updated_at": now_iso()})
            self._items[stored.id] = stored
            return stored

    def list(self) -> list[RobotProfile]:
        return sorted(self._items.values(), key=lambda profile: profile.created_at)

    def delete(self, profile_id: str) -> None:
        with self._lock:
            self.get(profile_id)
            del self._items[profile_id]


class InMemoryModelRepository:
    def __init__(self) -> None:
        self._items: dict[str, ModelRecord] = {}
        self._documents: dict[str, ModelDocument] = {}
        self._usages: list[dict] = []
        self._lock = threading.RLock()

    # -- models --------------------------------------------------------

    def create(self, record: ModelRecord) -> ModelRecord:
        with self._lock:
            stamp = now_iso()
            stored = record.model_copy(
                update={
                    "id": record.id or new_id(),
                    "created_at": record.created_at or stamp,
                    "updated_at": stamp,
                }
            )
            self._require_unique(stored)
            self._items[stored.id] = stored
            return stored

    def _require_unique(self, record: ModelRecord) -> None:
        """One person, one name, one version.

        Mirrors the SQL unique constraint. Both exist: the constraint is
        the guarantee, this is the readable error.
        """
        for other in self._items.values():
            if (
                other.id != record.id
                and other.uploaded_by_user_id == record.uploaded_by_user_id
                and other.name == record.name
                and other.version == record.version
            ):
                raise RegistryError(
                    f"you already have a model called {record.name!r} at version "
                    f"{record.version!r}; use a new version number"
                )

    def get(self, model_id: str) -> ModelRecord:
        record = self._items.get(model_id)
        if record is None:
            raise NotFoundError("model", model_id)
        return record

    def save(self, record: ModelRecord) -> ModelRecord:
        with self._lock:
            self.get(record.id)
            self._require_unique(record)
            stored = record.model_copy(update={"updated_at": now_iso()})
            self._items[stored.id] = stored
            return stored

    def list(self) -> list[ModelRecord]:
        return sorted(self._items.values(), key=lambda record: record.created_at, reverse=True)

    def list_versions(self, name: str, user_id: str) -> list[ModelRecord]:
        return sorted(
            (
                record
                for record in self._items.values()
                if record.name == name and record.uploaded_by_user_id == user_id
            ),
            key=lambda record: record.version,
        )

    def delete(self, model_id: str) -> None:
        with self._lock:
            self.get(model_id)
            del self._items[model_id]
            for document_id in [
                key for key, document in self._documents.items() if document.model_id == model_id
            ]:
                del self._documents[document_id]

    # -- documents -----------------------------------------------------

    def add_document(self, document: ModelDocument) -> ModelDocument:
        with self._lock:
            stored = document.model_copy(
                update={
                    "id": document.id or new_id(),
                    "created_at": document.created_at or now_iso(),
                }
            )
            self._documents[stored.id] = stored
            return stored

    def list_documents(self, model_id: str) -> list[ModelDocument]:
        return sorted(
            (doc for doc in self._documents.values() if doc.model_id == model_id),
            key=lambda doc: doc.created_at,
        )

    # -- usage ---------------------------------------------------------

    def record_usage(self, model_id: str, benchmark_id: str, version: str, checksum: str) -> None:
        with self._lock:
            self._usages.append(
                {
                    "model_id": model_id,
                    "benchmark_id": benchmark_id,
                    "model_version": version,
                    "model_checksum": checksum,
                    "created_at": now_iso(),
                }
            )

    def benchmarks_using(self, model_id: str) -> list[str]:
        seen: list[str] = []
        for usage in self._usages:
            if usage["model_id"] == model_id and usage["benchmark_id"] not in seen:
                seen.append(usage["benchmark_id"])
        return seen


class InMemoryPluginBundleRepository:
    """Imported algorithm bundles, in memory.

    No ``delete``. A bundle is what a benchmark *ran*: results are filed
    against its id, and removing the row turns those measurements into
    records of nothing. Disabling is the retirement path — the same rule
    the models table follows, and the reason its delete button was never
    wired up either.
    """

    def __init__(self) -> None:
        self._items: dict[str, PluginBundleRecord] = {}
        self._lock = threading.RLock()

    def create(self, record: PluginBundleRecord) -> PluginBundleRecord:
        with self._lock:
            stamp = now_iso()
            stored = record.model_copy(
                update={
                    "id": record.id or new_id(),
                    "created_at": record.created_at or stamp,
                    "updated_at": stamp,
                }
            )
            self._require_unique(stored)
            self._items[stored.id] = stored
            return stored

    def _require_unique(self, record: PluginBundleRecord) -> None:
        """One plugin id, one plugin version, once.

        Keyed on the **manifest's** identity rather than on the display
        name: two uploads declaring `org.lab.vfh-plus@0.2.0` are two
        claims to one candidate identity, and letting both in would make
        "which code produced this result?" unanswerable however carefully
        the display names differ.
        """
        for other in self._items.values():
            if (
                other.id != record.id
                and other.plugin_id == record.plugin_id
                and other.plugin_version == record.plugin_version
            ):
                raise RegistryError(
                    f"{record.plugin_id!r} version {record.plugin_version!r} is already "
                    "imported; publish a new version in the manifest rather than "
                    "replacing what a benchmark may have run"
                )

    def get(self, bundle_id: str) -> PluginBundleRecord:
        record = self._items.get(bundle_id)
        if record is None:
            raise NotFoundError("algorithm bundle", bundle_id)
        return record

    def save(self, record: PluginBundleRecord) -> PluginBundleRecord:
        with self._lock:
            self.get(record.id)
            self._require_unique(record)
            stored = record.model_copy(update={"updated_at": now_iso()})
            self._items[stored.id] = stored
            return stored

    def list(self) -> list[PluginBundleRecord]:
        return sorted(self._items.values(), key=lambda record: record.created_at, reverse=True)

    def find_by_plugin(self, plugin_id: str, plugin_version: str) -> PluginBundleRecord | None:
        for record in self._items.values():
            if record.plugin_id == plugin_id and record.plugin_version == plugin_version:
                return record
        return None


__all__ = [
    "InMemoryModelRepository",
    "InMemoryPluginBundleRepository",
    "InMemoryRobotProfileRepository",
]
