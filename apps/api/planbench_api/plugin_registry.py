"""Imported algorithm bundles, as the platform knows them.

The sibling of :mod:`planbench_api.model_registry`, and deliberately not
a reuse of it. A model is weights for a controller the platform already
has; a bundle is a controller the platform has never seen. They share
storage, statuses and ownership, and they share nothing about what the
uploaded bytes *are* — so the record is its own type rather than a
`ModelRecord` with half its fields meaning something else.

**Nothing here imports, extracts or executes a bundle.**
:func:`inspect_bundle` reads the archive's table of contents and parses
one JSON member. That is metadata parsing: no member is written to disk
and no plugin code runs. Extraction is P2's job and happens only after
preflight has said the plugin may run at all — see
`docs/reference/plugin_import_security.md` §1 for the ordering and why it is the
ordering.
"""

from __future__ import annotations

import io
import json
import zipfile
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from planbench_api.model_registry import (
    RegistryError,
    ValidationStatus,
)

#: The directory a bundle carries its manifest in, and the file's name.
#: Duplicated from ``planbench_simulator.host.discovery`` rather than
#: imported: this module refuses to depend on the simulator, and a
#: constant that disagreed would show up as "no manifest found" on a
#: perfectly good bundle. There is a test pinning the two together.
BUNDLE_DIRNAME = ".planbench-plugin"
MANIFEST_FILENAME = "plugin.json"

ZIP_MAGIC = b"PK\x03\x04"

#: The lane an imported bundle is measured in. Not configurable: the
#: host never falls back between lanes, so a plugin declaring the
#: in-process lane and being run in a subprocess would be measured in a
#: lane it did not declare. See `docs/reference/plugin_import_security.md` §7.
REQUIRED_LANE = "subprocess"

#: Roles the subprocess lane can actually drive. ``SubprocessPlugin``
#: implements ``reset`` and ``step`` and has no ``plan``, so ``global``
#: is refused for a reason about capability rather than about policy.
#: Widening this is this constant plus the lane work it names (§8).
SUPPORTED_ROLES = frozenset({"local", "monolithic"})


class BundleInspection(BaseModel):
    """What reading an archive's table of contents concluded.

    ``problems`` empty means the archive is a bundle this deployment
    could register. It does **not** mean the plugin runs: that needs
    preflight, and preflight needs a deployment.
    """

    model_config = ConfigDict(frozen=True)

    problems: tuple[str, ...] = ()
    #: The manifest as it was written, when it parsed. Stored verbatim so
    #: the checksum identifies what the author actually uploaded rather
    #: than a re-serialisation of it.
    manifest: dict[str, Any] | None = None
    #: The single top-level directory in the archive — the Python package
    #: name the entry point must resolve against.
    package_dir: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems


def inspect_bundle(
    data: bytes,
    *,
    max_members: int,
    max_extracted_bytes: int,
    max_manifest_bytes: int,
) -> BundleInspection:
    """Structural check of an uploaded bundle. Executes nothing.

    Every refusal is a sentence written for the person uploading. They
    are returned rather than raised, and all of them are collected, so an
    author fixing three things learns about three things.
    """
    if not data.startswith(ZIP_MAGIC):
        return BundleInspection(
            problems=(
                "this file is not a zip archive. An algorithm bundle is a .zip of the "
                "directory holding your planner and its .planbench-plugin/plugin.json",
            )
        )

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return _inspect_open(
                archive,
                max_members=max_members,
                max_extracted_bytes=max_extracted_bytes,
                max_manifest_bytes=max_manifest_bytes,
            )
    except zipfile.BadZipFile:
        return BundleInspection(problems=("the zip archive is corrupt and cannot be read",))


def _inspect_open(
    archive: zipfile.ZipFile,
    *,
    max_members: int,
    max_extracted_bytes: int,
    max_manifest_bytes: int,
) -> BundleInspection:
    problems: list[str] = []

    infos = archive.infolist()
    if len(infos) > max_members:
        problems.append(
            f"the archive holds {len(infos)} members, more than the {max_members} allowed"
        )

    broken = archive.testzip()
    if broken is not None:
        problems.append(f"the archive contains a corrupt member: {broken}")

    unsafe = sorted(name for name in archive.namelist() if not _member_is_safe(name))
    if unsafe:
        problems.append(
            "the archive contains unsafe member paths (absolute, escaping, or "
            f"backslash-separated): {unsafe[:3]}"
        )

    # The compressed size says nothing about what extraction writes, and
    # extraction is the step that fills a disk.
    extracted = sum(info.file_size for info in infos)
    if extracted > max_extracted_bytes:
        problems.append(
            f"the archive expands to {extracted} bytes, more than the {max_extracted_bytes} allowed"
        )

    if problems:
        # Reading further means trusting names this function has just
        # said it does not trust.
        return BundleInspection(problems=tuple(problems))

    manifest_members = [
        name
        for name in archive.namelist()
        if Path(name).name == MANIFEST_FILENAME and BUNDLE_DIRNAME in Path(name).parts
    ]
    if not manifest_members:
        return BundleInspection(
            problems=(
                f"no {BUNDLE_DIRNAME}/{MANIFEST_FILENAME} in the archive. The bundle "
                "must be a directory containing your planner and that manifest, zipped "
                "as a directory rather than as its contents",
            )
        )
    if len(manifest_members) > 1:
        return BundleInspection(
            problems=(
                f"the archive holds {len(manifest_members)} manifests "
                f"({sorted(manifest_members)[:3]}); a bundle declares exactly one plugin",
            )
        )

    member = manifest_members[0]
    package_dir = _package_dir(member)
    if not package_dir:
        return BundleInspection(
            problems=(
                f"{member!r} sits at the top of the archive. The manifest must live "
                "inside the bundle directory, because that directory's name is the "
                "Python package your entry point imports",
            )
        )

    info = archive.getinfo(member)
    if info.file_size > max_manifest_bytes:
        return BundleInspection(
            problems=(
                f"{MANIFEST_FILENAME} is {info.file_size} bytes, more than the "
                f"{max_manifest_bytes} allowed",
            )
        )

    try:
        raw = json.loads(archive.read(member).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return BundleInspection(problems=(f"{member} is not readable JSON: {error}",))
    if not isinstance(raw, dict):
        return BundleInspection(problems=(f"{member} must be a JSON object",))

    manifest_problems = _check_manifest(raw, package_dir)
    return BundleInspection(
        problems=tuple(manifest_problems),
        manifest=raw if not manifest_problems else None,
        package_dir=package_dir,
    )


def _check_manifest(raw: dict[str, Any], package_dir: str) -> list[str]:
    """Parse the manifest with the SDK, then apply this door's rules.

    The SDK's refusals come first and are reported verbatim: they are the
    same refusals a plugin author meets from the CLI, and rewording them
    here would give one person two vocabularies for one mistake.
    """
    from planbench_plugin_sdk import PluginSDKError, parse_manifest

    try:
        manifest = parse_manifest(raw, source=f"{package_dir}/{BUNDLE_DIRNAME}/{MANIFEST_FILENAME}")
    except PluginSDKError as error:
        return [str(error)]
    except ValueError as error:  # pydantic refusals arrive as ValueError
        return [f"the manifest is not valid: {error}"]

    problems: list[str] = []
    if manifest.role not in SUPPORTED_ROLES:
        problems.append(
            f"role {manifest.role!r} cannot be imported yet: the subprocess lane drives "
            "reset/step and has no plan(), so a global planner has nothing to run in. "
            f"Supported today: {sorted(SUPPORTED_ROLES)}"
        )
    if manifest.runtime.production_lane != REQUIRED_LANE:
        problems.append(
            f"production_lane is {manifest.runtime.production_lane!r}; an imported bundle "
            f"is measured in the {REQUIRED_LANE!r} lane and the host never falls back "
            "between lanes, so a plugin declaring another one would be measured "
            "somewhere it did not declare"
        )
    profile = manifest.runtime.profiles.get(REQUIRED_LANE)
    if profile is None:
        problems.append(f"the manifest declares no {REQUIRED_LANE!r} runtime profile")
    elif not profile.entry_point:
        problems.append(
            f"the {REQUIRED_LANE!r} profile declares no entry_point; without it there is "
            "nothing to load"
        )
    elif profile.entry_point.partition(":")[0].split(".")[0] != package_dir:
        problems.append(
            f"entry_point {profile.entry_point!r} does not start with the bundle "
            f"directory {package_dir!r}. The directory's name is the Python package "
            "that gets imported, so the two have to agree"
        )
    return problems


def _member_is_safe(name: str) -> bool:
    """Reject anything that could write outside the extraction root.

    Checked here **and** again when members are written (P2). Two
    moments, and only the second one can actually escape — but a bundle
    carrying such a name is broken or hostile either way, and saying so
    at upload time is a better error than saying so at install time.
    """
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = Path(name).parts
    return ".." not in parts and not any(part.startswith("/") for part in parts)


def _package_dir(manifest_member: str) -> str:
    """The bundle's top-level directory, or '' when there is not one."""
    parts = Path(manifest_member).parts
    if len(parts) < 3 or parts[-1] != MANIFEST_FILENAME or parts[-2] != BUNDLE_DIRNAME:
        return ""
    return parts[0]


class OperationalStatus(StrEnum):
    """Whether a bundle may be picked, and if not, whether that is final.

    A third value on the column that already answers the question,
    rather than a second column beside it. ``held`` is a reviewer
    pulling a revision back while they look at something; ``disabled``
    is terminal, and terminal on purpose — "turn it back on" and "upload
    the fixed one" should not both exist, because only the second is
    honest about what changed in between.

    Wire-compatible with the two values ``ModelStatus`` had, so rows
    written before this load unchanged.
    """

    ACTIVE = "active"
    HELD = "held"
    DISABLED = "disabled"


class PluginPublication(BaseModel):
    """One act of putting a revision in front of everyone.

    ``superseded_at`` and ``unpublished_at`` are separate because they
    are separate facts. A newer revision replacing this one says nothing
    about whether this one was any good; a reviewer withdrawing it says
    exactly that. Collapsing both into "no longer current" would leave a
    stored approval unable to tell which happened — and that is the
    difference between a recommendation that is merely old and one that
    was taken back.
    """

    model_config = ConfigDict(frozen=True)

    id: str = ""
    plugin_id: str
    bundle_id: str
    revision: int
    published_by_user_id: str | None = None
    published_at: str = ""
    superseded_at: str | None = None
    unpublished_at: str | None = None
    unpublished_by_user_id: str | None = None
    reason: str = ""

    @property
    def is_current(self) -> bool:
        return self.superseded_at is None and self.unpublished_at is None

    @property
    def was_withdrawn(self) -> bool:
        """Pulled back by a person, as opposed to replaced by a revision."""
        return self.unpublished_at is not None


class PluginEvent(BaseModel):
    """Append-only: what happened to a bundle, under which capability."""

    model_config = ConfigDict(frozen=True)

    sequence: int = 0
    bundle_id: str
    revision: int = 0
    actor_user_id: str | None = None
    actor_roles: str = ""
    authorized_capability: str = ""
    action: str
    reason: str = ""
    created_at: str = ""


class PluginBundleRecord(BaseModel):
    """One imported algorithm, as stored.

    ``manifest`` is kept verbatim rather than reconstructed from parsed
    fields: ``manifest_checksum`` identifies what the author uploaded,
    and a re-serialisation would identify what this version of the SDK
    thinks they uploaded.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: str = "1"
    description: str = ""
    plugin_id: str = ""
    #: What the manifest calls itself. A label the author maintains, not
    #: an identity: two bundles may declare the same one, and the earlier
    #: rule that they could not made an author hand-edit a number before
    #: every upload — the kind of number a person forgets, failing
    #: silently when they do.
    plugin_version: str = ""
    #: Which upload of this plugin this is, counted by the platform.
    #:
    #: **Assigned, not declared.** The author changes code; the platform
    #: says which turn of that loop it is looking at. Nothing hashes on
    #: it — candidate identity follows the archive's checksum — so it is
    #: free to be the readable thing the manifest version was being asked
    #: to be and kept failing at.
    revision: int = 1
    role: str = "local"
    entry_point: str = ""
    manifest: dict[str, Any] = Field(default_factory=dict)
    manifest_checksum: str = ""
    package_dir: str = ""
    storage_key: str = ""
    original_filename: str = ""
    file_size: int = 0
    checksum: str = ""
    uploaded_by_user_id: str = ""
    robot_profile_id: str = ""
    status: OperationalStatus = OperationalStatus.ACTIVE
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_message: str = ""
    disabled_at: str | None = None
    disabled_by_user_id: str | None = None
    disabled_reason: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} v{self.version}"

    @property
    def usable(self) -> bool:
        """Somebody enabled it and its file turned out to be a bundle.

        Necessary and not sufficient: whether it *runs* is a question
        about this deployment's providers, recomputed on every read
        rather than stored here.
        """
        return self.status is OperationalStatus.ACTIVE and self.validation_status in {
            ValidationStatus.STRUCTURAL,
            ValidationStatus.LOADED,
        }

    @property
    def requirements(self) -> tuple[str, ...]:
        """Capabilities the manifest declares as required."""
        block = self.manifest.get("requirements") or {}
        required = [*block.get("all_of", []), *block.get("any_of", [])]
        return tuple(str(item) for item in required)


class PluginBundleSummary(BaseModel):
    """The public view. No storage key, no owner id.

    Same rule as ``ModelSummary``: everybody sees this, so it carries
    nothing only the owner should know.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: str
    description: str
    plugin_id: str
    plugin_version: str
    revision: int
    role: str
    requirements: tuple[str, ...]
    robot_profile_id: str
    original_filename: str
    file_size: int
    checksum: str
    status: OperationalStatus
    validation_status: ValidationStatus
    validation_message: str
    owned: bool
    created_at: str
    updated_at: str

    @classmethod
    def of(
        cls, record: PluginBundleRecord, viewer_id: str, inspect: bool = False
    ) -> PluginBundleSummary:
        """The list view. ``inspect`` decides how much of it is filled in.

        One place, so that "what may an engineer see about an imported
        algorithm?" has one answer rather than one per endpoint. The
        checksum is the field worth naming: it identifies the exact bytes
        that ran, which is precisely what a reviewer needs and what a
        picker does not.
        """
        return cls(
            id=record.id,
            name=record.name,
            version=record.version,
            description=record.description,
            plugin_id=record.plugin_id,
            plugin_version=record.plugin_version,
            revision=record.revision,
            role=record.role,
            requirements=record.requirements,
            robot_profile_id=record.robot_profile_id,
            original_filename=record.original_filename,
            file_size=record.file_size,
            checksum=record.checksum if inspect else "",
            status=record.status,
            validation_status=record.validation_status,
            validation_message=record.validation_message,
            owned=bool(viewer_id) and record.uploaded_by_user_id == viewer_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class PluginNotAllowed(RegistryError):
    """Authenticated, but not permitted to do this to a bundle.

    Subclasses ``RegistryError`` so an existing handler catches it, and
    is registered ahead of it so being the wrong person is a 403 rather
    than a 422 — the same split ``ModelNotAllowed`` makes.
    """


__all__ = [
    "BUNDLE_DIRNAME",
    "MANIFEST_FILENAME",
    "REQUIRED_LANE",
    "SUPPORTED_ROLES",
    "BundleInspection",
    "PluginBundleRecord",
    "PluginBundleSummary",
    "PluginNotAllowed",
    "inspect_bundle",
]
