"""Importing an algorithm bundle, and asking whether it could run here.

Two things happen in this module and neither of them executes a plugin.
A bundle is stored and its manifest is read (P1); preflight then answers
"could this run on this deployment?" from the manifest and the provider
graph alone. Extraction and the conformance run are P2's, and the
ordering is the point — see `docs/plugin_import_security.md` §1.

**A bundle whose manifest does not parse is refused rather than stored
as FAILED.** That is the one place this diverges from the model
registry, and it is not a stylistic difference. A model's identity comes
from the form its uploader filled in, so a broken checkpoint still has a
row to hang an explanation on. A bundle's identity comes from the
manifest — no manifest, no `plugin_id`, and a table keyed on
`(plugin_id, plugin_version)` would collide the second unreadable upload
against the first. Refusing at the door keeps identity meaningful and
still tells the uploader every problem at once.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from planbench_api.accounts import User
from planbench_api.model_registry import (
    ModelStatus,
    RegistryError,
    ValidationStatus,
    sanitise_filename,
)
from planbench_api.model_storage import ModelStorage
from planbench_api.plugin_registry import (
    PluginBundleRecord,
    PluginNotAllowed,
    inspect_bundle,
)
from planbench_api.plugin_runtime import install_bundle, run_conformance
from planbench_api.repositories import new_id

logger = logging.getLogger("planbench.api.plugins")


@dataclass(frozen=True)
class PluginLimits:
    """The ceilings from settings, carried as one argument.

    Grouped rather than passed as four numbers because they are read
    together and changed together, and because a call site that had to
    name all four would be one that quietly forgot the fourth.
    """

    max_upload_bytes: int
    max_members: int
    max_extracted_bytes: int
    max_manifest_bytes: int


class HostCompatibility(BaseModel):
    """Preflight's answer, in a shape a JSON client can read.

    A projection of the host's ``CompatibilityReport`` dataclass, not a
    second opinion: every field here is copied, none is derived, and
    ``why`` is the host's own ``explain()``. The UI renders these; it
    does not restate them in friendlier words, because the friendlier
    words would be this layer inventing a diagnosis.
    """

    model_config = ConfigDict(frozen=True)

    state: str
    runnable: bool
    evidence_class: str
    runtime_lane: str
    why: str
    missing_capabilities: tuple[str, ...] = ()
    missing_providers: tuple[str, ...] = ()
    missing_runtime: tuple[str, ...] = ()
    incompatible_action_types: tuple[str, ...] = ()
    incompatible_dynamics: tuple[str, ...] = ()
    incompatible_execution_models: tuple[str, ...] = ()
    fairness_refusals: tuple[str, ...] = ()
    undeclared_providers: tuple[str, ...] = ()
    graph_problems: tuple[str, ...] = ()
    provider_order: tuple[str, ...] = ()
    oracle_providers: tuple[str, ...] = ()


def storage_key(user_id: str, bundle_id: str, version: str, filename: str) -> str:
    """Where a bundle's archive belongs.

    Built entirely from ids. The filename rides along for display and
    does not choose a location, so a hostile name cannot escape — the
    same rule `model_storage.storage_key` follows, and a separate prefix
    so the two never share a directory.
    """
    safe_version = version.replace("/", "_").replace("\\", "_") or "1"
    return f"plugins/{user_id or 'anonymous'}/{bundle_id}/{safe_version}/{filename}"


class PluginBundleService:
    """Imported algorithms: taking them in, and reading them back."""

    def __init__(
        self,
        bundles: Any,
        profiles: Any,
        storage: ModelStorage,
        *,
        limits: PluginLimits,
        install_root: Path,
    ) -> None:
        self._bundles = bundles
        self._profiles = profiles
        self._storage = storage
        self._limits = limits
        self._install_root = install_root

    # -- writing -------------------------------------------------------

    def upload(
        self,
        *,
        owner: User,
        name: str,
        version: str,
        description: str,
        robot_profile_id: str,
        filename: str,
        chunks: Iterator[bytes],
    ) -> PluginBundleRecord:
        """Store an archive, read its manifest, register it.

        The order is load-bearing. The extension is checked before a byte
        is written, the size limit is enforced *while* writing, and the
        manifest is read afterwards from the stored bytes — so what gets
        registered is what landed on disk rather than what a second read
        of the request would have said.
        """
        _require_admin(owner)
        if not name.strip():
            raise RegistryError("the algorithm needs a name")
        safe_name = sanitise_filename(filename)
        if not safe_name.lower().endswith(".zip"):
            raise RegistryError(
                "an algorithm bundle is a .zip of the directory holding your planner "
                "and its .planbench-plugin/plugin.json"
            )

        profile = self._profiles.get(robot_profile_id)  # 404 if unknown
        bundle_id = new_id()
        version = (version or "1").strip()
        key = storage_key(owner.id, bundle_id, version, safe_name)
        stored = self._storage.save(key, chunks, max_bytes=self._limits.max_upload_bytes)

        try:
            inspection = inspect_bundle(
                self._storage.open(key),
                max_members=self._limits.max_members,
                max_extracted_bytes=self._limits.max_extracted_bytes,
                max_manifest_bytes=self._limits.max_manifest_bytes,
            )
            if inspection.manifest is None:
                # No identity, so nothing to file the explanation against.
                raise RegistryError("; ".join(inspection.problems))

            from planbench_plugin_sdk import manifest_checksum, parse_manifest

            manifest = parse_manifest(inspection.manifest, source=safe_name)
            profile_spec = manifest.runtime.profiles.get(manifest.runtime.production_lane)
            record = PluginBundleRecord(
                id=bundle_id,
                name=name.strip(),
                version=version,
                description=description.strip(),
                plugin_id=manifest.id,
                plugin_version=manifest.version,
                role=manifest.role,
                entry_point=profile_spec.entry_point if profile_spec else "",
                manifest=inspection.manifest,
                manifest_checksum=manifest_checksum(inspection.manifest),
                package_dir=inspection.package_dir,
                storage_key=stored.storage_key,
                original_filename=safe_name,
                file_size=stored.size_bytes,
                checksum=stored.checksum,
                uploaded_by_user_id=owner.id,
                robot_profile_id=profile.id,
                # The archive is a bundle. Whether the plugin *behaves*
                # is the conformance run's verdict (P2), and claiming it
                # here would be a structural check wearing a behavioural
                # check's name.
                validation_status=ValidationStatus.STRUCTURAL,
                validation_message="the archive is a well-formed plugin bundle",
            )
            created = self._bundles.create(record)
        except BaseException:
            # No orphaned bytes: a refused upload must not leave its file
            # behind consuming disk nobody can account for.
            self._storage.delete(key)
            raise
        # Unpack and run it now rather than leaving that to a second
        # click. An importer wants to know whether the thing works, and
        # a registry full of rows nobody has ever run is a registry whose
        # statuses mean "not looked at yet" — which is what `structural`
        # already says without anybody being told to go and check.
        return self.validate(created.id)

    def revalidate(self, bundle_id: str, user: User) -> PluginBundleRecord:
        """`validate`, asked for by a person.

        Gated on the import privilege rather than the read one: this
        starts the uploader's code, and who may do that is the question
        §5 of the threat model answers.
        """
        _require_admin(user)
        return self.validate(bundle_id)

    def validate(self, bundle_id: str) -> PluginBundleRecord:
        """Unpack the bundle and put the plugin through the suite.

        Separate from `upload` and callable again on purpose: a bundle
        that could not be checked when it arrived — because a dependency
        was missing, or a provider was — is worth re-asking about once
        the deployment has changed, and re-asking must not mean
        re-uploading.
        """
        record = self._bundles.get(bundle_id)
        profile = self._profiles.get(record.robot_profile_id)
        try:
            directory = install_bundle(record, self._storage, self._install_root)
            outcome = run_conformance(record, profile, directory)
        except RegistryError as error:
            # Unpacking failed, which is a fact about the archive rather
            # than about the plugin's behaviour — so it is `failed`, and
            # it says which.
            return self._bundles.save(
                record.model_copy(
                    update={
                        "validation_status": ValidationStatus.FAILED,
                        "validation_message": str(error),
                    }
                )
            )
        saved = self._bundles.save(
            record.model_copy(
                update={
                    "validation_status": outcome.status,
                    "validation_message": outcome.message,
                }
            )
        )
        self.sync_catalogue()
        return saved

    def update(self, bundle_id: str, changes: dict[str, Any], user: User) -> PluginBundleRecord:
        """Rename, re-describe, enable or disable.

        Never the manifest and never the file. Both are identity: a
        bundle that could be edited in place would let one `plugin_id` at
        one version mean two different pieces of code, and every result
        recorded against it would stop being attributable.
        """
        record = self._bundles.get(bundle_id)
        _require_owner_or_admin(record, user)
        allowed = {"name", "version", "description", "status", "robot_profile_id"}
        unknown = sorted(set(changes) - allowed)
        if unknown:
            raise RegistryError(f"these fields cannot be changed after import: {unknown}")
        if "status" in changes:
            changes = {**changes, "status": ModelStatus(changes["status"])}
        if "robot_profile_id" in changes:
            self._profiles.get(changes["robot_profile_id"])
        saved = self._bundles.save(record.model_copy(update=changes))
        # Disabling one is how a plugin is retired, so the catalogue has
        # to hear about it here as well as at import.
        self.sync_catalogue()
        return saved

    def sync_catalogue(self) -> list[str]:
        """Publish every runnable bundle as a stack this process offers."""
        return sync_catalogue(self._bundles, self._install_root)

    # -- reading -------------------------------------------------------

    def list(self) -> list[PluginBundleRecord]:
        return self._bundles.list()

    def get(self, bundle_id: str) -> PluginBundleRecord:
        return self._bundles.get(bundle_id)

    def compatibility(self, bundle_id: str) -> HostCompatibility:
        """Could this run here — asked now, not remembered from import.

        Recomputed on every read on purpose. A deployment can gain or
        lose a provider between the upload and the question, so a stored
        verdict would be a claim about a host that no longer exists.
        """
        record = self._bundles.get(bundle_id)
        return host_compatibility(record.manifest)


def host_compatibility(manifest_data: dict[str, Any]) -> HostCompatibility:
    """Run the host's own preflight over a stored manifest.

    Imports the simulator lazily: the model registry does not need it,
    and paying for it on every API import would make an unrelated
    endpoint slower to serve.
    """
    from planbench_plugin_sdk import parse_manifest

    from planbench_simulator.host.compatibility import HostSupport, resolve_compatibility
    from planbench_simulator.host.fairness_policy import FairnessPolicy
    from planbench_simulator.host.provider_graph import ProviderGraph
    from planbench_simulator.host.providers import builtin_providers, builtin_registry

    manifest = parse_manifest(manifest_data, source="<stored manifest>")
    graph = ProviderGraph(builtin_providers(include_oracle=False), builtin_registry())
    report = resolve_compatibility(
        manifest,
        available_capabilities=frozenset(),
        graph=graph,
        policy=FairnessPolicy.production(),
        support=HostSupport(),
    )
    return HostCompatibility(
        state=str(report.state),
        runnable=report.runnable,
        evidence_class=str(report.evidence_class),
        runtime_lane=str(report.resolved_runtime_profile.get("lane", "")),
        why=report.explain(),
        missing_capabilities=report.missing_capabilities,
        missing_providers=report.missing_providers,
        missing_runtime=report.missing_runtime,
        incompatible_action_types=report.incompatible_action_types,
        incompatible_dynamics=report.incompatible_dynamics,
        incompatible_execution_models=report.incompatible_execution_models,
        fairness_refusals=report.fairness_refusals,
        undeclared_providers=report.undeclared_providers,
        graph_problems=report.graph_problems,
        provider_order=report.provider_order,
        oracle_providers=tuple(capability for capability, _ in report.ownership.oracle_owned),
    )


def sync_catalogue(bundles: Any, install_root: Path) -> list[str]:
    """Make the runtime catalogue match the stored bundles. Returns ids.

    **Driven by writes, not by reads.** The set of offerable stacks
    changes when somebody imports, re-validates or disables a bundle, and
    at nothing else — so this is called from those three places plus
    once at startup, rather than on every request that happens to list
    algorithms. A read path that rebuilt the catalogue would make
    "what does this platform offer?" depend on who asked last.

    Rebuilt wholesale rather than patched: re-registering over a stale
    entry would leave a disabled plugin still offerable under its old
    factory, which is the one direction this must not fail in.

    A bundle that cannot be turned into a stack is skipped rather than
    raised on. It is already visible in the plugins tab with the reason
    it cannot run; taking the whole catalogue down with it would hide
    every other algorithm behind one bad import.
    """
    from planbench_api.plugin_runtime import install_root as bundle_directory
    from planbench_benchmark.plugin_stacks import build_plugin_entries
    from planbench_benchmark.registry import clear_external, register_external

    clear_external()
    registered: list[str] = []
    try:
        stored = bundles.list()
    except Exception:  # noqa: BLE001 - the store, not a bundle
        # **A catalogue that cannot be read must not take the API down.**
        #
        # This runs at startup, before anything has been served, so an
        # exception here is not "imported algorithms are unavailable" —
        # it is the whole process failing to start. A database one
        # migration behind did exactly that: `plugin_bundles` did not
        # exist, the query raised, and `create_app` died on import with a
        # SQL traceback that named nothing a reader could act on.
        #
        # Logged rather than swallowed, and logged with the fix in it:
        # this is almost always a schema that has not had `alembic
        # upgrade head` run against it, and the operator needs that
        # sentence rather than a stack trace.
        logger.warning(
            "imported algorithms are unavailable: the plugin_bundles table could not be "
            "read. If this deployment has just taken an update, run 'alembic upgrade head'. "
            "Everything else works; no imported algorithm will be offered until it does.",
            exc_info=True,
        )
        return registered
    # **Oldest first, so the newest wins.** Two runnable versions of one
    # plugin share a stack id (`astar+<plugin id>`), so only one of them
    # can be the thing that id resolves to — and the registry is a dict,
    # so the last write decides which.
    #
    # `bundles.list()` is newest-first, which made the *oldest* version
    # win: importing a fix while the version it fixed was still enabled
    # left the platform quietly running the old code. Reversed here, with
    # the reason, because the correct order is not the natural one.
    for record in reversed(stored):
        if not record.usable or record.validation_status is not ValidationStatus.LOADED:
            continue
        try:
            entries = build_plugin_entries(
                record.manifest,
                directory=bundle_directory(install_root, record),
                description=record.description,
                # The checksum of the archive, truncated the same way the
                # built-in source checksum is. This is what makes a fixed
                # and re-imported bundle a different candidate.
                controller_version=record.checksum[:12],
            )
        except Exception:  # noqa: BLE001 - one bad bundle must not hide the rest
            continue
        # One stack per global planner: the controller is the same object
        # either way, and which planner drew the path it follows is a
        # property of the pairing rather than of the plugin.
        registered.extend(register_external(entry) for entry in entries)
    return registered


def _require_admin(user: User) -> None:
    """Only administrators may put code on this server.

    One call, in one place, so that replacing it with a finer grant means
    changing it rather than finding it — see
    `docs/plugin_import_security.md` §5.
    """
    if not user.is_admin:
        raise PluginNotAllowed(
            "importing an algorithm runs your code on this server, so it is limited to "
            "administrators. Ask a deployment administrator to import it for you"
        )


def _require_owner_or_admin(record: PluginBundleRecord, user: User) -> None:
    if user.is_admin or record.uploaded_by_user_id == user.id:
        return
    raise PluginNotAllowed("this algorithm was imported by somebody else")


__all__ = [
    "HostCompatibility",
    "PluginBundleService",
    "PluginLimits",
    "host_compatibility",
    "storage_key",
]
