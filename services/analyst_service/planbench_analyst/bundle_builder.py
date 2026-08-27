"""Freezing an analyst, and the three things freezing has to refuse.

A bundle is the claim "this exact system was graded". Everything here
exists so that claim cannot be made about something else:

**A dirty tree cannot be frozen.** ``agent_code_digest`` says
``git:<sha>``, and a working copy with edits in it is not that commit.
Freezing anyway would produce a bundle whose digest names code nobody
ran — and the edits are usually the interesting part.

**A placeholder digest is not a digest.** The image is named by
``sha256:<64 hex>``, supplied by whoever built it. This module will not
invent one, will not accept ``latest``, and will not fall back to "no
container" — a bundle that cannot say what it ran inside is a bundle
whose dependencies moved between calibration and the gate.

**Calibration is three runs and takes the worst.** Not the best, not the
mean. A best-of-three is a system that got lucky once; a mean hides the
run that failed structurally. And there is **no retry** — a retry is
another draw from the same distribution, reported as though the first
draw had not happened.

**The model has to be the same model each time.** The identity is read
before the first run and compared after each: a provider that re-points
an alias mid-calibration produces a report about two systems, and
nothing in the numbers would show it.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from planbench_analyst.identity import flatten_config, source_manifest_hash
from planbench_analyst.prompts import prompt_checksum
from planbench_explanation.budget import PLATFORM_BUDGET_CAP, AnalysisBudget
from planbench_explanation.bundle import AnalystBundle
from planbench_explanation.protocol import ANALYST_RUNNER_PROTOCOL_VERSION

__all__ = [
    "CalibrationRun",
    "FreezeRefusal",
    "ModelIdentity",
    "calibrate",
    "freeze_bundle",
    "git_sha",
    "working_tree_is_clean",
]

CONTAINER_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

#: How many times an official calibration runs the bundle. Three, and
#: the statistical metrics take the **minimum** across them.
CALIBRATION_RUNS = 3


class FreezeRefusal(RuntimeError):
    """A bundle that would claim to be something it is not."""


def working_tree_is_clean(root: Path) -> bool:
    """Whether ``git status --porcelain`` is empty.

    Untracked files count as dirty. A new module sitting beside the
    frozen code is code the digest does not cover and the container may
    still copy in.
    """
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "status", "--porcelain"],  # noqa: S607 - git resolved from PATH
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise FreezeRefusal(
            "git could not report the working tree state; a freeze that cannot see "
            "the tree cannot promise the digest covers it"
        )
    return not result.stdout.strip()


def git_sha(root: Path) -> str:
    """The full commit, never a short one.

    Seven hex characters identify a commit *in a repository at a
    moment*; the point of recording which build produced a result is
    that somebody can still resolve it later.
    """
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "rev-parse", "HEAD"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise FreezeRefusal("git could not resolve HEAD to a full commit sha")
    return sha


@dataclass(frozen=True)
class ModelIdentity:
    """What the provider says it is, read before and after each run."""

    model_id: str
    model_revision: str

    def matches(self, other: ModelIdentity) -> bool:
        return (self.model_id, self.model_revision) == (other.model_id, other.model_revision)


def freeze_bundle(
    *,
    root: Path,
    bundle_id: str,
    container_digest: str,
    identity: ModelIdentity,
    generation_parameters: dict[str, object],
    rag_index_version: str,
    retrieval_config_checksum: str,
    tool_catalog_version: str,
    requested_budget: AnalysisBudget = PLATFORM_BUDGET_CAP,
    created_at: str,
    allow_dirty: bool = False,
) -> AnalystBundle:
    """Freeze the analyst as it stands, or refuse to.

    ``allow_dirty`` exists for a developer rehearsing the freeze on a
    tree they are still editing. It is **not** a way to freeze for a
    gate: the resulting bundle names a commit that does not describe the
    code, and the docstring says so because the flag's name does not.
    """
    if not allow_dirty and not working_tree_is_clean(root):
        raise FreezeRefusal(
            "the working tree has changes; a bundle frozen here would carry a commit "
            "digest that does not describe the code it ran. Commit, or pass "
            "allow_dirty=True for a rehearsal that must not be gated."
        )
    if not CONTAINER_DIGEST.fullmatch(container_digest):
        raise FreezeRefusal(
            f"{container_digest!r} is not an image digest; write sha256:<64 hex>. A tag "
            "moves, and a bundle whose image moved is a bundle that cannot be re-run."
        )

    flattened = flatten_config(generation_parameters)
    return AnalystBundle(
        bundle_id=bundle_id,
        agent_code_digest=f"git:{git_sha(root)}",
        container_digest=container_digest,
        model_id=identity.model_id,
        model_revision=identity.model_revision,
        prompt_checksum=prompt_checksum(),
        rag_index_version=rag_index_version,
        retrieval_config_checksum=retrieval_config_checksum,
        tool_catalog_version=tool_catalog_version,
        # Flattened to JSON Pointer paths so two configurations that
        # differ only in nesting cannot share an identity. See
        # ``planbench_analyst.identity``.
        generation_parameters={key: _scalar(value) for key, value in flattened.items()},
        runner_protocol_version=ANALYST_RUNNER_PROTOCOL_VERSION,
        requested_budget=requested_budget,
        created_at=created_at,
    )


def _scalar(value: object) -> float | int | str | bool:
    if isinstance(value, float | int | str | bool):
        return value
    return str(value)


@dataclass
class CalibrationRun:
    """One official calibration: three runs, the worst of them, no retry."""

    bundle: AnalystBundle
    source_hash: str
    identity: ModelIdentity
    scores: list[dict[str, float]] = field(default_factory=list)
    structural_violations: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    identity_drift: bool = False

    @property
    def passed(self) -> bool:
        """Conservative on every axis, and every axis is a veto.

        A run that errored, a structural violation anywhere, or a model
        that changed under us — any one of them ends it. The statistical
        metrics are then read at their **minimum**, which is the run a
        deployment might get rather than the run worth quoting.
        """
        return (
            len(self.scores) == CALIBRATION_RUNS
            and not self.errors
            and not self.identity_drift
            and all(count == 0 for count in self.structural_violations)
        )

    @property
    def worst(self) -> dict[str, float]:
        if not self.scores:
            return {}
        return {
            metric: min(score.get(metric, 0.0) for score in self.scores)
            for metric in self.scores[0]
        }

    def report(self) -> dict[str, object]:
        return {
            "bundle_id": self.bundle.bundle_id,
            "bundle_identity_checksum": self.bundle.identity_checksum,
            "requested_budget_checksum": self.bundle.requested_budget.checksum,
            "source_manifest_hash": self.source_hash,
            "model": f"{self.identity.model_id}@{self.identity.model_revision}",
            "runs": len(self.scores),
            "passed": self.passed,
            "worst": self.worst,
            "structural_violations": list(self.structural_violations),
            "errors": list(self.errors),
            "identity_drift": self.identity_drift,
        }


ScoreOnce = Callable[[], tuple[dict[str, float], int, ModelIdentity]]


def calibrate(
    bundle: AnalystBundle,
    score_once: ScoreOnce,
    *,
    root: Path,
    runs: int = CALIBRATION_RUNS,
    globs: Sequence[str] | None = None,
) -> CalibrationRun:
    """Run the frozen bundle ``runs`` times and take the worst of it.

    ``score_once`` returns one run's metrics, its structural violation
    count, and the identity the provider reported for that run. It is
    called exactly ``runs`` times: a failure is recorded, **never
    retried**, because a retry is another draw reported as though the
    first had not happened.
    """
    source_hash = source_manifest_hash(root, globs=globs or ())  # type: ignore[arg-type]
    baseline: ModelIdentity | None = None
    record = CalibrationRun(
        bundle=bundle,
        source_hash=source_hash,
        identity=ModelIdentity(bundle.model_id, bundle.model_revision),
    )

    for index in range(runs):
        try:
            metrics, violations, identity = score_once()
        except Exception as failed:  # noqa: BLE001 - the boundary of somebody else's code
            record.errors.append(f"run {index + 1}: {failed}")
            continue
        if baseline is None:
            baseline = identity
            record.identity = identity
        elif not baseline.matches(identity):
            record.identity_drift = True
        record.scores.append(dict(metrics))
        record.structural_violations.append(violations)
    return record
