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

from planbench_api.accounts import Capability, User, roles_label
from planbench_api.errors import NotFoundError
from planbench_api.model_registry import (
    RegistryError,
    ValidationStatus,
    sanitise_filename,
)
from planbench_api.model_storage import ModelStorage
from planbench_api.plugin_registry import (
    OperationalStatus,
    PluginBundleRecord,
    PluginEvent,
    PluginNotAllowed,
    PluginPublication,
    inspect_bundle,
)
from planbench_api.plugin_runtime import install_bundle, run_conformance
from planbench_api.repositories import new_id, now_iso

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
        publications: Any = None,
        events: Any = None,
        governance: bool = False,
        strict_duties: bool = True,
    ) -> None:
        self._bundles = bundles
        self._profiles = profiles
        self._storage = storage
        self._limits = limits
        self._install_root = install_root
        self._publications = publications
        self._events = events
        self._governance = governance
        self._strict_duties = strict_duties

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
                revision=self._bundles.next_revision(manifest.id),
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

        Gated on ``algorithm.validate`` rather than on the read one:
        this starts the uploader's code, and who may do that is the
        question §5 of the threat model answers. Named separately from
        ``algorithm.import`` even though the same package holds both, so
        the audit row says which act it was — importing puts code on the
        machine, re-checking runs code already there, and a trail that
        called them the same thing would lose that.
        """
        _require_capability(user, Capability.ALGORITHM_VALIDATE)
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
        if saved.usable and not self._governance:
            # Only while the catalogue still resolves by "the newest
            # runnable row wins". Under governance the current
            # publication decides, and disabling the revision this one
            # replaces would pull a *published* algorithm out of every
            # picker because a *different* upload passed a check — the
            # machine deciding what runs, which is what publishing exists
            # to end.
            self._retire_previous(saved)
        self.sync_catalogue()
        return saved

    def _retire_previous(self, current: PluginBundleRecord) -> None:
        """Disable the uploads this one replaces.

        Only one upload of a plugin can be what `astar+<plugin id>`
        resolves to, so leaving the others enabled shows several rows as
        active while one of them is what actually runs — a screen that
        disagrees with the platform.

        Disabled rather than deleted, and that is the whole point of
        having a status: every result recorded against an earlier upload
        still resolves to the bundle that produced it. What changes is
        only what may be picked for new work.
        """
        for other in self._bundles.others_of(current.plugin_id, current.id):
            if other.status is OperationalStatus.ACTIVE:
                self._bundles.save(other.model_copy(update={"status": OperationalStatus.DISABLED}))

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
            changes = {**changes, "status": OperationalStatus(changes["status"])}
        if "robot_profile_id" in changes:
            self._profiles.get(changes["robot_profile_id"])
        saved = self._bundles.save(record.model_copy(update=changes))
        # Disabling one is how a plugin is retired, so the catalogue has
        # to hear about it here as well as at import.
        self.sync_catalogue()
        return saved

    def sync_catalogue(self) -> list[str]:
        """Make the runtime catalogue match what may be offered."""
        return sync_catalogue(
            self._bundles,
            self._install_root,
            self._storage,
            publications=self._publications if self._governance else None,
        )

    # -- governance ----------------------------------------------------

    def publish(self, bundle_id: str, user: User, reason: str = "") -> PluginBundleRecord:
        """Put this revision in front of everyone.

        Refused unless the bundle actually loaded. ``structural`` means
        the archive is *shaped* like a bundle — its table of contents was
        read, which executes nothing — and publishing on that would put
        code in front of every engineer that no conformance suite has
        run.

        Under strict duties the reviewer who uploaded a revision cannot
        be the one who publishes it. Not because uploading is suspect,
        but because a signature its own signer could have produced alone
        is not evidence of a second pair of eyes, and a second pair of
        eyes is the whole point of the step.
        """
        record = self._bundles.get(bundle_id)
        _require_capability(user, Capability.ALGORITHM_PUBLISH)
        if record.status is not OperationalStatus.ACTIVE:
            raise PluginNotAllowed(
                f"{record.label} is {record.status.value}; release the hold before publishing it"
            )
        if record.validation_status is not ValidationStatus.LOADED:
            raise PluginNotAllowed(
                f"{record.label} has not been loaded and checked (it is "
                f"{record.validation_status.value}). Run the conformance suite first: "
                "publishing puts this code in front of everyone who picks an algorithm"
            )
        if (
            self._strict_duties
            and record.uploaded_by_user_id
            and record.uploaded_by_user_id == user.id
        ):
            raise PluginNotAllowed(
                "this deployment separates duties: the reviewer who imported a revision is "
                "not the one who publishes it. Ask another reviewer to publish it"
            )
        self._publications.publish(
            plugin_id=record.plugin_id,
            bundle_id=record.id,
            revision=record.revision,
            published_by_user_id=user.id,
        )
        self._record_event(record, user, "published", Capability.ALGORITHM_PUBLISH, reason)
        self.sync_catalogue()
        return record

    def unpublish(self, bundle_id: str, user: User, reason: str = "") -> PluginBundleRecord:
        """Pull the current revision back. Reversible by publishing again."""
        record = self._bundles.get(bundle_id)
        _require_capability(user, Capability.ALGORITHM_PUBLISH)
        current = self._publications.current(record.plugin_id)
        if current is None or current.bundle_id != record.id:
            raise PluginNotAllowed(f"{record.label} is not the published revision")
        self._publications.unpublish(
            plugin_id=record.plugin_id, unpublished_by_user_id=user.id, reason=reason
        )
        self._record_event(record, user, "unpublished", Capability.ALGORITHM_PUBLISH, reason)
        self.sync_catalogue()
        return record

    def hold(self, bundle_id: str, user: User, reason: str = "") -> PluginBundleRecord:
        """Take it out of every picker while somebody looks at it."""
        return self._set_status(
            bundle_id, user, OperationalStatus.HELD, "held", Capability.ALGORITHM_PUBLISH, reason
        )

    def release_hold(self, bundle_id: str, user: User, reason: str = "") -> PluginBundleRecord:
        record = self._bundles.get(bundle_id)
        if record.status is OperationalStatus.DISABLED:
            raise PluginNotAllowed(
                f"{record.label} was disabled, which is final. Upload the fixed revision "
                "instead, so that what changed in between is visible"
            )
        return self._set_status(
            bundle_id,
            user,
            OperationalStatus.ACTIVE,
            "hold_released",
            Capability.ALGORITHM_PUBLISH,
            reason,
        )

    def disable(
        self,
        bundle_id: str,
        user: User,
        reason: str,
        *,
        capability: Capability = Capability.ALGORITHM_DISABLE,
    ) -> PluginBundleRecord:
        """Terminal: out of every picker, and it does not come back.

        ``capability`` is passed in rather than assumed, because two
        different jobs reach this code — a reviewer retiring an algorithm
        on governance grounds, and an administrator pulling a kill switch
        during an incident. Same effect, different job, and only the
        caller knows which one it is doing. Guessing here would put the
        wrong one in the audit row.
        """
        if not reason.strip():
            raise PluginNotAllowed(
                "disabling an algorithm is final and needs a reason: it is what somebody "
                "reads when a stored approval says the algorithm behind it was turned off"
            )
        record = self._set_status(
            bundle_id, user, OperationalStatus.DISABLED, "disabled", capability, reason
        )
        if self._publications is not None:
            self._publications.unpublish(
                plugin_id=record.plugin_id, unpublished_by_user_id=user.id, reason=reason
            )
            self.sync_catalogue()
        return record

    # -- resolving a stack name to code --------------------------------
    #
    # Three questions, deliberately narrow, because they are what
    # :mod:`planbench_api.run_identity` needs and nothing more. Passing
    # the whole service into that module would let it reach for anything
    # and make it untestable without a database.

    def current(self, plugin_id: str) -> PluginBundleRecord | None:
        """The bundle a published stack name resolves to."""
        publication = self.publication(plugin_id)
        if publication is None:
            return None
        try:
            return self._bundles.get(publication.bundle_id)
        except NotFoundError:
            return None

    def newest(self, plugin_id: str) -> PluginBundleRecord | None:
        """What the pre-publishing rule offered: the newest runnable one.

        Only reached with governance off. It exists so this phase can pin
        identity on a deployment that has not turned publishing on —
        before publishing there is no such thing as "not published", and
        refusing there would refuse runs that are ordinary today.
        """
        candidates = [
            record
            for record in self._bundles.list()
            if record.plugin_id == plugin_id
            and record.usable
            and record.validation_status is ValidationStatus.LOADED
        ]
        return max(candidates, key=lambda record: record.revision, default=None)

    def publication(self, plugin_id: str) -> PluginPublication | None:
        """The revision currently published for this plugin, if any."""
        if self._publications is None:
            return None
        return self._publications.current(plugin_id)

    def published_bundle_ids(self) -> set[str]:
        """Every bundle that is somebody's current publication.

        One query for a whole list view, rather than one publication
        lookup per row. The set is also all the answer a list needs:
        membership means "this is what an engineer would get", absence
        plus a sibling in the set means "a newer revision took over", and
        absence with no sibling means nobody has published this plugin at
        all. The list page draws those three differently, and none of
        them requires knowing *which* revision won.
        """
        if self._publications is None:
            return set()
        return self._publications.current_bundle_ids()

    def publications_for_bundle(self, bundle_id: str) -> list[PluginPublication]:
        """Every publication row naming this bundle.

        Asked by the reliance check, which needs "was this revision ever
        published, and is that still standing?" — a question about one
        bundle rather than about a plugin's timeline.
        """
        if self._publications is None:
            return []
        return self._publications.for_bundle(bundle_id)

    def publication_history(self, plugin_id: str) -> list[PluginPublication]:
        return [] if self._publications is None else self._publications.history(plugin_id)

    def events(self, bundle_id: str) -> list[PluginEvent]:
        return [] if self._events is None else self._events.list_for_bundle(bundle_id)

    def _set_status(
        self,
        bundle_id: str,
        user: User,
        status: OperationalStatus,
        action: str,
        capability: Capability,
        reason: str,
    ) -> PluginBundleRecord:
        record = self._bundles.get(bundle_id)
        _require_capability(user, capability)
        changes: dict[str, Any] = {"status": status}
        if status is OperationalStatus.DISABLED:
            changes |= {
                "disabled_at": now_iso(),
                "disabled_by_user_id": user.id,
                "disabled_reason": reason,
            }
        saved = self._bundles.save(record.model_copy(update=changes))
        self._record_event(saved, user, action, capability, reason)
        self.sync_catalogue()
        return saved

    def _record_event(
        self,
        record: PluginBundleRecord,
        user: User,
        action: str,
        capability: Capability,
        reason: str = "",
    ) -> None:
        if self._events is None:
            return
        self._events.record(
            PluginEvent(
                bundle_id=record.id,
                revision=record.revision,
                actor_user_id=user.id,
                actor_roles=roles_label(user.roles),
                authorized_capability=capability.value,
                action=action,
                reason=reason,
            )
        )

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


def sync_catalogue(
    bundles: Any,
    install_root: Path,
    storage: ModelStorage | None = None,
    publications: Any = None,
) -> list[str]:
    """Make the runtime catalogue match the stored bundles. Returns ids.

    **Two resolvers, and which one runs is a deployment setting.** With
    ``publications`` given — governance on — a bundle is offered only
    while it is its plugin's current publication, so what an engineer can
    pick is exactly what a reviewer put there. Without it, the older rule
    applies unchanged: every runnable bundle is offered and the newest
    wins the stack id.

    The pair exists so this phase can land without moving the ground
    under a deployment that is already running. It is a debt with a due
    date: the old branch goes when the flag is turned on for good, and
    keeping both is only safe because they are ten lines apart in one
    function rather than two code paths that could drift.

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
    offerable: set[str] | None = None
    if publications is not None:
        try:
            offerable = publications.current_bundle_ids()
        except Exception:  # noqa: BLE001 - same reasoning as the read above
            logger.warning(
                "the publication table could not be read; no imported algorithm will be "
                "offered until it can. If this deployment has just taken an update, run "
                "'alembic upgrade head'.",
                exc_info=True,
            )
            return registered
    for record in reversed(stored):
        if not record.usable or record.validation_status is not ValidationStatus.LOADED:
            continue
        if offerable is not None and record.id not in offerable:
            # Imported, checked, and nobody has vouched for it yet — or
            # a newer revision took its place. Visible in the algorithms
            # tab with that said plainly; not offerable.
            continue
        directory = _unpacked_directory(record, install_root, storage)
        if directory is None:
            continue
        try:
            entries = build_plugin_entries(
                record.manifest,
                directory=directory,
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


def _unpacked_directory(
    record: PluginBundleRecord,
    install_root: Path,
    storage: ModelStorage | None,
) -> Path | None:
    """Where this bundle's code is, unpacking it again if it is not there.

    **A bundle can be in the database with nothing on disk**, and until
    this existed the platform offered it anyway: the manifest lives in
    the row, so building a stack from it succeeded, and the failure
    waited until a sweep was running and every episode died with a
    Python traceback about a module nobody had heard of.

    The way that happens is an upgrade. `install_root` keys the
    directory on the archive's checksum; it used to key on the declared
    version, so every bundle imported before that change sits under a
    path this build no longer looks at. The row is fine, the archive is
    fine, and the two have simply stopped agreeing about where the code
    goes.

    So: unpack it again from the archive that is already stored, which
    `install_bundle` verifies against the checksum before it writes
    anything. When that cannot be done — no storage to read from, or an
    archive that no longer hashes as recorded — the bundle is **left out
    of the catalogue** rather than offered, and the log says which and
    why. Not offering it is the point: an algorithm missing from the
    picker sends somebody to look, while one that fails per-episode
    sends them to a traceback.
    """
    from planbench_api.plugin_runtime import INSTALLED_MARKER, install_bundle
    from planbench_api.plugin_runtime import install_root as bundle_directory

    directory = bundle_directory(install_root, record)
    if (directory / INSTALLED_MARKER).is_file():
        return directory
    if storage is None:
        logger.warning(
            "imported algorithm %r is not unpacked and cannot be restored here; "
            "it will not be offered. Import it again to restore it.",
            record.plugin_id,
        )
        return None
    try:
        return install_bundle(record, storage, install_root)
    except Exception:  # noqa: BLE001 - one bundle, not the catalogue
        logger.warning(
            "imported algorithm %r could not be unpacked from its stored archive; "
            "it will not be offered. Import it again to restore it.",
            record.plugin_id,
            exc_info=True,
        )
        return None


def _require_capability(user: User, capability: Capability) -> None:
    """The finer grant `plugin_import_security.md` §5 promised.

    It replaces `user.is_admin`, and the swap is not cosmetic: that flag
    conflated running the server with vouching for code, so the account
    that rotates an API key was also the only one that could put a
    planner on the machine. Reviewers vouch; administrators operate;
    somebody doing both jobs holds both roles and each act is audited
    under the capability that allowed it.
    """
    if user.can(capability):
        return
    raise PluginNotAllowed(
        f"{capability.value!r} is part of the reviewer role. Importing an algorithm runs "
        "your code on this server and publishing one puts it in front of everybody, so "
        "both are limited to reviewers — ask one to do it for you"
    )


def _require_admin(user: User) -> None:
    """Kept as the import gate's name; the rule behind it is a capability."""
    _require_capability(user, Capability.ALGORITHM_IMPORT)


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
