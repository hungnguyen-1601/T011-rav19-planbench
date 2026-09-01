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
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
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
from planbench_api.map_files import ensure_profile_map_materialised, materialise_map
from planbench_api.repositories import StoredMap, now_iso
from planbench_api.repository_ports import MapRepositoryPort
from planbench_api.run_identity import PinnedRun
from planbench_api.worker import Job, JobQueue
from planbench_benchmark.candidates import (
    LOCAL_CONTROLLER_CONFIGS,
    ConfigControllerMismatch,
    candidate_from_stack,
    validate_config_names,
)
from planbench_benchmark.selection import DEFAULT_SCOPE, run_comparison
from planbench_explanation.case_packet import RobotFacts
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.detectors import DETECTOR_VERSION
from planbench_schemas.contracts import CONTRACTS_VERSION
from planbench_schemas.task_profile import TaskProfile

#: The margin below which one episode's utility difference is a tie.
#:
#: Preregistered — chosen before any real run was read — and passed into
#: the builder rather than looked up inside it, because a margin picked
#: after the distribution is visible is a margin picked to produce an
#: answer. Half a percent of the utility range, which is the smallest
#: gap this platform reports anywhere else without a confidence interval
#: beside it.
EPISODE_TIE_EPSILON = 0.005


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

    def validate(self, payload: dict[str, Any]) -> TaskProfile:
        """The contract check on its own, with nothing stored.

        Validation happens through ``TaskProfile`` rather than here: it
        is the single definition of the contract, and it is what refuses
        a heading requirement the platform cannot evaluate, a periodic
        obstacle that shifts by less than one period, and a RAM budget
        that does not add up. Re-checking any of that at this layer would
        be a second opinion nobody asked for.

        **Split out so a caller can ask without filing.** The form needs
        the verdict while somebody is still typing, and the only honest
        way to give it is to run the check that will actually decide —
        anything else is a preview free to disagree with the refusal.
        ``create`` goes through here for the same reason: two entry
        points wrapping ``model_validate`` themselves would be two
        definitions of what a refusal looks like.

        **What this does not see.** It reads the document and nothing
        else — no repository, no ids in use. So an id already filed with
        different content still passes here and is refused by ``create``
        (HĐ-3.1); the endpoint says so rather than letting a caller read
        a pass as "this will file".
        """
        try:
            return TaskProfile.model_validate(payload)
        except Exception as error:  # pydantic ValidationError and friends
            # The blob message stays — it is what somebody pasting YAML
            # reads — and the per-field addresses travel beside it, which
            # is what a form with thirty inputs needs to turn a refusal
            # into a red outline on the right row.
            raise DomainValidationError(
                f"task profile is not valid under HĐ-2: {error}", field_errors(error)
            ) from error

    def create(self, payload: dict[str, Any], *, owner_user_id: str | None) -> StoredTaskProfile:
        """Validate against HĐ-2, then store."""
        profile = self.validate(payload)
        return self._repository.create(profile.model_dump(mode="json"), owner_user_id=owner_user_id)

    def replace(self, profile_id: str, payload: dict[str, Any]) -> StoredTaskProfile:
        """Correct a deployment, but only while nothing has measured it.

        **Why this is allowed at all, given that `create` refuses it.**
        That refusal is not about editing; it is about *stored runs*.
        ``episode_context_id`` hashes ``(task_profile_id, mission_id,
        environment_variant, seed)`` and HĐ-3.1 freezes that payload, so
        re-filing a changed deployment under the same id would produce
        contexts hashing identically to the old world's and every stored
        run would silently start describing somewhere that no longer
        exists. All of that damage is done *to runs*. A deployment
        nothing has ever run has no such runs to damage: it is a
        description somebody typed, and correcting a description is not
        rewriting history.

        So the gate is the same one ``delete`` uses, and for the same
        reason — a deployment nobody ran is a draft. The moment a single
        comparison exists this refuses, and the way forward is to derive
        a new deployment, which is what ``derive`` is for.

        **The id may not move.** A payload naming a different id is not
        an edit of this deployment, it is a second one; letting it
        through would leave the row's key and the document's ``id``
        disagreeing, and every reader picks a different one of the two.

        The map is materialised afterwards for the same reason ``create``
        leaves it to ``get``: the document may now name a custom map that
        has never been written to disk, and the engine reads files.
        """
        stored = self._repository.get(profile_id)
        if getattr(stored, "is_reference", False):
            raise InvalidStateError(
                f"deployment {profile_id!r} is a reference deployment: it is the fixed "
                "ground imported algorithms are validated against, so it cannot be "
                "edited or deleted"
            )

        incoming_id = str(payload.get("id", "")).strip()
        if incoming_id != profile_id:
            raise DomainValidationError(
                f"this edits deployment {profile_id!r}, but the document says "
                f"{incoming_id or '(nothing)'!r}. Renaming a deployment makes a second one; "
                "file it under its own id instead",
                [{"path": "id", "message": f"expected {profile_id!r}"}],
            )

        runs = self._runs.list(task_profile_id=profile_id) if self._runs is not None else []
        if runs:
            approved = sum(1 for run in runs if run.config_state == "approved")
            raise InvalidStateError(
                f"deployment {profile_id!r} has {len(runs)} stored run(s), so it can no longer "
                "be edited: episode_context_id does not hash the environment (HĐ-3.1), and "
                "changing this deployment would leave those runs describing a world that no "
                "longer exists while their ids still matched. Derive a new deployment from "
                "this one instead — it copies everything and takes its own id.",
                [
                    {
                        "runs": len(runs),
                        "approved": approved,
                        "ranked": sum(1 for run in runs if run.recommended_candidate_id),
                    }
                ],
            )

        profile = self.validate(payload)
        updated = self._repository.replace(profile_id, profile.model_dump(mode="json"))
        ensure_profile_map_materialised(updated.profile, self._map_root, self._maps)
        return updated

    def editable(self, profile_id: str) -> bool:
        """Whether `replace` would be allowed, without attempting it.

        The list view needs this per row to decide whether to offer an
        edit at all, and offering one that always refuses is worse than
        offering none.
        """
        stored = self._repository.get(profile_id)
        if getattr(stored, "is_reference", False):
            return False
        if self._runs is None:
            return True
        return not self._runs.list(task_profile_id=profile_id)

    def get(self, profile_id: str) -> StoredTaskProfile:
        stored = self._repository.get(profile_id)
        ensure_profile_map_materialised(stored.profile, self._map_root, self._maps)
        return stored

    def list(self) -> list[StoredTaskProfile]:
        return self._repository.list()

    def delete(self, profile_id: str, *, delete_runs: bool = False) -> int:
        """Remove a deployment; return how many runs went with it.

        A **reference** deployment is refused outright. It is the fixed
        ground a reviewer validates imported algorithms against, and two
        validation runs are only comparable if what they ran on did not
        change between them — so it is not the owner who may not delete
        it, it is nobody.

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
        stored = self._repository.get(profile_id)
        if getattr(stored, "is_reference", False):
            raise InvalidStateError(
                f"deployment {profile_id!r} is a reference deployment: it is the fixed "
                "ground imported algorithms are validated against, so it cannot be "
                "edited or deleted"
            )
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
            self._runs.delete_for_profile(profile_id) if runs and self._runs is not None else 0
        )
        self._repository.delete(profile_id)
        return removed

    def load(self, profile_id: str) -> TaskProfile:
        """The stored profile as the contract object the engine needs."""
        stored = self._repository.get(profile_id)
        ensure_profile_map_materialised(stored.profile, self._map_root, self._maps)
        return TaskProfile.model_validate(stored.profile)

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
        local_config: str = "",
        params: dict[str, Any] | None = None,
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
        # Two doors, one identity. A named config and an explicit params
        # dict both end in `candidate_from_stack`, which computes the one
        # hash everything downstream keys on — so a paper's stated
        # parameters register to exactly the id the paper reading
        # printed. Both at once is ambiguous and refused out loud: a
        # caller who names `dwa_coarse` *and* sends params would get
        # whichever this function preferred, silently, and silence here
        # is an identity bug waiting to be filed.
        if params is not None and local_config:
            raise DomainValidationError(
                "give either a named local_config or explicit params, not both; "
                "with both, which one defines the candidate would be this "
                "function's private decision"
            )
        if params is None and local_config not in LOCAL_CONTROLLER_CONFIGS:
            raise DomainValidationError(
                f"unknown local controller {local_config!r}; "
                f"known: {sorted(LOCAL_CONTROLLER_CONFIGS)}"
            )
        # **Existing is not the same as belonging.** Configuration names
        # are one flat namespace, and `dwa_coarse` is a perfectly real
        # name that has nothing to do with `dwa_predictive` — while every
        # one of its keys is a valid field there, so the pair constructs,
        # stores, and then labels every report with a configuration the
        # candidate never used.
        #
        # The comparison path gained this check at `build_candidates`;
        # registration is the *other* door into the same mistake, and a
        # candidate saved through it is wrong from then on rather than
        # wrong for one run.
        if params is None:
            try:
                validate_config_names([(stack, local_config)])
            except ConfigControllerMismatch as error:
                raise DomainValidationError(str(error)) from error
        try:
            # The explicit-params path needs no belonging check of its
            # own: `candidate_from_stack` rejects any parameter the
            # stack's config model does not declare, which is the same
            # guarantee stated directly instead of via a config name.
            candidate = candidate_from_stack(
                stack,
                params=dict(params)
                if params is not None
                else dict(LOCAL_CONTROLLER_CONFIGS[local_config]),
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


def _candidate_bundle(run) -> dict | None:
    """The imported bundle the recommended candidate ran, if there was one.

    Reads the pinned identity rather than resolving the stack name now:
    the name points at whatever is published today, and this file is
    about what was measured then.
    """
    recommended_id = run.recommended_candidate_id
    for entry in getattr(run, "candidates", []) or []:
        if not entry.get("bundle_id"):
            continue
        # Matched on stack rather than candidate_id, because the pinned
        # row records what was asked for and the card records the hash of
        # what it became.
        if recommended_id and entry.get("stack") not in str(run.card or ""):
            continue
        return {
            "bundle_id": entry.get("bundle_id"),
            "plugin_id": entry.get("plugin_id"),
            "revision": entry.get("revision"),
            "archive_checksum": entry.get("archive_checksum"),
        }
    return None


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
        maps: MapRepositoryPort | None = None,
    ) -> None:
        self._runs = runs
        self._profiles = profiles
        self._maps = maps or getattr(profiles, "_maps", None)
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
        pinned: PinnedRun | None = None,
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
        return self._store(
            report, stored_profile, scope=scope, created_by=created_by, pinned=pinned
        )

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
        pinned: PinnedRun | None = None,
        recheck=None,
        stop_check=None,
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

            def should_stop() -> str | None:
                """Asked at every episode boundary.

                Two things can make a queued sweep stop being the right
                thing to run: the person who asked for it cancelled, or
                something it depends on was withdrawn. Both are checked
                here rather than only before the first episode, because
                a three-hour warehouse sweep spends almost all of its
                life *after* that point.
                """
                if jobs.is_cancelled(job.id):
                    return "cancelled by the account that started it"
                if stop_check is not None:
                    return stop_check()
                return None

            ensure_profile_map_materialised(stored_profile.profile, self._repo_root, self._maps)

            # **Re-checked, not re-resolved.** Between the request and
            # this line a reviewer can publish a new revision or withdraw
            # the one that was pinned. Asking the question again would
            # quietly measure whatever is current now, under a run id
            # that claims to be about what was requested; comparing
            # against the pin lets the job fail with the name of the
            # thing that moved, which is recoverable.
            if recheck is not None and pinned is not None:
                recheck(pinned)

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
                should_stop=should_stop,
            )
            stored = self._store(
                report, stored_profile, scope=scope, created_by=created_by, pinned=pinned
            )
            job.run_id = stored.id
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
        return jobs.submit(
            job_id,
            "decision_run",
            work,
            total=0,
            created_by=created_by,
            purpose=(pinned.purpose.value if pinned is not None else "production"),
            pinned=pinned,
        )

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
        relaxed: bool = False,
    ) -> StoredDecisionRun:
        """``relaxed`` comes from the deployment, never from the request.

        It is the single-person install's answer to "may one account both
        create a run and sign it?". Passed down rather than read here so
        the store stays a state machine with no opinion about where it is
        running — and so a caller cannot ask for it.
        """
        return self._runs.decide_config(
            run_id,
            approve=approve,
            actor_user_id=actor_user_id,
            username=username,
            comment=comment,
            relaxed=relaxed,
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
        from planbench_simulator.trace import find_traces

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

        # Searched, not constructed. A trace is now addressed by its
        # evidence class and the conditions it ran under, and this
        # endpoint knows neither — building a path from a guessed
        # fingerprint would produce a filename rather than an answer.
        # The search applies the production policy, so an oracle episode
        # is *not found* here rather than downloadable as evidence.
        profile = self._profiles.load(run.task_profile_id)
        map_data = load_task_map(profile, base_dir=self._repo_root, validate=False)

        matches = find_traces(self._trace_root, candidate_id, episode_context_id)
        # **Narrowed to this run's world.** A pair can legitimately have
        # several production traces now — the same candidate measured
        # under two deployments — and taking whichever sorted last would
        # serve a different experiment's evidence under this run's name.
        # That is the defect the conditions hash was added to close, so
        # answering it with an arbitrary pick would reopen it at the one
        # endpoint a human actually looks through.
        expected = _expected_fingerprint(profile, map_data, episode_context_id)
        if expected:
            matches = [path for path in matches if path.parent.parent.name == expected]
        if not matches:
            raise NotFoundError("trace file", f"{candidate_id}/{episode_context_id}")
        if len(matches) > 1:
            raise InvalidStateError(
                f"{candidate_id}/{episode_context_id} has {len(matches)} traces under one "
                "set of conditions; the store is ambiguous and serving either would be a "
                "guess about which experiment this run meant"
            )
        path = matches[0]

        table = pq.read_table(path)
        columns = {name: table.column(name).to_pylist() for name in table.column_names}
        # Built once: the planned routes are placed against these same
        # indices, and two lists built the same way twice is two lists
        # that can disagree.
        events = [
            {"index": index, "event": value}
            for index, value in enumerate(columns.get("event", []))
            if value
        ]
        raw = (table.schema.metadata or {}).get(b"planbench_trace")
        metadata = json.loads(raw) if raw else {}

        return {
            "candidate_id": candidate_id,
            "episode_context_id": episode_context_id,
            "task_profile_id": run.task_profile_id,
            "metadata": metadata,
            "map": _packed_map(map_data),
            "robot_radius_m": profile.robot.radius,
            # G4's budget, so a latency chart can say where "too slow"
            # is rather than drawing a shape and leaving the reader to
            # supply the threshold from memory.
            "control_period_s": profile.robot.control_period,
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
            "events": events,
            # **What moved while the robot drove.** The map is static and
            # the trace records only the robot, so a canvas drawing both
            # showed a path bending around nothing — the one thing on
            # screen that explained the bend was missing from it. One
            # position per timestamp, so the obstacle and the robot are
            # always the same instant apart.
            "dynamic_obstacles": _obstacle_tracks(
                profile,
                _context_for(profile, episode_context_id),
                columns.get("t", []),
            ),
            # **What the planner asked for, beside where the robot
            # went.** A replan is the moment those two diverged, and a
            # canvas showing only the second cannot say so.
            "planned_routes": _planned_routes(path, events),
        }

    def replay_sync(
        self,
        run_id: str,
        episode_context_id: str,
        *,
        candidate_a: str,
        candidate_b: str,
        steps: int = 200,
    ) -> dict[str, Any]:
        """The two panels of one episode, aligned by arc length (E2).

        Time-sync needs nothing from the server: both panels already run
        off one clock in the browser. Progress-sync does, because the
        projection has rules — which line the arc length is measured
        along, and how honest that line is — and a second copy of them
        in TypeScript would drift from the one the tests cover.

        Thin on purpose. Two traces come out of :meth:`trace`, which
        already refuses an episode or a candidate that does not belong
        to this run and applies the production trace policy; everything
        after that is :func:`build_replay_sync_view`.
        """
        from planbench_explanation.replay_sync import ReferenceLine, ReplaySyncRefusal
        from planbench_explanation.replay_view import build_replay_sync_view

        payload_a = self.trace(run_id, candidate_a, episode_context_id)
        payload_b = self.trace(run_id, candidate_b, episode_context_id)
        try:
            view = build_replay_sync_view(
                payload_a,
                payload_b,
                # **The reference line can be the real plan now.** E4.5
                # records every attempt's polyline and the trace endpoint
                # serves it, so a run made after that gets
                # ``reference_plan`` quality instead of measuring arc
                # length along a candidate's own trajectory. A run made
                # before it passes ``None`` and the view still says which
                # lens it fell back to.
                planned_path=_first_route(payload_a),
                steps=steps,
            )
        except ReplaySyncRefusal as refusal:
            # A refusal here is a statement about *this evidence* — two
            # different episodes, a run with no samples, columns that do
            # not line up. The caller asked something the data cannot
            # answer, which is a 422; letting it fall through to the
            # global handler would file an expected outcome as an
            # internal error and bury it in the logs as a bug.
            raise DomainValidationError(str(refusal)) from refusal

        body = view.model_dump()
        body["running"] = self._running_block(
            run_id,
            payload_a,
            payload_b,
            # The same ruler the ladder was built on, handed back rather
            # than rebuilt: two rulers on one canvas is how a comparison
            # starts disagreeing with the chart above it.
            ReferenceLine(
                points=tuple(tuple(point) for point in view.plan.reference.points),
                quality=view.plan.reference.quality,
            ),
            view.plan.rows,
        )
        return body

    def _running_block(
        self,
        run_id: str,
        payload_a: dict[str, Any],
        payload_b: dict[str, Any],
        reference,  # type: ignore[no-untyped-def]
        rows: Sequence[Any],
    ) -> dict[str, Any] | None:
        """The E4.3 numbers, in the two shapes the page reads them in.

        ``ladder`` pairs the candidates at each rung of the progress
        scale — the comparison table. ``by_step`` is each candidate's own
        series, one entry per row of its trace, which is what the tiles
        under each canvas show as the scrubber moves.

        **One computation, two shapes.** The alternative was to let the
        browser derive the tiles from the trace columns it already has,
        which is a second implementation of "the running minimum
        clearance" living in a different language — free to drift from
        this one, and the drift invisible because both would render as
        clearances. Everything here is projected onto the same reference
        line the ladder above it uses.

        ``None`` rather than an empty structure when the numbers cannot
        be made: a deployment whose anchors will not resolve has no
        objective curves, and a composite computed without them would be
        a number this platform did not author. Empty would read as "the
        two are identical".
        """
        from planbench_decision.anchors import AnchorError, load_anchors
        from planbench_decision.objectives import DecisionSettings
        from planbench_explanation.replay_sync import ReplaySyncRefusal
        from planbench_explanation.running_metrics import (
            Deployment,
            RunningMetricsRefusal,
            compare_at_progress,
            sample_series,
        )

        run = self._runs.get(run_id)
        profile = self._profiles.load(run.task_profile_id)
        try:
            anchors = load_anchors().resolve(profile)
        except AnchorError:
            return None
        if not rows:
            return None

        # **The line's own length, not the ladder's top rung.** The top
        # rung is the furthest point *both* candidates reached, so a run
        # where one fails early gives a short denominator and a
        # ``progress_fraction`` that reads 100% with the robot halfway
        # down the map. The tile is labelled "route covered"; the route
        # is the reference line.
        reference_length = reference.length_m
        if reference_length <= 0:
            return None
        deployment = Deployment(
            robot_radius_m=profile.robot.radius,
            control_period_s=profile.robot.control_period,
            clearance_warning_m=profile.constraints.clearance_warning_m,
            max_linear_velocity=profile.robot.max_linear_velocity,
            reference_length_m=reference_length,
        )

        try:
            slices = [_slice_for(payload, reference) for payload in (payload_a, payload_b)]
        except (ReplaySyncRefusal, RunningMetricsRefusal, ValueError):
            return None

        settings = DecisionSettings()
        ladder: list[dict[str, Any]] = []
        for row in rows:
            comparison = compare_at_progress(
                slices[0],
                slices[1],
                float(row.progress_m),
                deployment=deployment,
                settings=settings,
                anchors=anchors,
            )
            if comparison is None:
                continue
            ladder.append({"progress_m": float(row.progress_m), **comparison.model_dump()})

        # Indexed by trace row, so the tile under a canvas and the pose
        # drawn on it are the same instant. Anything else — a time grid
        # of its own, a decimated series — would drift against the
        # scrubber, and the drift would look like the metric moving.
        by_step = {
            side: [sample.model_dump() for sample in sample_series(slice_, deployment=deployment)]
            for side, slice_ in zip(("a", "b"), slices, strict=True)
        }
        return {"ladder": ladder, "by_step": by_step}

    def explanation(self, run_id: str) -> dict[str, Any]:
        """The analyst's case packet for one run (E4.1).

        Everything the decision page needs to show *evidence* rather
        than a verdict: the ΔU decomposition, what the detectors saw,
        what the contrast lattice would and would not attribute, the
        four preregistered exemplars, and the gaps the platform declares
        about itself.

        **Claims are not here, and that is not an omission.** A claim
        comes from the promotion matrix run over a checker result, and
        no analyst has passed the gate yet — so the honest answer is
        evidence with no conclusions drawn on it. The panel already
        knows how to render that state; what it lacked was the evidence.

        Refuses a run scored before E4.1 rather than returning an empty
        packet. The two are different facts, and only one of them means
        "nobody could explain this run".
        """
        from planbench_explanation.case_packet import CasePacketRefusal
        from planbench_explanation.packet_builder import packet_from_block

        run = self._runs.get(run_id)
        block = (run.report or {}).get("case_packet")
        try:
            packet = packet_from_block(block if isinstance(block, dict) else {})
        except CasePacketRefusal as refusal:
            # 409 for the same reason the exemplars route uses it: the
            # request is fine, the run is in a state that has no packet.
            raise InvalidStateError(str(refusal)) from refusal
        return {
            "packet": packet.model_dump(mode="json"),
            # Carried through so a reader can tell a thin packet from a
            # broken one without opening the report.
            "omissions": list(block.get("omissions") or []) if isinstance(block, dict) else [],
            "skipped_episodes": (
                list(block.get("skipped_episodes") or []) if isinstance(block, dict) else []
            ),
        }

    def exemplars(self, run_id: str) -> dict[str, Any]:
        """The four episodes the comparison page should open with (E2).

        Preregistered, so that which pair a reader sees first is not a
        choice somebody made after looking at the results. Refuses for a
        run scored before per-episode utility was stored: three of the
        four roles are defined on ΔU, and no column left in the report
        can stand in for it.
        """
        from planbench_explanation.exemplars import (
            ExemplarRefusal,
            select_exemplars_from_report,
        )

        run = self._runs.get(run_id)
        try:
            return select_exemplars_from_report(run.report or {}).model_dump()
        except ExemplarRefusal as refusal:
            # 409, not 422 and not 500: nothing is wrong with the
            # request. This run is in a state that has no exemplar set —
            # no card, or scored before per-episode utility was kept —
            # and the answer is the same however politely it is asked.
            raise InvalidStateError(str(refusal)) from refusal

    def episode_verdict(
        self,
        run_id: str,
        episode_context_id: str,
        *,
        candidate_a: str = "",
        candidate_b: str = "",
        tie_epsilon: float = EPISODE_TIE_EPSILON,
    ) -> dict[str, Any]:
        """One episode: who won, what happened to each side, what differed.

        Everything here is deterministic and **no model is involved**.
        The verdict is the utility this run already scored per episode;
        the diagnoses are the detectors over the two served traces; the
        contrasts are the platform's own rules over the two.

        The pair defaults to the run's own ``comparison_pair`` rather
        than to the first two candidates registered: which two a page
        compares is a claim, and the registration order is not one. A
        run that ranked nobody has no pair, and refuses rather than
        picking.

        Refuses a run scored before per-episode utility existed for the
        same reason the exemplars route does — the answer is the same
        however politely it is asked.
        """
        from planbench_explanation.episode_builder import (
            EpisodeBuildRefusal,
            build_episode_packet,
        )
        from planbench_explanation.episode_floor import episode_floor
        from planbench_explanation.exemplars import (
            CardlessPairRefusal,
            cardless_pair,
            compared_pair,
        )
        from planbench_explanation.packet_builder import DeploymentThresholds

        run = self._runs.get(run_id)
        report = run.report or {}

        if not candidate_a or not candidate_b:
            pair = compared_pair(report)
            if pair is None:
                # **A run with no card is still a run somebody has to
                # explain.** The card is refused when fewer than two
                # candidates clear the gates, and that refusal is about a
                # deployment claim; whether one stack reached the goal in
                # this episode and the other did not is a different claim,
                # settled without utility, and it is the one a reader with
                # a replay open is asking. Refusing it sent them a
                # sentence about ranking when they had asked about an
                # episode.
                #
                # The pair is still not guessed: `cardless_pair` reads a
                # run that compared exactly two candidates and refuses
                # three, because choosing two of three after the numbers
                # are visible is a choice nobody made.
                try:
                    candidate_a, candidate_b = cardless_pair(report)
                except CardlessPairRefusal as refusal:
                    raise InvalidStateError(
                        f"{refusal}; ask for two candidates explicitly if you want a "
                        "specific comparison"
                    ) from refusal
            else:
                candidate_a, candidate_b = pair

        traces: dict[str, dict[str, Any] | None] = {}
        for candidate_id in (candidate_a, candidate_b):
            try:
                traces[candidate_id] = self.trace(run_id, candidate_id, episode_context_id)
            except (NotFoundError, InvalidStateError):
                # One unreadable trace is a reason to say so beside the
                # other side's findings, not a reason to have no answer.
                traces[candidate_id] = None

        # The deployment is what a timeline is measured against, and it
        # can be gone: a run outlives the profile it was run under, and
        # the verdict itself needs none of it — the rows were scored
        # when the profile still existed. So a missing one costs the
        # timeline and the geometry, is said out loud, and does not cost
        # the answer.
        thresholds: DeploymentThresholds | None = None
        robot: RobotFacts | None = None
        try:
            profile = self._profiles.load(run.task_profile_id)
        except (NotFoundError, InvalidStateError):
            profile = None
        if profile is not None:
            thresholds = DeploymentThresholds(
                robot_radius_m=profile.robot.radius,
                control_period_s=profile.robot.control_period,
                clearance_warning_m=profile.constraints.clearance_warning_m,
                max_linear_velocity=profile.robot.max_linear_velocity,
            )
            robot = RobotFacts(radius_m=profile.robot.radius)

        try:
            packet = build_episode_packet(
                header=self._episode_header(run),
                run_id=run_id,
                episode_context_id=episode_context_id,
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                report=report,
                trace_a=traces[candidate_a],
                trace_b=traces[candidate_b],
                tie_epsilon=tie_epsilon,
                robot=robot,
                thresholds=thresholds,
            )
        except EpisodeBuildRefusal as refusal:
            raise InvalidStateError(str(refusal)) from refusal

        floor = episode_floor(packet)
        return {
            "packet": packet.model_dump(mode="json"),
            "verdict": packet.verdict.model_dump(mode="json"),
            "diagnoses": [item.model_dump(mode="json") for item in packet.diagnoses],
            "contrasts": [item.model_dump(mode="json") for item in packet.contrasts],
            "ruled_out": [item.model_dump(mode="json") for item in packet.ruled_out],
            "floor": {
                "abstained": floor.abstained,
                "proposals": [item.model_dump(mode="json") for item in floor.proposals],
                "bearings": dict(floor.bearings),
            },
            "omissions": list(packet.omissions),
            "candidate_a": candidate_a,
            "candidate_b": candidate_b,
            "episode_context_id": episode_context_id,
        }

    def episode_analysis(
        self,
        run_id: str,
        episode_context_id: str,
        *,
        candidate_a: str = "",
        candidate_b: str = "",
        policy: Any,
        provider: Any,
        caller: str,
        is_admin: bool,
        ledger: Any,
        in_flight: Any,
        artifact_root: Path,
        tie_epsilon: float = EPISODE_TIE_EPSILON,
    ) -> dict[str, Any]:
        """The deterministic answer, plus what a model made of it.

        **The deterministic half is served either way.** A refusal at any
        gate below removes the model's part and nothing else: a reader
        who cannot be shown a model's answer is still owed the verdict,
        the diagnoses and the differences, and a route that returned
        nothing would have made the model the feature rather than the
        layer on top of it.

        Four gates, in this order, each of which is somebody's decision
        rather than this code's: the mode this deployment runs in,
        whether this caller may read what the model wrote, what they
        have already spent today, and whether the identical question is
        already in flight.
        """
        from planbench_analyst.episode_prompts import episode_prompt_checksum
        from planbench_analyst.episode_runner import (
            EpisodeRound,
            episode_runtime_config,
            run_episode_round,
        )
        from planbench_analyst.episode_view import build_episode_view
        from planbench_analyst.features import RoundFeatures
        from planbench_api.episode_analysis import (
            artifact_path,
            dedup_key,
            today,
            visible_to,
            write_artifact,
        )
        from planbench_explanation.catalog import TOOL_CATALOG, TOOL_CATALOG_VERSION
        from planbench_explanation.magnitudes import render, unresolvable
        from planbench_explanation.versioning import artifact_checksum

        body = self.episode_verdict(
            run_id,
            episode_context_id,
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            tie_epsilon=tie_epsilon,
        )
        body["mode"] = policy.mode
        body["model"] = None
        body["audit"] = None

        if policy.mode == "off":
            # Absent here, not broken: the verdict route beside this
            # one keeps answering, and a 404 says the feature is not
            # part of this deployment rather than that it failed.
            raise NotFoundError("episode analyst", f"{run_id}/{episode_context_id}")
        refusal = policy.refusal(now=datetime.now(UTC).isoformat())
        if refusal:
            raise InvalidStateError(refusal)

        # **What a deployment actually runs, rather than the bare
        # baseline the arms were measured against.**
        #
        # Three of the four are on because each was measured and each
        # earned it, and all three are free at read time: the
        # placeholder is a prompt sentence that took silence from 60 per
        # cent of hold-out rounds to 43; the floor answers the rounds
        # that still end with nothing, which was eighteen of eighteen
        # with no model call at all; the rewording turn costs a second
        # call and only on a round that already lost everything, and it
        # rescued six of the fifteen it fired on.
        #
        # `ep_b1` — none of them — stays the arm every measurement is
        # reported against. What a reader is served and what an
        # experiment compares are different questions, and a baseline
        # that quietly gained features would answer neither.
        features = RoundFeatures(
            episode_scope=True,
            magnitude_placeholders=True,
            floor_when_silent=True,
            reword_once=True,
        )
        runtime = episode_runtime_config(
            features,
            source_manifest_hash=body["packet"]["header"]["source_manifest_checksum"],
            catalog_version=TOOL_CATALOG_VERSION,
        )
        runtime_checksum = artifact_checksum(runtime)
        packet_checksum = artifact_checksum(body["packet"])
        key = dedup_key(
            packet_checksum=packet_checksum,
            runtime_config_checksum=runtime_checksum,
        )

        spend_refusal = ledger.check(caller, policy=policy, today=today())
        if spend_refusal:
            raise InvalidStateError(spend_refusal)

        # **The same question, asked at the same time, is answered once.**
        # Two rounds of a non-deterministic model give two answers to a
        # question asked once, and two readers on the same episode would
        # be shown different explanations of it. This coalesces the
        # concurrent case; it is not a cache, and a request that arrives
        # after the first has finished runs its own round.
        slot, owned = in_flight.start(key)
        if not owned:
            slot.done.wait(timeout=policy.timeout_s)
            body["audit"] = {"served_from": "in_flight", "dedup_key": key}
            if slot.answer is not None and visible_to(policy, is_admin=is_admin):
                body["model"] = slot.answer
            return body

        packet = self._episode_packet_of(body)
        view = build_episode_view(packet)
        try:
            outcome = run_episode_round(
                EpisodeRound(
                    analysis_run_id=f"{run_id}:{episode_context_id}",
                    analyst_bundle_id=f"episode:{episode_prompt_checksum()[:16]}",
                    catalog=TOOL_CATALOG,
                ),
                view,
                provider,
                features=features,
                catalog=TOOL_CATALOG,
            )
        except Exception as failed:  # noqa: BLE001 - the provider boundary
            # The round is the layer on top. Losing it must not lose the
            # verdict underneath, so the failure is reported in the audit
            # and the deterministic half is returned as it stands.
            in_flight.finish(key, answer=None, error=failed)
            body["audit"] = {"model_failed": str(failed)}
            return body

        # **The figures are filled in here, not by whoever renders this.**
        #
        # A statement may name a magnitude as a ref in braces rather than
        # writing the number, which is what lets it past rule 2 at all.
        # The slot has to be filled from the packet's own index, and the
        # index lives on this side; a client asked to do it would need
        # the whole fact table and a second copy of the rule for what
        # counts as fillable.
        #
        # The artifact below keeps what the model actually wrote, slots
        # and all. That separation is the point: the record holds the
        # analyst's words, the reader gets the platform's numbers in
        # them, and the two can be compared afterwards by anybody who
        # wonders whether a figure was ever really cited.
        served = outcome.response.model_dump(mode="json")
        facts = {fact.ref: fact.value for fact in view.facts}
        for proposal in served.get("proposals", ()):
            statement = proposal.get("hypothesis_statement") or ""
            if unresolvable(statement, facts):
                # The guard refuses these before they reach here, so a
                # slot arriving unfillable means the two disagree. Left
                # as written rather than papered over: a sentence with a
                # visible slot is a bug somebody can see and report.
                continue
            proposal["hypothesis_statement"] = render(statement, facts)
        model_part = {
            "response": served,
            "annotations": dict(outcome.annotations),
        }
        audit = {
            "blocked": [
                {"hypothesis_id": item.hypothesis_id, "rule": item.rule, "detail": item.detail}
                for item in outcome.blocked
            ],
            "prompt_checksum": episode_prompt_checksum(),
            "runtime_config_checksum": runtime_checksum,
            "packet_checksum": packet_checksum,
            "dedup_key": key,
        }
        in_flight.finish(key, answer=model_part, error=None)
        ledger.record(caller, today=today(), tokens=outcome.cost.output_tokens)

        # Written in every mode that runs a round, shadow included: the
        # artifact is how a shadow round is read at all, and a mode that
        # ran a model and kept no record of it would be spending for
        # nothing.
        write_artifact(
            artifact_path(
                artifact_root,
                run_id=run_id,
                episode_context_id=episode_context_id,
                key=key,
            ),
            {
                # As the analyst wrote it, placeholders intact.
                "model": {
                    "response": outcome.response.model_dump(mode="json"),
                    # Dataclasses, and `write_artifact` knows how to
                    # record one. Encoding them here as well would put
                    # the same rule in two places, and the writer is
                    # the place every caller already goes through.
                    "annotations": dict(outcome.annotations),
                },
                "audit": audit,
                "verdict": body["verdict"],
            },
        )

        body["audit"] = audit
        if visible_to(policy, is_admin=is_admin):
            body["model"] = model_part
        return body

    def _episode_packet_of(self, body: Mapping[str, Any]) -> Any:
        """The packet this response was built from, back as an object."""
        from planbench_explanation.episode_packet import EpisodePacket

        return EpisodePacket.model_validate(body["packet"])

    def _episode_header(self, run: Any) -> Any:
        """The provenance header an episode packet carries.

        Reuses the run's own manifest reference and checksum: an episode
        packet explains part of that run, and a header naming anything
        else would let a reader check the wrong artifact and find it
        consistent.
        """
        from planbench_explanation.knowledge import KNOWLEDGE_BASE_VERSION
        from planbench_explanation.versioning import ExplanationArtifactHeader

        report = run.report or {}
        block = report.get("case_packet")
        if isinstance(block, dict):
            header = (block.get("packet") or {}).get("header")
            if isinstance(header, dict):
                return ExplanationArtifactHeader(**header)
        return ExplanationArtifactHeader.for_current_code(
            source_manifest_ref=str(report.get("run_uri") or f"runs/{run.id}"),
            source_manifest_checksum=str(report.get("run_checksum") or "0" * 64),
            detector_version=DETECTOR_VERSION,
            knowledge_base_version=KNOWLEDGE_BASE_VERSION,
            tool_catalog_version=TOOL_CATALOG_VERSION,
        )

    def approved_config(
        self, run_id: str, reliance: str = "active", warning: dict | None = None
    ) -> str:
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
            # **The two questions, kept apart.** ``approval.status`` below
            # says what a person decided and never changes.
            # ``reliance_status`` says whether that decision may still be
            # acted on, and is derived when this file is generated — an
            # algorithm disabled last week does not un-decide anything,
            # but it does mean this is no longer a configuration to run.
            "reliance_status": reliance,
            "candidate": {
                "candidate_id": recommended.get("candidate_id"),
                "stack": recommended.get("stack"),
                "params_ref": recommended.get("params_ref"),
                # Which bundle, at which revision. Without it a warning
                # about "the algorithm behind this" could not name it,
                # and a reader could not resolve the stack back to the
                # code — the alias points at whatever is published now.
                "bundle": _candidate_bundle(run),
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
                # What a person decided, and when. Paired with
                # ``reliance_status`` above and deliberately not merged
                # with it: this one is a record of a human act and never
                # changes, that one is a fact about the world now.
                "status": run.config_state,
                "approved_by": run.config_decided_by,
                "approved_at": run.config_decided_at,
                "reviewed_by": run.reviewed_by,
                "reviewed_at": run.reviewed_at,
            },
        }
        if warning:
            # Ahead of everything else in the file: somebody opening this
            # to copy a number should meet the reason it may not be a
            # number to copy before they reach it.
            payload = {"artifact": payload.pop("artifact"), "warning": warning, **payload}
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    # -- internals -----------------------------------------------------

    def _materialise(self, stored: StoredTaskProfile) -> Path:
        import yaml

        ensure_profile_map_materialised(stored.profile, self._repo_root, self._maps)
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
        pinned: PinnedRun | None = None,
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
                purpose=(pinned.purpose.value if pinned is not None else "production"),
                # Written in the same transaction as the run, so a stored
                # measurement can always say what it measured.
                candidates=[
                    {
                        "slot": row.slot,
                        "stack": row.stack,
                        "local_config": row.local_config,
                        "bundle_id": row.bundle_id,
                        "plugin_id": row.plugin_id,
                        "revision": row.revision,
                        "archive_checksum": row.archive_checksum,
                        "provider_fingerprint": row.provider_fingerprint,
                        "runtime_profile": row.runtime_profile,
                    }
                    for row in (pinned.candidates if pinned is not None else ())
                ],
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
        ensure_profile_map_materialised(profile, self._map_root, self._maps)

        params = LOCAL_CONTROLLER_CONFIGS.get(local_config)
        if params is None:
            raise DomainValidationError(
                f"no local-controller configuration named {local_config!r}; "
                f"known: {', '.join(sorted(LOCAL_CONTROLLER_CONFIGS))}"
            )

        context = EpisodeContext(task_profile_id=task_profile_id, mission_id=mission_id, seed=seed)
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
            stored_map.id, scenario
        ) or self._scenarios.create(stored_map.id, scenario)

        # Through the service rather than the repository, so the same
        # refusals a hand-built simulation gets apply here: an unknown
        # stack, a config the controller will not accept, a scenario the
        # map cannot support.
        #
        # **Replanning comes from the deployment**, exactly as
        # `run_contract_episode` takes it. This used to be hardcoded off
        # with a comment saying that matched the contract runner — true
        # then, because no profile could declare it, and false the moment
        # one could. A test bench running a stack that cannot replan while
        # the comparison runs one that can would break the single claim
        # this page makes: what you watch is what will be measured.
        stored_simulation = SimulationService(self._repos).create(
            stored_map.id, stored_scenario.id, stack, params, profile.replanning
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

        **On the checksum, which is what "the grid itself" means.** This
        used to compare whole ``MapData`` documents, and that comparison
        could never be true: the right-hand side has been written out as
        a map_server pair and read back, and a map read from disk takes
        its ``name`` from the image file's stem — ``b92f3f964633__v1``
        where the stored row says ``sudden-stop``. Same walls, same
        resolution, same origin, different name, so every staging call
        filed another row. One database reached 27 of them that way, and
        the copies then went on to confuse the *next* lookup: with the
        original edited, a stale duplicate is what an equality scan finds
        first.

        **Not `checksum()`, which hashes the name too.** That field is
        the identity of the *document* and is right to be — it backs
        `find_by_checksum`, which `adopt` uses to stop the library import
        filing the same entry twice under the same name. It cannot answer
        this question, because here the two names differ by design.

        The cheap fields are compared first so that a store holding
        hundreds of maps rejects almost all of them on three integers
        rather than on a list of several thousand cells.
        """
        for stored in self._maps.list():
            other = stored.map_data
            if (other.width, other.height, other.resolution) != (
                map_data.width,
                map_data.height,
                map_data.resolution,
            ):
                continue
            if other.origin != map_data.origin:
                continue
            if other.cells == map_data.cells:
                return stored
        return None

    def _existing_scenario(self, map_id: str, scenario: Any) -> Any | None:
        """A stored scenario identical to the one about to be staged.

        **Matched on content, and it used to be matched on the name.**
        The name is the ``episode_context_id``, and the old docstring
        called that "the hash of the conditions" — which is exactly the
        thing HĐ-3.1 says it is not. That id hashes the deployment id,
        the mission, the environment variant and the seed; it does *not*
        hash the traffic, the noise or the thresholds.

        So editing a deployment and staging it again produced the same
        name, the name matched a row built from the *old* document, and
        the bench replayed a world the deployment no longer described.
        Removing an obstacle changed nothing on screen — the strongest
        possible symptom, and one nothing else in the system would have
        contradicted, because a staged episode reaches no gate and no
        card.

        Comparing the scenario itself asks the question that was meant
        all along: is the world already stored the world we are about to
        run? A row that differs is left alone rather than overwritten —
        an earlier staged episode still describes what it actually ran,
        and these rows are cheap.
        """
        for stored in self._scenarios.list():
            if stored.map_id == map_id and stored.scenario == scenario:
                return stored
        return None


def _context_for(profile, episode_context_id: str):  # type: ignore[no-untyped-def]
    """The episode context behind an id, or ``None``.

    The id is a content hash, so it cannot be taken apart — the only way
    back is to rebuild the deployment's contexts and look for the one
    that hashes to it. Extracted because two callers now need it and a
    second copy of the scan would be a second place to forget the
    ``sample_set`` rule.
    """
    from planbench_benchmark.contexts import build_evaluation_contexts

    for context in build_evaluation_contexts(profile):
        if context.episode_context_id == episode_context_id:
            return context
    return None


def _obstacle_tracks(profile, context, times: list[float]) -> list[dict[str, object]]:
    """Where each dynamic obstacle was, at the trace's own timestamps.

    **Computed here, never in the browser.** ``position_at`` is the one
    implementation of these motion models, seed shift included, and a
    second copy in TypeScript would drift from it the first time either
    was fixed — the same argument that keeps progress-sync on the
    server. The page receives coordinates and draws circles.

    Sampled at the trace's timestamps rather than on a grid of its own,
    so an obstacle and the robot on the same canvas are always being
    shown at the same instant. Empty when the context could not be
    rebuilt: a moving obstacle drawn at the wrong seed's positions is
    worse than no obstacle, because it looks like evidence.
    """
    if context is None or not times:
        return []
    from planbench_schemas.dynamic import position_at

    tracks = []
    for obstacle in profile.environment.dynamic_obstacles:
        points = [position_at(obstacle, time, context.seed) for time in times]
        tracks.append(
            {
                "name": obstacle.name,
                "radius_m": obstacle.radius,
                "x": [point.x for point in points],
                "y": [point.y for point in points],
            }
        )
    return tracks


def _first_route(payload: Mapping[str, Any]) -> list[tuple[float, float]] | None:
    """The initial planned route, for use as the replay's reference line.

    The *first* attempt rather than the last: arc length has to be
    measured along one line for the whole episode, and a later replan's
    route describes only the part after it.
    """
    routes = payload.get("planned_routes") or []
    for route in routes:
        points = route.get("points") or []
        if len(points) >= 2:
            return [(float(point["x"]), float(point["y"])) for point in points]
    return None


def _slice_for(payload: Mapping[str, Any], reference):  # type: ignore[no-untyped-def]
    """One candidate's trace in the shape the running metrics take.

    Progress comes from :func:`~planbench_explanation.replay_sync.project`
    against **the reference line the view published**, so the arc length
    here is the same arc length the progress ladder was built on. An
    earlier draft used cumulative driven distance as a stand-in, which
    would have made ``path_efficiency`` — progress over distance driven —
    identically 1.0 for every candidate: a metric that renders, reads
    plausibly, and measures nothing.
    """
    from planbench_explanation.replay_sync import project
    from planbench_explanation.replay_view import _track  # noqa: PLC2701
    from planbench_explanation.running_metrics import TraceSlice

    projected = project(_track(payload), reference)
    replans = tuple(
        int(event["index"])
        for event in payload.get("events") or []
        if event.get("event") == "replan"
    )
    return TraceSlice(
        candidate_id=str(payload.get("candidate_id") or ""),
        t=tuple(float(value) for value in payload.get("t") or []),
        x=tuple(float(value) for value in payload.get("x") or []),
        y=tuple(float(value) for value in payload.get("y") or []),
        clearance_m=tuple(float(value) for value in payload.get("clearance_m") or []),
        planner_latency_ms=tuple(float(value) for value in payload.get("planner_latency_ms") or []),
        progress_m=tuple(sample.progress_m for sample in projected.samples),
        replan_indices=replans,
    )


def _planned_routes(trace_path, events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Every route the global planner returned, and when each took over.

    Read from the E4.5 sidecar beside the trace — nothing else keeps a
    plan's polyline. The metrics store its length, ``StackRun.plans``
    dies with the process that ran the episode, and the trace records
    where the robot *went*, which is the other half of the very
    comparison a reader is trying to make.

    **The handover point comes from the trace's own replan events, not
    from the sidecar's tick counter.** The record counts simulation
    ticks and the trace counts control steps; they are different clocks,
    and converting between them here would be a third opinion about the
    episode's timeline. The events are already in the payload and
    already indexed against the rows the canvas draws.

    Returns nothing rather than guessing when the two disagree. A run
    with three recorded attempts and one replan event is a run whose
    plans cannot be placed, and a route drawn at the wrong moment is a
    picture of a decision nobody made.
    """
    from planbench_explanation.planning_input_evidence import SidecarViolation
    from planbench_explanation.sidecar_writer import read_sidecar

    sidecar = trace_path.with_suffix(".planning_inputs.jsonl")
    if not sidecar.exists():
        return []
    try:
        _header, records = read_sidecar(sidecar)
    except (SidecarViolation, ValueError):
        # A sidecar that cannot be read is a file problem, not a reason
        # to fail a trace download. The canvas draws one fewer thing.
        return []

    replans = [int(event["index"]) for event in events if event.get("event") == "replan"]
    if len(records) != len(replans) + 1:
        return []

    # Attempt 1 is in force from the first row; attempt k+1 from the row
    # its replan was recorded on.
    starts = [0, *replans]
    routes = []
    for record, start in zip(records, starts, strict=True):
        if not record.output_path:
            # A refused attempt has no route. Recorded so the canvas can
            # say the plan went *away* at that step rather than silently
            # keeping the previous one on screen.
            routes.append({"attempt": record.planning_attempt, "from_index": start, "points": []})
            continue
        routes.append(
            {
                "attempt": record.planning_attempt,
                "from_index": start,
                "points": [{"x": x, "y": y} for x, y in record.output_path],
            }
        )
    return routes


def _expected_fingerprint(profile, map_data, episode_context_id: str) -> str:
    """The conditions hash this run's episode should carry, or ``""``.

    Rebuilt from the deployment rather than read off a file, so it is a
    statement about what was *asked for* and can be compared against
    what is on disk. Empty when the context cannot be reconstructed —
    the caller then falls back to the class filter alone rather than
    refusing a download over a lookup it could not perform.
    """
    from planbench_benchmark.episode import scenario_for
    from planbench_benchmark.fingerprint import execution_conditions_fingerprint

    context = _context_for(profile, episode_context_id)
    if context is None:
        return ""
    return execution_conditions_fingerprint(map_data, scenario_for(profile, context), profile)
