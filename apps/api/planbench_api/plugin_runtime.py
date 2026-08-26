"""Unpacking an imported bundle and finding out whether it behaves.

This is the module where the uploader's code finally runs, and every
line before it exists so that this moment can be refused. Extraction
happens only after preflight says the plugin may run here, and the run
itself happens in a child process — crash and interpreter isolation, not
a sandbox (`docs/plugin_import_security.md` §2).

**Behaviour is a separate verdict from structure.** P1's answer is "this
archive is a bundle"; this module's is "the object inside it does what
its manifest says". The two are different claims and they are recorded
in different words — `structural` and `loaded` — because a platform that
collapsed them would be saying it had run something it had only read.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from planbench_api.model_registry import RegistryError, RobotProfile, ValidationStatus
from planbench_api.model_storage import ModelStorage
from planbench_api.plugin_registry import PluginBundleRecord

#: Written beside an unpacked bundle so a second install can tell that
#: the directory already holds *these* bytes. Without it, "already
#: extracted" would mean "a directory of that name exists", which is the
#: same sentence for a half-written extraction.
INSTALLED_MARKER = ".planbench-installed"

#: The deadline the conformance run holds a plugin to.
#:
#: Deliberately generous, and deliberately **not** a control period. G4
#: asks whether a controller answers within the cycle time of a
#: particular robot on a particular deployment; this asks whether it
#: answers at all and answers the same way twice. Borrowing a control
#: period here would report a slow machine as a broken plugin.
CONFORMANCE_DEADLINE_S = 5.0

#: Channel payloads this module knows how to synthesise for a check.
#: Anything outside it is a capability whose shape only a running episode
#: has, and the honest answer there is to skip the run and say which
#: capability stopped it — not to feed the plugin a plausible-looking
#: fake and report the result as evidence.
LIDAR_2D = "lidar_2d"
HUMAN_STATES = "human_state_estimates"
ROBOT_STATE = "planbench://channel/robot-state@1"
LEGACY_OBSERVATION = "planbench://channel/legacy-observation@1"
SYNTHESISABLE = frozenset({LIDAR_2D, HUMAN_STATES, ROBOT_STATE, LEGACY_OBSERVATION})


class BundleInstallError(RegistryError):
    """The archive could not be turned into a directory to run from."""


@dataclass(frozen=True)
class ConformanceOutcome:
    """What running the plugin concluded, and what to record."""

    status: ValidationStatus
    message: str


def install_root(root: Path, record: PluginBundleRecord) -> Path:
    """Where this bundle's code lives once unpacked.

    **Keyed by the archive's checksum**, which is what makes two uploads
    of one plugin two directories. Keying on the manifest's version put
    changed code on top of the code it replaced the moment an author
    forgot to bump it — the old files still on disk, the new row pointing
    at them, and nothing anywhere saying which was running.

    The checksum is also what a stored candidate id hashes on, so this
    path can still be resolved from a result recorded months ago.
    """
    return root / record.plugin_id / (record.checksum[:16] or "unknown")


def install_bundle(record: PluginBundleRecord, storage: ModelStorage, root: Path) -> Path:
    """Unpack the archive, once, into a directory the lane can import from.

    Idempotent by checksum: a directory already holding these bytes is
    left alone, and a directory holding *different* bytes under the same
    identity is replaced rather than merged — a half-old, half-new
    package directory would import as neither.
    """
    target = install_root(root, record)
    marker = target / INSTALLED_MARKER
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == record.checksum:
        return target

    data = storage.open(record.storage_key)
    actual = hashlib.sha256(data).hexdigest()
    if actual != record.checksum:
        raise BundleInstallError(
            f"the stored archive for {record.plugin_id!r} no longer matches its checksum "
            "recorded at import; refusing to unpack bytes nobody vouched for"
        )

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            _extract_safely(archive, target)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    marker.write_text(record.checksum, encoding="utf-8")
    return target


def _extract_safely(archive: zipfile.ZipFile, target: Path) -> None:
    """Write every member, refusing any that would land outside `target`.

    P1 already rejected unsafe names when it read the table of contents.
    This is the *second* check, and it is the one that can actually
    prevent an escape: the first read names, this one resolves paths.
    Two moments, and only a check at the writing moment knows where the
    write would go.
    """
    root = target.resolve()
    for info in archive.infolist():
        destination = (target / info.filename).resolve()
        if not destination.is_relative_to(root):
            raise BundleInstallError(
                f"member {info.filename!r} would be written outside the bundle directory"
            )
        if info.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, destination.open("wb") as handle:
            shutil.copyfileobj(source, handle)


def run_conformance(
    record: PluginBundleRecord,
    profile: RobotProfile,
    directory: Path,
) -> ConformanceOutcome:
    """Load the plugin in a subprocess and put it through the SDK suite.

    Returns rather than raises, always. A harness that could not start —
    no interpreter, no worker, a capability this module cannot
    synthesise — is not a verdict about the plugin, so it leaves the
    bundle `structural` with a sentence saying what stopped the run. Only
    the plugin's own misbehaviour earns `failed`.
    """
    from planbench_plugin_sdk import check_local_plugin, parse_manifest

    manifest = parse_manifest(record.manifest, source=record.original_filename)
    granted = tuple(manifest.requirements.all_of) + tuple(manifest.requirements.optional)
    unknown = sorted(set(granted) - SYNTHESISABLE)
    if unknown:
        return ConformanceOutcome(
            ValidationStatus.STRUCTURAL,
            f"not run: this check cannot synthesise {unknown} outside an episode, so the "
            "plugin's behaviour is unverified rather than verified-good",
        )

    from planbench_simulator.host.compatibility import HostSupport, resolve_compatibility
    from planbench_simulator.host.fairness_policy import FairnessPolicy
    from planbench_simulator.host.provider_graph import ProviderGraph
    from planbench_simulator.host.providers import builtin_providers, builtin_registry
    from planbench_simulator.host.runtimes.subprocess_lane import SubprocessRuntime

    graph = ProviderGraph(builtin_providers(include_oracle=True), builtin_registry())
    report = resolve_compatibility(
        manifest,
        available_capabilities=frozenset(),
        graph=graph,
        policy=FairnessPolicy.research(),
        support=HostSupport(),
    )
    if not report.runnable:
        return ConformanceOutcome(
            ValidationStatus.STRUCTURAL,
            f"not run: {report.explain()}",
        )

    runtime = SubprocessRuntime(search_paths=(str(directory),))
    started: list[Any] = []

    def factory() -> Any:
        plugin = runtime.load(manifest, report, {}, control_period_s=CONFORMANCE_DEADLINE_S)
        started.append(plugin)
        return plugin

    try:
        step_request, reset_request = _requests_for(manifest, profile)
        conformance = check_local_plugin(manifest, factory, step_request, reset_request)
        findings = list(conformance.findings)
        findings += _refusals_are_not_answers(started, step_request)
    except Exception as error:  # noqa: BLE001 - the harness, not the plugin
        return ConformanceOutcome(
            ValidationStatus.STRUCTURAL,
            f"not run: the conformance harness could not start ({error!r})",
        )
    finally:
        for plugin in started:
            close = getattr(plugin, "close", None)
            if callable(close):
                close()

    rendered = "; ".join(str(finding) for finding in findings)
    # Warnings do not fail a plugin — the SDK is explicit that they are
    # things an author may have decided on purpose, while errors are
    # things the host would go on to act on wrongly. Reported either way:
    # a warning nobody is told about is a warning that does not exist.
    if any(finding.severity == "error" for finding in findings):
        return ConformanceOutcome(ValidationStatus.FAILED, rendered)
    if findings:
        return ConformanceOutcome(
            ValidationStatus.LOADED,
            f"loaded in a subprocess and passed, with warnings: {rendered}",
        )
    return ConformanceOutcome(
        ValidationStatus.LOADED,
        "loaded in a subprocess and passed the conformance suite: it presents its role's "
        "methods, two fresh instances answered identically, its optional channels really "
        "are optional, it read only what it declared, and it did not write into the request",
    )


def _refusals_are_not_answers(started: list[Any], step_request: Any) -> list[Any]:
    """Catch the failure mode this lane hides from the SDK suite.

    In the subprocess lane a plugin that crashes does not raise: the
    handle converts the dead worker into a **safe stop**, which is a
    perfectly well-formed `LocalPlanResult` carrying zero velocity. So a
    plugin that dies on every tick answers `(0.0, 0.0)` twice and passes
    the determinism check by being reliably broken.

    The suite cannot see this — it is looking at commands, and a safe
    stop is a command. The distinguishing fact is `failure_reason`, so
    this reads it.
    """
    from planbench_plugin_sdk import Finding

    if not started:
        return []
    result = started[0].step(step_request.model_copy(deep=True))
    reason = getattr(result, "failure_reason", "")
    if not reason:
        return []
    return [
        Finding(
            check="runtime",
            severity="error",
            message=(
                f"the worker answered with a safe stop rather than a command: {reason}. "
                "In this lane a crash arrives as zero velocity, so this would otherwise "
                "read as a plugin that is merely very cautious"
            ),
        )
    ]


def _requests_for(manifest: Any, profile: RobotProfile) -> tuple[Any, Any]:
    """A plausible first tick, built from the robot the bundle names.

    Synthesised rather than replayed: this asks whether the object obeys
    its contract, which does not need a map. Everything it hands over is
    shaped like the real channel and none of it is presented as a
    measurement.
    """
    from planbench_plugin_sdk import ChannelEnvelope, LocalResetRequest, LocalStepRequest

    from planbench_schemas.episode import Observation
    from planbench_schemas.robot import Pose2D, RobotState

    pose = Pose2D(x=0.0, y=0.0, theta=0.0)
    state = RobotState(pose=pose, linear_velocity=0.0, angular_velocity=0.0)
    ranges = tuple(float(profile.lidar_range) for _ in range(profile.lidar_beams))
    observation = Observation(
        time=0.0,
        pose=pose,
        linear_velocity=0.0,
        angular_velocity=0.0,
        goal_distance=5.0,
        goal_bearing=0.0,
        lidar_ranges=ranges,
    )
    payloads = {
        LIDAR_2D: ranges,
        HUMAN_STATES: (),
        ROBOT_STATE: state,
        LEGACY_OBSERVATION: observation,
    }
    granted = tuple(manifest.requirements.all_of) + tuple(manifest.requirements.optional)
    channels = tuple(
        ChannelEnvelope(
            capability=capability,
            cadence="per_tick",
            produced_at=0.0,
            provenance="oracle" if capability == HUMAN_STATES else "deployment",
            revision=0,
            payload=payloads[capability],
        )
        for capability in granted
    )
    step_request = LocalStepRequest(state={"robot_state": state}, channels=channels)
    reset_request = LocalResetRequest(
        global_path=((0.0, 0.0), (5.0, 0.0)),
        robot={
            "robot_config": {
                "radius": profile.radius,
                "max_linear_velocity": profile.max_linear_velocity,
                "max_angular_velocity": profile.max_angular_velocity,
                "max_linear_acceleration": profile.max_linear_acceleration or 1.0,
                "max_angular_acceleration": profile.max_angular_acceleration or 1.0,
            }
        },
        episode_seed=0,
    )
    return step_request, reset_request


__all__ = [
    "CONFORMANCE_DEADLINE_S",
    "INSTALLED_MARKER",
    "BundleInstallError",
    "ConformanceOutcome",
    "install_bundle",
    "install_root",
    "run_conformance",
]
