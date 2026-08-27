"""Service layer: domain orchestration between routers and repositories.

Routers hold no simulation logic; everything domain-shaped lives here
or in the core packages.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from planbench_api.accounts import User
from planbench_api.approval import (
    Action,
    ApprovalRecord,
    BenchmarkState,
    Capability,
    Role,
    TransitionError,
    next_state,
)
from planbench_api.auth import Forbidden
from planbench_api.errors import DomainValidationError, InvalidStateError, NotFoundError
from planbench_api.registry_service import ModelRegistryService
from planbench_api.repositories import (
    RepositoryHub,
    StoredBenchmark,
    StoredMap,
    StoredScenario,
    StoredSimulation,
)
from planbench_api.review import ReviewStage, ReviewStatus
from planbench_api.review_service import ReviewService
from planbench_api.worker import Job, JobQueue
from planbench_benchmark import (
    AlgorithmSpec,
    BenchmarkSpec,
    build_global_planner,
    build_local_planner,
    list_algorithms,
    run_benchmark,
    validate_algorithm_config,
)
from planbench_benchmark.registry import AlgorithmConfigError, UnknownAlgorithmError
from planbench_schemas.map import MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.engine import SimulationEngine
from planbench_simulator.nav_stack import StackRun, run_stack
from planbench_tracking import ExperimentTracker, NullTracker

logger = logging.getLogger("planbench.api.services")


class BenchmarkCancelled(Exception):
    """Raised inside the run loop when an operator cancels mid-benchmark."""


DEFAULT_ALGORITHM = "astar+dwa"

#: Which review stage, if any, gates each action. Spec review guards
#: everything that leads to a run; result review guards the verdict on
#: what the run produced.
REVIEW_STAGE_FOR: dict[Action, ReviewStage] = {
    Action.SUBMIT: ReviewStage.SPEC,
    Action.SELF_APPROVE: ReviewStage.SPEC,
    Action.APPROVE: ReviewStage.SPEC,
    Action.REJECT: ReviewStage.SPEC,
    Action.RUN: ReviewStage.SPEC,
    Action.ACCEPT_RESULT: ReviewStage.RESULT,
    Action.REJECT_RESULT: ReviewStage.RESULT,
}

#: States from which the owner may clear their own spec gate on the way
#: to a run. APPROVED is absent: it is already through.
SELF_APPROVABLE = frozenset(
    {BenchmarkState.DRAFT, BenchmarkState.REJECTED, BenchmarkState.PENDING_APPROVAL}
)

#: Actions the owner loses while the matching review is pending. Asking
#: for review and then answering it yourself is the one thing the whole
#: feature has to prevent.
OWNER_BLOCKED_BY_REVIEW = frozenset(
    {
        Action.SELF_APPROVE,
        Action.RUN,
        Action.ACCEPT_RESULT,
        Action.REJECT_RESULT,
    }
)


#: The one message a user should ever see for "you did not pick a model".
#: The raw Pydantic version of this — `invalid config for astar+ppo
#: model_path Field required` — names an internal field and tells the
#: reader nothing they can act on.
NO_PPO_MODEL_MESSAGE = (
    "You have not chosen a PPO model. Pick one you have uploaded, or upload a new "
    "one — PPO needs a trained model, which is the .zip that Stable-Baselines3 saves."
)


def require_algorithm(algorithm: str, config: dict | None = None) -> None:
    """Validate an algorithm id and its config, as domain errors."""
    try:
        validate_algorithm_config(algorithm, config)
    except UnknownAlgorithmError as exc:
        raise DomainValidationError(str(exc)) from exc
    except AlgorithmConfigError as exc:
        # Rewrite the one case a user hits by clicking rather than by
        # crafting a request: choosing PPO and not choosing a model.
        if algorithm == "astar+ppo" and not (config or {}).get("model_id"):
            raise DomainValidationError(NO_PPO_MODEL_MESSAGE) from exc
        raise DomainValidationError(str(exc)) from exc


class MapService:
    """Maps, and who is allowed to change one.

    **Ownership here is narrower than it looks.** A map with no owner is
    shared, not protected: rows made before accounts existed read that
    way, and so does a grid `adopt` handed back because the library
    already defined it. Refusing to let anybody edit those would strand
    them; letting anybody edit an *owned* one would let a person change
    the ground under somebody else's stored scenario.
    """

    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(self, map_data: MapData, owner_user_id: str | None = None) -> StoredMap:
        return self._repos.maps.create(map_data, owner_user_id=owner_user_id)

    def adopt(self, map_data: MapData) -> StoredMap:
        """Store this grid, or hand back the row that already holds it.

        **The difference from `create` is who is asking.** `POST /maps`
        is a person filing a map and means it: two uploads of the same
        grid under different names are two things that person wanted.
        Importing a library scenario is not that — it is a caller who
        needs *a* map id for a grid the library already defines, and
        giving it a fresh row every time is how a form that merely
        opened wrote 117 copies of one hall into the store.
        """
        existing = self._repos.maps.find_by_checksum(map_data.checksum())
        return existing if existing is not None else self._repos.maps.create(map_data)

    def get(self, map_id: str) -> StoredMap:
        return self._repos.maps.get(map_id)

    def list(self) -> list[StoredMap]:
        return self._repos.maps.list()

    def update(self, map_id: str, map_data: MapData, actor_user_id: str | None = None) -> StoredMap:
        self._require_owner(self._repos.maps.get(map_id), actor_user_id)
        return self._repos.maps.update(map_id, map_data)

    def archive(self, map_id: str, actor_user_id: str | None = None) -> StoredMap:
        self._require_owner(self._repos.maps.get(map_id), actor_user_id)
        return self._repos.maps.archive(map_id)

    def delete(self, map_id: str) -> None:
        """Hard delete. Reached by the orphan sweep, not by the API."""
        self._repos.maps.delete(map_id)

    @staticmethod
    def _require_owner(stored: StoredMap, actor_user_id: str | None) -> None:
        if stored.owner_user_id is None or actor_user_id is None:
            return
        if stored.owner_user_id != actor_user_id:
            raise Forbidden(
                f"map {stored.id} belongs to another member. Copy it to make your own — "
                "editing it would change the ground under their stored scenarios"
            )

    def validate(self, map_data: MapData) -> list[str]:
        """Semantic checks beyond schema validation (schema ran at parse)."""
        errors: list[str] = []
        if not any(value == 0 for value in map_data.cells):
            errors.append("map has no free cells")
        return errors


class ScenarioService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(
        self, map_id: str, scenario: Scenario, owner_user_id: str | None = None
    ) -> StoredScenario:
        stored_map = self._repos.maps.get(map_id)
        errors = self.validate_against_map(stored_map.map_data, scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.scenarios.create(map_id, scenario, owner_user_id=owner_user_id)

    def adopt(self, map_id: str, scenario: Scenario) -> StoredScenario:
        """The scenario already stored on this map under this name, or a
        new one.

        Matched on map **and** name rather than on content: a library
        scenario is generated from its name, so two imports of the same
        entry onto the same grid are the same description twice. Two
        scenarios that merely *look* alike are not the same claim — the
        poses are an author's choice — so nothing broader than this is
        collapsed, and `create` is left alone for the callers filing a
        scenario somebody wrote.
        """
        for stored in self._repos.scenarios.list():
            if stored.map_id == map_id and stored.scenario.name == scenario.name:
                return stored
        return self.create(map_id, scenario)

    def get(self, scenario_id: str) -> StoredScenario:
        return self._repos.scenarios.get(scenario_id)

    def list(self) -> list[StoredScenario]:
        return self._repos.scenarios.list()

    def update(
        self,
        scenario_id: str,
        map_id: str,
        scenario: Scenario,
        actor_user_id: str | None = None,
    ) -> StoredScenario:
        self._require_owner(self._repos.scenarios.get(scenario_id), actor_user_id)
        stored_map = self._repos.maps.get(map_id)
        errors = self.validate_against_map(stored_map.map_data, scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.scenarios.update(scenario_id, map_id, scenario)

    def archive(self, scenario_id: str, actor_user_id: str | None = None) -> StoredScenario:
        self._require_owner(self._repos.scenarios.get(scenario_id), actor_user_id)
        return self._repos.scenarios.archive(scenario_id)

    def delete(self, scenario_id: str) -> None:
        """Hard delete. Reached by the orphan sweep, not by the API."""
        self._repos.scenarios.delete(scenario_id)

    @staticmethod
    def _require_owner(stored: StoredScenario, actor_user_id: str | None) -> None:
        """Unowned scenarios stay shared — see :class:`MapService`."""
        if stored.owner_user_id is None or actor_user_id is None:
            return
        if stored.owner_user_id != actor_user_id:
            raise Forbidden(
                f"scenario {stored.id} belongs to another member; copy it to make your own"
            )

    @staticmethod
    def validate_against_map(map_data: MapData, scenario: Scenario) -> list[str]:
        """Reuse the engine's placement validation; return errors as a list."""
        engine = SimulationEngine()
        engine.load_map(map_data)
        try:
            engine.load_scenario(scenario)
        except ValueError as exc:
            return [str(exc)]
        return []


class SimulationService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(
        self,
        map_id: str,
        scenario_id: str,
        algorithm: str,
        config: dict | None = None,
        replanning: ReplanningConfig | None = None,
    ) -> StoredSimulation:
        require_algorithm(algorithm, config)
        stored_map = self._repos.maps.get(map_id)
        stored_scenario = self._repos.scenarios.get(scenario_id)
        errors = ScenarioService.validate_against_map(stored_map.map_data, stored_scenario.scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.simulations.create(
            map_id, scenario_id, algorithm, config or {}, replanning or NO_REPLANNING
        )

    def get(self, simulation_id: str) -> StoredSimulation:
        return self._repos.simulations.get(simulation_id)

    def list(self) -> list[StoredSimulation]:
        return self._repos.simulations.list()

    def run(self, simulation_id: str) -> StoredSimulation:
        stored = self._repos.simulations.get(simulation_id)
        if stored.state == "finished":
            raise InvalidStateError(f"simulation {simulation_id!r} already finished")
        map_data = self._repos.maps.get(stored.map_id).map_data
        scenario = self._repos.scenarios.get(stored.scenario_id).scenario
        planner = build_local_planner(stored.algorithm, stored.config)
        # The scenario's own seed also seeds a sampling global planner,
        # so re-running a stored simulation reproduces the same path.
        global_planner = build_global_planner(stored.algorithm, episode_seed=scenario.random_seed)
        # The rule comes from the stored simulation, so re-running one
        # replays the conditions it was created with rather than whatever
        # the default happens to be today.
        stack_run: StackRun = run_stack(
            map_data, scenario, planner, global_planner, stored.replanning
        )
        logger.info(
            "simulation finished",
            extra={
                "context": {
                    "simulation_id": simulation_id,
                    "algorithm": stored.algorithm,
                    "status": stack_run.result.status.value,
                    "steps": stack_run.result.steps,
                    "replans": stack_run.metrics.replan_count,
                }
            },
        )
        return self._repos.simulations.set_finished(simulation_id, stack_run)


class BenchmarkService:
    """Benchmark orchestration over the core engine.

    M4 scope: sequential execution inside the request, plus the approval
    state machine. Background workers and parallelism arrive in M5.

    Running is gated on the APPROVED state, so an unapproved spec can
    never execute (spec section 21, gate 1).
    """

    def __init__(
        self,
        repos: RepositoryHub,
        tracker: ExperimentTracker | None = None,
        jobs: JobQueue | None = None,
        reviews: ReviewService | None = None,
        models: ModelRegistryService | None = None,
    ) -> None:
        self._repos = repos
        self._tracker = tracker or NullTracker()
        self._jobs = jobs
        self._reviews = reviews
        self._models = models

    # -- authorization -------------------------------------------------

    def is_owner(self, stored: StoredBenchmark, user: User) -> bool:
        """Whether this member created this benchmark.

        Benchmarks created before accounts existed have no owner id; for
        those, and only those, the stored creator *name* is compared
        against the caller's nickname. It is a weaker check, which is
        exactly why it is confined to rows that predate the strong one —
        without it, every benchmark from before the refactor would be
        stranded with nobody able to act on it.
        """
        if stored.owner_user_id:
            return stored.owner_user_id == user.id
        return bool(user.nickname) and stored.created_by == user.nickname

    def capabilities(
        self, stored: StoredBenchmark, user: User, action: Action
    ) -> frozenset[Capability]:
        """What this caller may do to this benchmark, for this action.

        The state machine is pure and knows nothing about review
        requests, so the "a pending review takes the owner's self-service
        action away" rule is applied here, where the requests live.

        An admin keeps their capability even when a review is pending.
        That is deliberate — somebody has to be able to unstick a request
        whose reviewer has left — and every such action lands in the
        audit trail with the admin's own id on it.
        """
        capabilities: set[Capability] = set()
        stage = REVIEW_STAGE_FOR.get(action)
        pending = (
            self._reviews.pending(stored.id, stage)
            if (self._reviews is not None and stage is not None)
            else None
        )
        # A pending request is a question the owner asked; answering it
        # themselves would make asking meaningless.
        owner_blocked = pending is not None and action in OWNER_BLOCKED_BY_REVIEW
        if self.is_owner(stored, user) and not owner_blocked:
            capabilities.add(Capability.OWNER)
        if pending is not None and pending.reviewer_user_id == user.id:
            capabilities.add(Capability.REVIEWER)
        if user.is_admin:
            capabilities.add(Capability.ADMIN)
        return frozenset(capabilities)

    def transition(
        self,
        benchmark_id: str,
        action: Action,
        user: User,
        comment: str = "",
        review_request_id: str | None = None,
        capabilities: frozenset[Capability] | None = None,
    ) -> StoredBenchmark:
        """Apply a lifecycle action, recording an audit entry.

        ``capabilities`` is normally computed here. Answering a review
        passes them in, because recording the answer is what ends the
        request's pending state — recomputing afterwards would find no
        pending request and refuse the reviewer their own decision.
        """
        stored = self._repos.benchmarks.get(benchmark_id)
        if capabilities is None:
            capabilities = self.capabilities(stored, user, action)
        try:
            target = next_state(stored.state, action, capabilities)
        except TransitionError as exc:
            raise InvalidStateError(str(exc)) from exc
        record = ApprovalRecord(
            benchmark_id=benchmark_id,
            user=user.label,
            user_id=user.id,
            role=Role.ADMIN if user.is_admin else Role.MEMBER,
            action=action,
            previous_state=stored.state,
            new_state=target,
            comment=comment,
            timestamp=datetime.now(UTC).isoformat(),
            review_request_id=review_request_id,
        )
        logger.info(
            "benchmark transition",
            extra={
                "context": {
                    "benchmark_id": benchmark_id,
                    "action": action.value,
                    "from": stored.state.value,
                    "to": target.value,
                    "user_id": user.id,
                    "capabilities": sorted(capability.value for capability in capabilities),
                }
            },
        )
        return self._repos.benchmarks.set_state(benchmark_id, target, record)

    def create(
        self,
        name: str,
        map_id: str,
        scenario_id: str,
        algorithms: list[AlgorithmSpec],
        seeds: list[int],
        owner: User,
        description: str = "",
        replanning: ReplanningConfig | None = None,
    ) -> StoredBenchmark:
        for algorithm in algorithms:
            require_algorithm(algorithm.id, algorithm.config)
        self._repos.maps.get(map_id)
        self._repos.scenarios.get(scenario_id)
        try:
            spec = BenchmarkSpec(
                name=name,
                description=description,
                algorithms=tuple(algorithms),
                seeds=tuple(seeds),
                replanning=replanning or NO_REPLANNING,
            )
        except ValueError as exc:
            raise DomainValidationError("invalid benchmark spec", [str(exc)]) from exc
        return self._repos.benchmarks.create(
            spec, map_id, scenario_id, owner.label, owner_user_id=owner.id
        )

    def get(self, benchmark_id: str) -> StoredBenchmark:
        return self._repos.benchmarks.get(benchmark_id)

    def list(self) -> list[StoredBenchmark]:
        return self._repos.benchmarks.list()

    def run(
        self,
        benchmark_id: str,
        user: User,
        on_progress: Callable[[int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> StoredBenchmark:
        """Execute the benchmark; store the report and episodes.

        The spec gate is still a gate — it just no longer needs a second
        person by default. An owner with nobody reviewing clears it
        themselves, and that is written to the audit trail as
        ``self_approved`` rather than ``approve``, so a reader can always
        tell which benchmarks a second pair of eyes actually saw.

        If a spec review is pending, the owner does not hold OWNER for
        SELF_APPROVE and this raises before any episode executes.
        """
        stored = self.get(benchmark_id)
        if stored.state in SELF_APPROVABLE:
            stored = self.transition(
                benchmark_id,
                Action.SELF_APPROVE,
                user,
                comment="approved by the owner; no reviewer was asked",
            )
        stored = self.transition(benchmark_id, Action.RUN, user)
        map_data = self._repos.maps.get(stored.map_id).map_data
        scenario = self._repos.scenarios.get(stored.scenario_id).scenario
        # Registry ids become file paths here and nowhere else: the
        # benchmark package must not know about API storage, and the
        # frontend must never see a path.
        spec = self._resolve_models(stored)

        # Episodes are persisted as they finish, so replay works without
        # re-running anything and the report itself stays metrics-only.
        finished = 0

        def store_episode(record, stack_run: StackRun) -> None:
            nonlocal finished
            self._repos.episodes.create(
                benchmark_id, record.algorithm, record.seed, stack_run, record
            )
            finished += 1
            if on_progress is not None:
                on_progress(finished)
            if should_cancel is not None and should_cancel():
                raise BenchmarkCancelled(f"benchmark {benchmark_id!r} cancelled by operator")

        try:
            report = run_benchmark(map_data, scenario, spec, on_run=store_episode)
        except BenchmarkCancelled:
            self.transition(benchmark_id, Action.CANCEL, user, comment="cancelled during run")
            raise
        except Exception:
            self.transition(benchmark_id, Action.FAIL, user, comment="execution error")
            raise
        logger.info(
            "benchmark finished",
            extra={
                "context": {
                    "benchmark_id": benchmark_id,
                    "episodes": len(report.runs),
                    "conditions_checksum": report.fairness.conditions_checksum,
                    # P05: every look at a held-out scenario is recorded.
                    # A held-out set erodes by being consulted, and that
                    # erosion is only auditable if each consultation left
                    # a trace.
                    "scenario_split": report.scenario_split,
                    "protocol_version": report.protocol_version,
                }
            },
        )
        self._repos.benchmarks.set_report(benchmark_id, report)
        # Tracking must never break a benchmark: build_tracker degrades to
        # a null tracker when MLflow is unavailable.
        self._tracker.log_benchmark(benchmark_id, report, {"created_by": stored.created_by})
        # Results now await the second human gate (Reviewer accept/reject).
        return self.transition(benchmark_id, Action.COMPLETE, user)

    # -- PPO models ----------------------------------------------------

    def _resolve_models(self, stored: StoredBenchmark) -> BenchmarkSpec:
        """Turn every registry ``model_id`` into a path the runner can open.

        Returns a spec for *this run only* — the stored spec keeps the
        id, which is what makes the benchmark reproducible. Writing the
        resolved path back would pin the result to a filesystem layout.

        Compatibility is re-checked here rather than trusted from
        creation time: a model can be disabled, replaced or deleted
        between drafting a benchmark and running it, and discovering
        that halfway through a run is worse than refusing at the start.
        """
        algorithms: list[AlgorithmSpec] = []
        changed = False
        for algorithm in stored.spec.algorithms:
            config = dict(algorithm.config or {})
            model_id = config.get("model_id", "")
            if algorithm.id != "astar+ppo" or not model_id:
                algorithms.append(algorithm)
                continue
            if self._models is None:  # pragma: no cover - wired in create_app
                raise InvalidStateError("the model registry is not available")

            report = self._models.compatibility(model_id, config.get("robot_profile_id") or None)
            if not report.ok:
                raise DomainValidationError(
                    f"the PPO model for this benchmark cannot be run: {report.errors[0]}",
                    list(report.errors),
                )
            record = self._models.get(model_id)
            config["model_path"] = self._models.internal_location(record)
            # The loader wants a sidecar naming the observation and
            # reward versions; the registry renders one from the record.
            config["metadata_path"] = self._models.sidecar_location(record)
            config["model_checksum"] = record.checksum
            config["model_version"] = record.version
            self._models.record_usage(model_id, stored.id)
            algorithms.append(AlgorithmSpec(id=algorithm.id, config=config))
            changed = True

        if not changed:
            return stored.spec
        return stored.spec.model_copy(update={"algorithms": tuple(algorithms)})

    # -- review bookkeeping --------------------------------------------

    def request_review(
        self,
        benchmark_id: str,
        user: User,
        stage: ReviewStage,
        reviewer_nickname: str,
        comment: str = "",
    ):
        """Ask a named member to look. Owner only; state does not move.

        The transition is validated *first*, so a non-owner is refused
        before a request row exists to clean up.
        """
        stored = self.get(benchmark_id)
        capabilities = self.capabilities(stored, user, Action.REQUEST_REVIEW)
        next_state(stored.state, Action.REQUEST_REVIEW, capabilities)
        if self._reviews is None:  # pragma: no cover - wired in create_app
            raise InvalidStateError("review requests are not available")
        request = self._reviews.request(
            benchmark_id=benchmark_id,
            stage=stage,
            requester=user,
            reviewer_nickname=reviewer_nickname,
            comment=comment,
        )
        # Sending a spec for review *is* submitting it. Without this the
        # benchmark would sit in DRAFT, APPROVE would have no edge to
        # take, and the reviewer's genuine approval would end up recorded
        # as the owner's self-approval on the next run.
        if stage is ReviewStage.SPEC and stored.state in {
            BenchmarkState.DRAFT,
            BenchmarkState.REJECTED,
        }:
            self.transition(
                benchmark_id,
                Action.SUBMIT,
                user,
                comment=f"sent to {reviewer_nickname} for spec review",
                review_request_id=request.id,
            )
        self.transition(
            benchmark_id,
            Action.REQUEST_REVIEW,
            user,
            comment=f"{stage.value} review requested from {reviewer_nickname}",
            review_request_id=request.id,
        )
        return request

    def cancel_review(self, benchmark_id: str, user: User, request_id: str):
        """Withdraw a pending request the caller sent."""
        stored = self.get(benchmark_id)
        capabilities = self.capabilities(stored, user, Action.CANCEL_REVIEW)
        next_state(stored.state, Action.CANCEL_REVIEW, capabilities)
        if self._reviews is None:  # pragma: no cover - wired in create_app
            raise InvalidStateError("review requests are not available")
        cancelled = self._reviews.cancel(request_id, user)
        self.transition(
            benchmark_id,
            Action.CANCEL_REVIEW,
            user,
            comment=f"{cancelled.stage.value} review request withdrawn",
            review_request_id=cancelled.id,
        )
        return cancelled

    def check_runnable(self, benchmark_id: str, user: User) -> None:
        """Raise exactly what :meth:`run` would, without running anything.

        The background path needs this: queueing a job that is going to be
        refused turns a 403 the caller could act on into a job that fails
        minutes later, in a log they are not watching.
        """
        stored = self.get(benchmark_id)
        if stored.state in SELF_APPROVABLE:
            next_state(
                stored.state,
                Action.SELF_APPROVE,
                self.capabilities(stored, user, Action.SELF_APPROVE),
            )
        else:
            next_state(stored.state, Action.RUN, self.capabilities(stored, user, Action.RUN))

    def decide(
        self,
        benchmark_id: str,
        user: User,
        stage: ReviewStage,
        status: ReviewStatus,
        comment: str = "",
    ) -> StoredBenchmark:
        """Approve or reject at ``stage``, from the benchmark's own page.

        When the caller is the pending request's reviewer this goes
        through :meth:`answer_review`, so the request is marked answered
        rather than left open next to a benchmark that already moved.
        Without a pending request it is a plain transition, which is how
        an owner accepts their own results.
        """
        pending = self._reviews.pending(benchmark_id, stage) if self._reviews else None
        if pending is not None and pending.reviewer_user_id == user.id:
            stored, _answered = self.answer_review(pending.id, user, status, comment)
            return stored
        return self.transition(
            benchmark_id, REVIEW_DECISION_ACTIONS[(stage, status)], user, comment
        )

    def answer_review(
        self, request_id: str, reviewer: User, status: ReviewStatus, comment: str = ""
    ) -> tuple[StoredBenchmark, object]:
        """Record a reviewer's decision and apply the transition it implies.

        The request is answered first: a rejected *spec* leaves a
        PENDING_APPROVAL benchmark in DRAFT, but a spec review sent on a
        DRAFT benchmark has no transition to apply at all. The decision
        must be recorded either way, otherwise the reviewer's answer
        would vanish whenever the benchmark happened to be in a state
        the machine has no edge from.
        """
        if self._reviews is None:  # pragma: no cover - wired in create_app
            raise InvalidStateError("review requests are not available")
        pending = self._reviews.get_request(request_id)
        stored = self.get(pending.benchmark_id)
        action = REVIEW_DECISION_ACTIONS[(pending.stage, status)]
        # Captured while the request is still pending; see transition().
        capabilities = self.capabilities(stored, reviewer, action)
        answered = self._reviews.answer(request_id, reviewer, status, comment)
        try:
            stored = self.transition(
                answered.benchmark_id,
                action,
                reviewer,
                comment=comment,
                review_request_id=answered.id,
                capabilities=capabilities,
            )
        except InvalidStateError:
            # No edge from here — the decision still stands, and the
            # owner sees it on the benchmark.
            logger.info(
                "review answered with no state change",
                extra={
                    "context": {
                        "request_id": request_id,
                        "state": stored.state.value,
                        "action": action.value,
                    }
                },
            )
        return stored, answered


#: How a reviewer's verdict maps onto a lifecycle action.
REVIEW_DECISION_ACTIONS: dict[tuple[ReviewStage, ReviewStatus], Action] = {
    (ReviewStage.SPEC, ReviewStatus.APPROVED): Action.APPROVE,
    (ReviewStage.SPEC, ReviewStatus.REJECTED): Action.REJECT,
    (ReviewStage.RESULT, ReviewStatus.APPROVED): Action.ACCEPT_RESULT,
    (ReviewStage.RESULT, ReviewStatus.REJECTED): Action.REJECT_RESULT,
}


class BenchmarkJobService:
    """Runs approved benchmarks on the bounded background worker.

    The approval gate is applied *before* queueing, so an unapproved
    benchmark never reaches the worker. Cancellation is cooperative: the
    worker stops between episodes so recorded results stay consistent.
    """

    def __init__(self, benchmarks: BenchmarkService, jobs: JobQueue) -> None:
        self._benchmarks = benchmarks
        self._jobs = jobs

    def start(self, benchmark_id: str, user: User) -> Job:
        # Refuse here, where the caller is still listening.
        self._benchmarks.check_runnable(benchmark_id, user)
        stored = self._benchmarks.get(benchmark_id)
        episodes = len(stored.spec.algorithms) * len(stored.spec.seeds)

        def work(job: Job) -> None:
            self._benchmarks.run(
                benchmark_id,
                user,
                on_progress=lambda done: _report(job, done),
                should_cancel=lambda: self._jobs.is_cancelled(job.id),
            )

        def _report(job: Job, done: int) -> None:
            job.progress = done
            job.message = f"{done}/{job.total} episodes finished"

        return self._jobs.submit(benchmark_id, "benchmark", work, total=episodes)

    def status(self, benchmark_id: str) -> Job | None:
        return self._jobs.get(benchmark_id)

    def cancel(self, benchmark_id: str) -> bool:
        return self._jobs.cancel(benchmark_id)


class EpisodeService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def get(self, episode_id: str):
        return self._repos.episodes.get(episode_id)

    def list_for_benchmark(self, benchmark_id: str):
        self._repos.benchmarks.get(benchmark_id)  # 404 if unknown
        return self._repos.episodes.list_for_benchmark(benchmark_id)


def algorithms_catalogue():
    """Registered stacks, for the /algorithms endpoint."""
    return list_algorithms()


__all__ = [
    "DEFAULT_ALGORITHM",
    "BenchmarkService",
    "EpisodeService",
    "MapService",
    "NotFoundError",
    "ScenarioService",
    "SimulationService",
    "algorithms_catalogue",
    "require_algorithm",
]
