"""Services for the decision layer (Phase 6.2).

Thin on purpose. Every rule these enforce already lives in the contract
layer — ``TaskProfile`` validates HĐ-2, ``candidate_from_stack`` computes
HĐ-1.3's hash, ``validate_experiment_scope`` and ``validate_control_rate``
refuse an unrunnable set, and ``run_comparison`` owns the chain. A service
that re-implemented any of them would create a second definition free to
drift from the first, which §16 puts one owner on each schema to prevent.

What the services *do* own is the API's side of the story: turning a
request body into validated domain objects, and turning a finished run
into a stored row.

**A run is stored whether or not it produced a card.** Fewer than two
candidates through the gates means no ΔU and no Decision Card, and the
gate table is then the whole deliverable. ``POST /decisions`` returns 201
for that case exactly as for a ranked one — a 4xx would tell the caller
their request was wrong when the platform in fact answered the question
they asked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from planbench_api.decisions import (
    ArtifactKind,
    CandidateRepository,
    DecisionRunRepository,
    StoredCandidate,
    StoredDecisionRun,
    StoredTaskProfile,
    TaskProfileRepository,
    new_run_id,
)
from planbench_api.errors import DomainValidationError
from planbench_api.repositories import now_iso
from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS, candidate_from_stack
from planbench_benchmark.selection import DEFAULT_SCOPE, run_comparison
from planbench_schemas.contracts import CONTRACTS_VERSION
from planbench_schemas.task_profile import TaskProfile


class TaskProfileService:
    def __init__(self, repository: TaskProfileRepository) -> None:
        self._repository = repository

    def create(self, payload: dict[str, Any], *, owner_user_id: str | None) -> StoredTaskProfile:
        """Validate against HĐ-2, then store.

        Validation happens through ``TaskProfile`` rather than here: it
        is the single definition of the contract, and it is what refuses
        a heading requirement the platform cannot evaluate, a periodic
        obstacle that shifts by less than one period, and a RAM budget
        that does not add up. Re-checking any of that at this layer would
        be a second opinion nobody asked for.
        """
        try:
            profile = TaskProfile.model_validate(payload)
        except Exception as error:  # pydantic ValidationError and friends
            raise DomainValidationError(f"task profile is not valid under HĐ-2: {error}") from error
        return self._repository.create(
            profile.model_dump(mode="json"), owner_user_id=owner_user_id
        )

    def get(self, profile_id: str) -> StoredTaskProfile:
        return self._repository.get(profile_id)

    def list(self) -> list[StoredTaskProfile]:
        return self._repository.list()

    def load(self, profile_id: str) -> TaskProfile:
        """The stored profile as the contract object the engine needs."""
        return TaskProfile.model_validate(self._repository.get(profile_id).profile)


class CandidateService:
    def __init__(self, repository: CandidateRepository) -> None:
        self._repository = repository

    def register(
        self,
        *,
        stack: str,
        local_config: str,
        registered_by: str | None,
        tuning: dict[str, Any] | None = None,
    ) -> StoredCandidate:
        """Register a candidate and hand back its content hash.

        The id is **computed, never supplied**. HĐ-1.3 defines it as a
        hash over the stack, its parameters and its code version, so
        letting a caller name their own candidate would allow two
        different configurations to share an identity — and every trace,
        pairing and ΔU in the system keys on that identity.

        ``tuning`` carries HĐ-1.6's declaration with its evidence log.
        Absent is allowed and is not the same as zero: the objectives
        layer charges an undeclared candidate for the silence, which is
        the honest handling.
        """
        if local_config not in LOCAL_CONTROLLER_CONFIGS:
            raise DomainValidationError(
                f"unknown local controller {local_config!r}; "
                f"known: {sorted(LOCAL_CONTROLLER_CONFIGS)}"
            )
        try:
            candidate = candidate_from_stack(
                stack, params=dict(LOCAL_CONTROLLER_CONFIGS[local_config])
            )
        except Exception as error:
            raise DomainValidationError(f"cannot register {stack!r}: {error}") from error
        return self._repository.create(
            candidate.model_dump(mode="json"),
            candidate_id=candidate.candidate_id,
            # A computed property, so it is absent from ``model_dump``.
            # Two candidates differing only in parameters share it, which
            # is exactly why identity is the hash and never this string.
            stack_label=candidate.stack_label,
            registered_by=registered_by,
            tuning=tuning,
        )

    def get(self, candidate_id: str) -> StoredCandidate:
        return self._repository.get(candidate_id)

    def list(self) -> list[StoredCandidate]:
        return self._repository.list()


class DecisionRunService:
    """Runs a selection through the shared chain and stores the result."""

    def __init__(
        self,
        runs: DecisionRunRepository,
        profiles: TaskProfileService,
        *,
        repo_root: Path,
        trace_root: Path,
        run_root: Path,
    ) -> None:
        self._runs = runs
        self._profiles = profiles
        self._repo_root = repo_root
        self._trace_root = trace_root
        self._run_root = run_root

    def run(
        self,
        *,
        task_profile_id: str,
        candidate_specs: list[tuple[str, str]],
        scope: str = DEFAULT_SCOPE,
        episodes: int | None = None,
        created_by: str | None = None,
        reuse_traces: bool = True,
    ) -> StoredDecisionRun:
        """Execute the selection, then store whatever it produced.

        The profile is written back to a file for the engine because
        every path in it (map, map_yaml) is relative to the repository
        root, and the chain loads maps from disk. Storing the profile in
        the database did not change where its map lives.
        """
        stored_profile = self._profiles.get(task_profile_id)
        profile_path = self._materialise(stored_profile)

        report = run_comparison(
            profile_path=profile_path,
            candidate_specs=candidate_specs,
            scope=scope,
            episodes=episodes,
            trace_root=self._trace_root,
            run_root=self._run_root,
            reuse=reuse_traces,
            quiet=True,
            map_base_dir=self._repo_root,
        )
        return self._store(report, stored_profile, scope=scope, created_by=created_by)

    def get(self, run_id: str) -> StoredDecisionRun:
        return self._runs.get(run_id)

    def list(
        self, *, task_profile_id: str | None = None, ranked: bool | None = None
    ) -> list[StoredDecisionRun]:
        return self._runs.list(task_profile_id=task_profile_id, ranked=ranked)

    # -- internals -----------------------------------------------------

    def _materialise(self, stored: StoredTaskProfile) -> Path:
        import yaml

        directory = self._run_root / "profiles"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{stored.id}.yaml"
        path.write_text(yaml.safe_dump(stored.profile, sort_keys=False), encoding="utf-8")
        return path

    def _store(
        self,
        report: dict[str, Any],
        profile: StoredTaskProfile,
        *,
        scope: str,
        created_by: str | None,
    ) -> StoredDecisionRun:
        card = report.get("decision_card")
        # HĐ-13: the manifest is what somebody else rebuilds the card
        # from, so storing a card without one keeps a claim that cannot
        # be reproduced. It travels in the report for exactly this.
        manifest = report.get("manifest")
        kind: ArtifactKind = "decision_card" if card is not None else "comparison"
        recommended = card["recommended"]["candidate_id"] if card is not None else None
        return self._runs.create(
            StoredDecisionRun(
                id=new_run_id(),
                task_profile_id=profile.id,
                artifact_kind=kind,
                experiment_scope=scope,
                contracts_version=CONTRACTS_VERSION,
                created_at=now_iso(),
                created_by=created_by,
                report=report,
                card=card,
                manifest=manifest,
                recommended_candidate_id=recommended,
                status=card["status"] if card is not None else None,
                # The run's own directory and a fingerprint of the traces
                # it was computed from — not the root every run shares.
                # ``run_uri`` pointing at the parent said nothing a reader
                # could act on, and ``run_checksum`` was always null, which
                # left D15's reference decorative: a URI cannot say the
                # files behind it are still the ones this result came from.
                run_uri=report.get("run_uri") or f"file://{self._run_root}",
                run_checksum=report.get("run_checksum"),
            )
        )
