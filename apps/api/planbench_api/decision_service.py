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

import base64
import json
from pathlib import Path
from typing import Any

from planbench_api.decisions import (
    ArtifactKind,
    CandidateRepository,
    DecisionRunRepository,
    ReviewEvent,
    StoredCandidate,
    StoredDecisionRun,
    StoredTaskProfile,
    TaskProfileRepository,
    new_run_id,
)
from planbench_api.errors import (
    DomainValidationError,
    InvalidStateError,
    NotFoundError,
    field_errors,
)
from planbench_api.map_files import materialise_map
from planbench_api.repositories import StoredMap, now_iso
from planbench_api.repository_ports import MapRepositoryPort
from planbench_api.worker import Job, JobQueue
from planbench_benchmark.candidates import LOCAL_CONTROLLER_CONFIGS, candidate_from_stack
from planbench_benchmark.selection import DEFAULT_SCOPE, run_comparison
from planbench_schemas.contracts import CONTRACTS_VERSION
from planbench_schemas.task_profile import TaskProfile


class TaskProfileService:
    def __init__(
        self,
        repository: TaskProfileRepository,
        *,
        maps: MapRepositoryPort,
        map_root: Path,
        runs: DecisionRunRepository | None = None,
    ) -> None:
        self._repository = repository
        self._maps = maps
        self._map_root = map_root
        #: Needed only by `delete`, which has to know whether anything was
        #: measured on this deployment before it destroys it. Optional so
        #: the callers that only file and read profiles keep working
        #: unchanged; `delete` treats a missing store as "no runs", which
        #: is true for every one of them.
        self._runs = runs

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
            # The blob message stays — it is what somebody pasting YAML
            # reads — and the per-field addresses travel beside it, which
            # is what a form with thirty inputs needs to turn a refusal
            # into a red outline on the right row.
            raise DomainValidationError(
                f"task profile is not valid under HĐ-2: {error}", field_errors(error)
            ) from error
        return self._repository.create(profile.model_dump(mode="json"), owner_user_id=owner_user_id)

    def get(self, profile_id: str) -> StoredTaskProfile:
        return self._repository.get(profile_id)

    def list(self) -> list[StoredTaskProfile]:
        return self._repository.list()

    def delete(self, profile_id: str, *, delete_runs: bool = False) -> int:
        """Remove a deployment; return how many runs went with it.

        **Two cases, and the difference is whether anything was
        measured.** A deployment nobody ever ran is a draft: deleting it
        destroys a description and nothing else, so it goes straight
        away. A deployment with runs is the subject of every one of them
        — a run is a statement *about* a deployment, which is why the
        foreign key is ``ON DELETE RESTRICT`` rather than a cascade — so
        deleting it destroys measurements, and possibly a configuration
        somebody approved.

        That second case is refused unless the caller says
        ``delete_runs``. The refusal is not a wall: it carries the counts
        so the dialog can ask *"delete seven runs, two of them
        approved?"* rather than *"are you sure?"*. Counting them again in
        the browser would be a second answer, free to disagree with the
        one the server refused on.

        The service owns this rather than the repository because the rule
        spans two stores, and only something that can see both can state
        it once.
        """
        self._repository.get(profile_id)  # 404 before anything else
        runs = self._runs.list(task_profile_id=profile_id) if self._runs is not None else []

        # An approved run is not more data. Somebody signed a
        # configuration off, and `decision_run_reviews` cascades, so
        # deleting it erases both the decision and the record of who made
        # it — the two things HĐ-14 exists to keep apart and keep. No
        # confirmation reaches past this: a dialog that let one click
        # destroy an audit trail is not a safeguard, it is a speed bump.
        approved_ids = [run.id for run in runs if run.config_state == "approved"]
        if approved_ids:
            raise InvalidStateError(
                f"deployment {profile_id!r} has {len(approved_ids)} approved run(s) "
                f"({', '.join(sorted(approved_ids))}). An approved run is a configuration "
                "somebody signed off, together with the record of who signed it (HĐ-14). "
                "Withdraw the approval first (POST /decisions/{id}/config-approval/withdraw) — it "
                "stays in the journal beside the withdrawal.",
                [{"runs": len(runs), "approved": len(approved_ids), "approved_ids": approved_ids}],
            )

        if runs and not delete_runs:
            approved = sum(1 for run in runs if run.config_state == "approved")
            reviewed = sum(1 for run in runs if run.review_state == "reviewed")
            raise InvalidStateError(
                f"deployment {profile_id!r} has {len(runs)} stored run(s), so deleting it would "
                "delete measurements. A run is a statement about a deployment: without its "
                "subject it is unreadable, not merely smaller. Confirm to delete both.",
                [
                    {
                        "runs": len(runs),
                        "ranked": sum(1 for run in runs if run.recommended_candidate_id),
                        "reviewed": reviewed,
                        "approved": approved,
                    }
                ],
            )
        removed = (
            self._runs.delete_for_profile(profile_id)
            if runs and self._runs is not None
            else 0
        )
        self._repository.delete(profile_id)
        return removed

    def load(self, profile_id: str) -> TaskProfile:
        """The stored profile as the contract object the engine needs."""
        return TaskProfile.model_validate(self._repository.get(profile_id).profile)

    def derive(
        self,
        *,
        base_task_profile_id: str,
        new_id: str,
        map_id: str,
        missions: list[dict[str, Any]] | None = None,
        owner_user_id: str | None = None,
    ) -> StoredTaskProfile:
        """A deployment identical to another except for its map.

        **Why this is a new deployment and never an edit.** A map is the
        world, and ``episode_context_id`` hashes ``(task_profile_id,
        mission_id, environment_variant, seed)`` with HĐ-3.1 freezing
        that payload — the map is not in it. Repointing an existing
        profile at different walls would produce contexts hashing
        identically to the old world's, and ``--reuse-traces`` would then
        serve episodes recorded somewhere that no longer exists. Nothing
        warns; the ids match. Same trap ``sensor_noise`` sprang, and the
        same answer: new world, new id.

        **Why the map is written to disk.** The map editor stores grids
        in the database; the decision layer reads its map from the two
        paths a profile names (HĐ-2). Materialising the pair is the
        crossing, and it costs no contract change — what lands on disk is
        an ordinary map_server map. The filename carries the map's
        *version*, so editing a map afterwards writes a new file and
        leaves this deployment pointing at the walls it was measured on.

        **Why the missions are checked here.** A goal inside a shelf
        gives 0% success for every candidate, and the comparison then
        reports a tie between stacks on a question none of them was
        asked — every column a plausible 0.00, nothing in the numbers
        wrong. ``validate_missions_on_map`` already catches the five ways
        a profile and a map disagree; calling it now is the difference
        between a refusal and two hours of machine time spent measuring
        the map instead of the candidates.
        """
        from planbench_benchmark.task_map import MapProfileMismatch, load_task_map

        if new_id == base_task_profile_id:
            raise DomainValidationError(
                f"a derived deployment needs its own id, not {new_id!r} again. Changing the "
                "map changes the world, and episode_context_id does not hash the map "
                "(HĐ-3.1) — reusing the id would make episodes from two different worlds "
                "collide on one hash, and --reuse-traces would serve the wrong ones"
            )

        base = self._repository.get(base_task_profile_id)
        stored_map = self._maps.get(map_id)

        # Written before the missions are checked, because the check
        # reads the map back off disk — that round trip is the point, not
        # an accident of ordering: it is what proves the engine will see
        # the same walls the validator did.
        #
        # A refusal below therefore leaves the pair behind, and that is
        # not litter to sweep up. The filename is (map id, version), so a
        # failed attempt and a later successful one write identical
        # bytes to the same path — and deleting it would be deleting the
        # map some other deployment already points at.
        image_rel, yaml_rel = self._materialise_map(stored_map)

        payload: dict[str, Any] = json.loads(json.dumps(base.profile))
        payload["id"] = new_id
        environment = payload.setdefault("environment", {})
        environment["map"] = image_rel
        environment["map_yaml"] = yaml_rel
        if missions is not None:
            if not missions:
                raise DomainValidationError(
                    "a deployment with no missions measures nothing; give at least one "
                    "start/goal pair that fits the map"
                )
            payload["missions"] = missions

        try:
            profile = TaskProfile.model_validate(payload)
        except Exception as error:
            raise DomainValidationError(
                f"derived task profile is not valid under HĐ-2: {error}", field_errors(error)
            ) from error

        try:
            load_task_map(profile, base_dir=self._map_root, validate=True)
        except MapProfileMismatch as error:
            raise DomainValidationError(str(error)) from error
        except Exception as error:
            raise DomainValidationError(
                f"the derived deployment's map could not be read back: {error}"
            ) from error

        return self._repository.create(profile.model_dump(mode="json"), owner_user_id=owner_user_id)

    def _materialise_map(self, stored: StoredMap) -> tuple[str, str]:
        """The stored grid as the two paths a profile names.

        A method only so this class need not carry the map root into
        every call site; the writing itself is
        :func:`planbench_api.map_files.materialise_map`, shared with the
        endpoint a form uses to file a deployment from scratch. Two
        copies of "where does a drawn map land on disk" would put two
        deployments on two different files for one map.
        """
        return materialise_map(stored, self._map_root)


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

    def submit(
        self,
        *,
        jobs: JobQueue,
        task_profile_id: str,
        candidate_specs: list[tuple[str, str]],
        scope: str = DEFAULT_SCOPE,
        episodes: int | None = None,
        created_by: str | None = None,
        reuse_traces: bool = True,
    ) -> Job:
        """Queue the selection instead of running it inside the request.

        **The queue this goes into holds one job at a time, and that is a
        contract requirement rather than a resource choice.** HĐ-7.4
        forbids two evaluation runs on one machine at once: both pin the
        same cores, so each becomes the other's background load and G4
        measures a machine that does not exist. A second slot would let
        the API produce exactly the corruption the pinning exists to
        prevent.

        Nothing about the run changes — same chain, same storage, same
        refusals. What changes is who waits: a 300-episode warehouse
        sweep is hours of simulation, and an HTTP request that holds a
        browser open for hours is not a design, it is an omission.

        The synchronous path stays for small runs. A six-episode fixture
        finishes before a progress bar would finish appearing, and making
        every caller poll for that would be ceremony.
        """
        stored_profile = self._profiles.get(task_profile_id)
        profile_path = self._materialise(stored_profile)
        job_id = new_run_id()

        def work(job: Job) -> None:
            def progress(done: int, total: int, what: str) -> None:
                job.progress = done
                job.total = total
                job.message = what

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
                progress=progress,
            )
            stored = self._store(report, stored_profile, scope=scope, created_by=created_by)
            # The finished run's id, so a client watching the job knows
            # where to look without searching the list for something that
            # appeared recently — "recent" is not an identity.
            job.message = stored.id

        # `total=0` rather than the episode count the caller asked for.
        # A sweep runs one pair per (candidate, episode) — 30 episodes
        # across two candidates is 60 units of work — and seeding the
        # counter with 30 made the job read "0/30" and then jump to
        # "60/60". A denominator that changes under the reader is worse
        # than one that arrives a second late, so the sweep reports both
        # numbers itself when it has them.
        return jobs.submit(job_id, "decision_run", work, total=0)

    def get(self, run_id: str) -> StoredDecisionRun:
        return self._runs.get(run_id)

    def list(
        self, *, task_profile_id: str | None = None, ranked: bool | None = None
    ) -> list[StoredDecisionRun]:
        return self._runs.list(task_profile_id=task_profile_id, ranked=ranked)

    # -- the two human acts (HĐ-14, phase 6.3) -------------------------

    def review(
        self, run_id: str, *, actor_user_id: str | None, username: str, comment: str = ""
    ) -> StoredDecisionRun:
        return self._runs.review(
            run_id, actor_user_id=actor_user_id, username=username, comment=comment
        )

    def decide_config(
        self,
        run_id: str,
        *,
        approve: bool,
        actor_user_id: str | None,
        username: str,
        comment: str = "",
    ) -> StoredDecisionRun:
        return self._runs.decide_config(
            run_id,
            approve=approve,
            actor_user_id=actor_user_id,
            username=username,
            comment=comment,
        )

    def withdraw_config(
        self, run_id: str, *, actor_user_id: str | None, username: str, comment: str = ""
    ) -> StoredDecisionRun:
        return self._runs.withdraw_config(
            run_id, actor_user_id=actor_user_id, username=username, comment=comment
        )

    def events(self, run_id: str) -> list[ReviewEvent]:
        return self._runs.events(run_id)

    def trace(self, run_id: str, candidate_id: str, episode_context_id: str) -> dict[str, Any]:
        """One episode, as something a canvas can draw.

        **The trace is the only record of what happened**, and until now
        nothing could read one back out. ``compare.py`` writes one Parquet
        file per (candidate, episode) — that file is the sole input the
        Metrics Engine has (HĐ-5) — and every number on a Decision Card
        is derived from it. A platform that computes a gate verdict from
        evidence nobody can look at is asking to be believed.

        Three things travel together because none of them means anything
        alone: the poses, the map they were driven on, and the metadata
        that says which episode this is. A trajectory without its map is
        a squiggle; a map without the episode ids is a picture of
        somewhere.

        Refuses a trace that does not belong to this run rather than
        serving whatever the path spells. The ids are content hashes, so
        a mismatch is not a typo — it is a request for a different
        experiment's evidence under this run's name.
        """
        import pyarrow.parquet as pq

        from planbench_benchmark.task_map import load_task_map
        from planbench_simulator.trace import trace_path

        run = self._runs.get(run_id)
        report = run.report or {}
        candidates = {
            str(entry.get("candidate_id"))
            for entry in report.get("candidates", [])  # type: ignore[union-attr]
        }
        if candidate_id not in candidates:
            raise NotFoundError("candidate in this run", candidate_id)
        episodes = set(report.get("sample", {}).get("episode_context_ids", []))  # type: ignore[union-attr]
        if episodes and episode_context_id not in episodes:
            raise NotFoundError("episode in this run", episode_context_id)

        path = trace_path(candidate_id, episode_context_id, root=self._trace_root)
        if not path.is_file():
            raise NotFoundError("trace file", f"{candidate_id}/{episode_context_id}")

        table = pq.read_table(path)
        columns = {name: table.column(name).to_pylist() for name in table.column_names}
        raw = (table.schema.metadata or {}).get(b"planbench_trace")
        metadata = json.loads(raw) if raw else {}

        profile = self._profiles.load(run.task_profile_id)
        map_data = load_task_map(profile, base_dir=self._repo_root, validate=False)

        return {
            "candidate_id": candidate_id,
            "episode_context_id": episode_context_id,
            "task_profile_id": run.task_profile_id,
            "metadata": metadata,
            "map": _packed_map(map_data),
            "robot_radius_m": profile.robot.radius,
            # Explicit fields rather than `list(pose)`: iterating a
            # pydantic model yields (name, value) pairs, which serialised
            # the start pose as [["x", 2.0], ["y", 8.0], ["theta", 0.0]]
            # — readable by nothing and drawable by less.
            "missions": [
                {
                    "id": mission.id,
                    "start": {"x": mission.start.x, "y": mission.start.y},
                    "goal": {"x": mission.goal.x, "y": mission.goal.y},
                }
                for mission in profile.missions
            ],
            # Column-oriented, matching the file. Rewriting 546 rows into
            # 546 objects would triple the payload to say the same thing.
            "t": columns.get("t", []),
            "x": columns.get("x", []),
            "y": columns.get("y", []),
            "theta": columns.get("theta", []),
            "clearance_m": columns.get("clearance_m", []),
            "planner_latency_ms": columns.get("planner_latency_ms", []),
            # Sparse: only the steps that carry one. HĐ-5 events are what
            # turn a path into an outcome, and dropping them would leave a
            # collision indistinguishable from an arrival.
            "events": [
                {"index": index, "event": value}
                for index, value in enumerate(columns.get("event", []))
                if value
            ],
        }

    def approved_config(self, run_id: str) -> str:
        """The deployable configuration, as YAML — approved runs only.

        HĐ-14: *"only a Decision Card in the APPROVED state can export
        `approved_config.yaml`"*, and the same clause says the system is
        **sim-only** — there is no technical path from here to a robot.
        "Deploying" is emitting this file, and the file says so about
        itself, in it, where somebody reading it later will see it.

        Everything needed to argue with the choice travels with it: the
        deployment it was chosen for, the evidence behind the margin, the
        manifest reference, and the trace checksum. A config naming a
        winner and nothing else invites being applied somewhere it was
        never measured — the recommendation is scoped to *one* deployment
        (HĐ-1.4), and dropping that scope is how it stops being true.
        """
        import yaml

        run = self._runs.get(run_id)
        if run.config_state != "approved":
            raise InvalidStateError(
                f"decision run {run_id} is {run.config_state}, not approved. "
                "Only an approved recommendation exports a configuration (HĐ-14)"
            )
        card = run.card or {}
        recommended = card.get("recommended", {})
        evidence = card.get("evidence", {})
        payload = {
            "artifact": "approved_config",
            "sim_only_notice": (
                "Đây là một FILE CẤU HÌNH, không phải một lệnh triển khai. Hệ thống ở chế độ "
                "sim-only: không tồn tại đường dẫn kỹ thuật nào từ đây tới robot thật (HĐ-14). "
                "Mọi con số dưới đây được đo trong mô phỏng, trên đúng deployment ghi ở "
                "task_profile_id — và chỉ có nghĩa ở đó."
            ),
            "task_profile_id": run.task_profile_id,
            "experiment_scope": run.experiment_scope,
            "candidate": {
                "candidate_id": recommended.get("candidate_id"),
                "stack": recommended.get("stack"),
                "params_ref": recommended.get("params_ref"),
            },
            "decision": {
                "status": run.status,
                "decision_utility": card.get("decision_utility"),
                "delta_u_vs_second": evidence.get("delta_u_vs_second"),
                "ci95": evidence.get("ci95"),
                "n_episodes": evidence.get("n_episodes"),
                "pareto_label": card.get("pareto_label"),
            },
            "provenance": {
                "decision_run_id": run.id,
                "contracts_version": run.contracts_version,
                "manifest_ref": card.get("manifest_ref"),
                "run_uri": run.run_uri,
                "run_checksum": run.run_checksum,
                "created_at": run.created_at,
            },
            "approval": {
                "approved_by": run.config_decided_by,
                "approved_at": run.config_decided_at,
                "reviewed_by": run.reviewed_by,
                "reviewed_at": run.reviewed_at,
            },
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

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


def _packed_map(map_data: Any) -> dict[str, Any]:
    """The occupancy grid as base64 bits, not 153,600 JSON numbers.

    The reference hall is 480x320. As a JSON array of zeroes and ones
    that is roughly 300 kB of text to say one bit per cell; packed eight
    to a byte it is 19 kB, and the browser unpacks it in a loop it was
    going to write anyway to walk the grid.

    Row-major with row 0 at the map origin, matching ``MapData`` — the
    canvas flips it, because screen y grows downward and world y does
    not, and getting that wrong draws a mirror of the run.
    """
    cells = map_data.cells
    packed = bytearray((len(cells) + 7) // 8)
    for index, value in enumerate(cells):
        if value:
            packed[index >> 3] |= 1 << (index & 7)
    return {
        "name": map_data.name,
        "width": map_data.width,
        "height": map_data.height,
        "resolution": map_data.resolution,
        "origin": {"x": map_data.origin.x, "y": map_data.origin.y},
        "occupied_bits": base64.b64encode(bytes(packed)).decode("ascii"),
    }


class TestBenchStaging:
    """What staging one test-bench episode produced.

    Three ids rather than one because each answers a different question
    the caller has: which simulation to run and stream, which conditions
    were actually assembled, and which stored map the canvas should draw.
    """

    __slots__ = ("simulation_id", "scenario_id", "map_id", "episode_context_id", "scenario")

    def __init__(
        self,
        *,
        simulation_id: str,
        scenario_id: str,
        map_id: str,
        episode_context_id: str,
        scenario: dict[str, Any],
    ) -> None:
        self.simulation_id = simulation_id
        self.scenario_id = scenario_id
        self.map_id = map_id
        self.episode_context_id = episode_context_id
        self.scenario = scenario


class TestBenchService:
    """One episode of a deployment, watched live. Never a measurement.

    **The gap this fills.** Before a comparison spends hours on three
    hundred episodes there is no way to see *one* of them. A mission whose
    goal sits behind a shelf, a noise amplitude entered a decimal place
    out, a robot radius that will not fit the doorway — each of those
    costs the whole run and shows up at the end as a uniform wall of
    ``no_path`` that looks like a platform fault. Watching one episode
    costs seconds and answers the question directly.

    **Why it assembles the episode from the contract rather than a form.**
    The point is fidelity: what you watch has to be what the comparison
    will run, or it is a different experiment offering false comfort.
    So the scenario comes from :func:`scenario_for` — the same function
    :func:`run_contract_episode` calls — and the planners come from the
    same registry entry with the same episode seed. Nothing here is
    allowed to invent a condition.

    **Why it writes no trace, and why that is the whole safety argument.**
    HĐ-5 makes the Parquet trace the sole input of the Metrics Engine. A
    test-bench episode that wrote one would inject an episode into the
    evaluation set outside the context-outer run order (HĐ-3.2) and
    outside the ban on two concurrent evaluation runs (HĐ-7.4) — and it
    would do so with a *real* ``episode_context_id``, so nothing
    downstream could tell it apart from a measured episode. Instead the
    run lands in the simulations store, which no gate, metric or card
    ever reads. The id is real; the run is not evidence.
    """

    def __init__(self, repos: Any, *, map_root: Path) -> None:
        self._repos = repos
        self._maps: MapRepositoryPort = repos.maps
        self._scenarios = repos.scenarios
        self._profiles: TaskProfileRepository = repos.task_profiles
        self._map_root = map_root

    def stage(
        self,
        *,
        task_profile_id: str,
        mission_id: str,
        seed: int,
        stack: str,
        local_config: str,
    ) -> TestBenchStaging:
        """Build the episode and hand back a simulation ready to run."""
        from planbench_api.services import SimulationService
        from planbench_benchmark.episode import EpisodeSetupError, scenario_for
        from planbench_benchmark.task_map import MapProfileMismatch, load_task_map
        from planbench_schemas.episode_context import EpisodeContext

        profile = TaskProfile.model_validate(self._profiles.get(task_profile_id).profile)

        params = LOCAL_CONTROLLER_CONFIGS.get(local_config)
        if params is None:
            raise DomainValidationError(
                f"no local-controller configuration named {local_config!r}; "
                f"known: {', '.join(sorted(LOCAL_CONTROLLER_CONFIGS))}"
            )

        context = EpisodeContext(
            task_profile_id=task_profile_id, mission_id=mission_id, seed=seed
        )
        try:
            scenario = scenario_for(profile, context)
        except EpisodeSetupError as error:
            raise DomainValidationError(str(error)) from error

        try:
            map_data = load_task_map(profile, base_dir=self._map_root, validate=True)
        except MapProfileMismatch as error:
            raise DomainValidationError(str(error)) from error
        except FileNotFoundError as error:
            raise DomainValidationError(
                f"deployment {task_profile_id!r} names a map that is not on disk: {error}"
            ) from error

        stored_map = self._existing_map(map_data) or self._maps.create(map_data)
        stored_scenario = self._existing_scenario(
            stored_map.id, scenario.name
        ) or self._scenarios.create(stored_map.id, scenario)

        # Through the service rather than the repository, so the same
        # refusals a hand-built simulation gets apply here: an unknown
        # stack, a config the controller will not accept, a scenario the
        # map cannot support. Replanning is left at its default off, which
        # is also what `run_contract_episode` runs with — a test bench
        # that quietly enabled it would be showing a different stack from
        # the one the comparison will measure.
        stored_simulation = SimulationService(self._repos).create(
            stored_map.id, stored_scenario.id, stack, params
        )

        return TestBenchStaging(
            simulation_id=stored_simulation.id,
            scenario_id=stored_scenario.id,
            map_id=stored_map.id,
            episode_context_id=context.episode_context_id,
            scenario=scenario.model_dump(mode="json"),
        )

    def _existing_map(self, map_data: Any) -> StoredMap | None:
        """A stored map with these exact walls, if one is already there.

        Staging is idempotent in the thing that matters: watching the same
        deployment twenty times leaves one map row, not twenty. Equality is
        on the grid itself because that is what identity means here — two
        rows holding the same occupancy are the same world however they
        got there.
        """
        for stored in self._maps.list():
            if stored.map_data == map_data:
                return stored
        return None

    def _existing_scenario(self, map_id: str, name: str) -> Any | None:
        """The scenario for this context, if it has been staged before.

        Matched on the name, which :func:`scenario_for` sets to the
        ``episode_context_id`` — so the lookup key is the hash of the
        conditions rather than a label somebody typed.
        """
        for stored in self._scenarios.list():
            if stored.map_id == map_id and stored.scenario.name == name:
                return stored
        return None
