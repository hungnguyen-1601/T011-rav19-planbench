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
from planbench_api.plugin_registry import PluginBundleRecord, PluginEvent, PluginPublication
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
        """One plugin, one archive, once.

        **Keyed on the bytes, not on the label.** A candidate hashes on
        this checksum, so two rows carrying the same archive would be two
        names for one piece of code. Two rows carrying *different*
        archives are different controllers whatever their manifests call
        themselves — which is why re-uploading changed code is accepted
        even when the author left the manifest version alone.
        """
        for other in self._items.values():
            if (
                other.id != record.id
                and other.plugin_id == record.plugin_id
                and other.checksum == record.checksum
            ):
                raise RegistryError(
                    f"this exact bundle is already imported as {other.label!r} "
                    f"(revision {other.revision}). Nothing in it has changed, so there "
                    "is nothing new to measure; change the code and upload again"
                )

    def next_revision(self, plugin_id: str) -> int:
        """Which upload of this plugin the next one will be."""
        seen = [r.revision for r in self._items.values() if r.plugin_id == plugin_id]
        return max(seen, default=0) + 1

    def others_of(self, plugin_id: str, exclude_id: str) -> list[PluginBundleRecord]:
        """Every other upload of the same plugin, newest first."""
        return [
            record
            for record in self.list()
            if record.plugin_id == plugin_id and record.id != exclude_id
        ]

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


class InMemoryPluginPublicationRepository:
    """The publication history, in memory. See the SQL twin for the shape."""

    def __init__(self) -> None:
        self._items: list[PluginPublication] = []
        self._lock = threading.RLock()

    def current(self, plugin_id: str) -> PluginPublication | None:
        with self._lock:
            for row in self._items:
                if row.plugin_id == plugin_id and row.is_current:
                    return row
            return None

    def current_bundle_ids(self) -> set[str]:
        with self._lock:
            return {row.bundle_id for row in self._items if row.is_current}

    def history(self, plugin_id: str) -> list[PluginPublication]:
        with self._lock:
            return [row for row in self._items if row.plugin_id == plugin_id]

    def for_bundle(self, bundle_id: str) -> list[PluginPublication]:
        with self._lock:
            return [row for row in self._items if row.bundle_id == bundle_id]

    def publish(
        self, *, plugin_id: str, bundle_id: str, revision: int, published_by_user_id: str | None
    ) -> PluginPublication:
        with self._lock:
            stamp = now_iso()
            for index, row in enumerate(self._items):
                if row.plugin_id == plugin_id and row.is_current:
                    if row.bundle_id == bundle_id:
                        return row
                    self._items[index] = row.model_copy(update={"superseded_at": stamp})
                    break
            published = PluginPublication(
                id=new_id(),
                plugin_id=plugin_id,
                bundle_id=bundle_id,
                revision=revision,
                published_by_user_id=published_by_user_id,
                published_at=stamp,
            )
            self._items.append(published)
            return published

    def unpublish(
        self, *, plugin_id: str, unpublished_by_user_id: str | None, reason: str = ""
    ) -> PluginPublication | None:
        with self._lock:
            for index, row in enumerate(self._items):
                if row.plugin_id == plugin_id and row.is_current:
                    withdrawn = row.model_copy(
                        update={
                            "unpublished_at": now_iso(),
                            "unpublished_by_user_id": unpublished_by_user_id,
                            "reason": reason,
                        }
                    )
                    self._items[index] = withdrawn
                    return withdrawn
            return None


class InMemoryPluginEventRepository:
    def __init__(self) -> None:
        self._items: list[PluginEvent] = []
        self._lock = threading.RLock()

    def record(self, event: PluginEvent) -> PluginEvent:
        with self._lock:
            stamped = event.model_copy(
                update={
                    "sequence": len(self._items) + 1,
                    "created_at": event.created_at or now_iso(),
                }
            )
            self._items.append(stamped)
            return stamped

    def list_for_bundle(self, bundle_id: str) -> list[PluginEvent]:
        with self._lock:
            return [event for event in self._items if event.bundle_id == bundle_id]


__all__ = [
    "InMemoryModelRepository",
    "InMemoryPluginBundleRepository",
    "InMemoryPluginEventRepository",
    "InMemoryPluginPublicationRepository",
    "InMemoryRobotProfileRepository",
]
