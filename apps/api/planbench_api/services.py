"""Service layer: domain orchestration between routers and repositories.

Routers hold no simulation logic; everything domain-shaped lives here
or in the core packages.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from planbench_api.accounts import User, UserRole
from planbench_api.approval import (
    Action,
    ApprovalRecord,
    BenchmarkState,
    Capability,
    PermissionDenied,
    Role,
    TransitionError,
    next_state,
)
from planbench_api.errors import DomainValidationError, InvalidStateError, NotFoundError
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
    build_local_planner,
    list_algorithms,
    run_benchmark,
    validate_algorithm_config,
)
from planbench_benchmark.registry import AlgorithmConfigError, UnknownAlgorithmError
from planbench_schemas.map import MapData
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


def _audit_role(user: User) -> Role:
    """What to write in an audit row's ``role`` field.

    ``is_admin`` wins the label even for a plain OWNER_ONLY action taken
    on the caller's own benchmark: it is a fact about the account, not
    about which capability happened to satisfy this particular action,
    and a reader scanning the trail for admin activity should be able to
    find every row where it applied.
    """
    if user.is_admin:
        return Role.ADMIN
    return Role.APPROVER if user.role is UserRole.APPROVER else Role.ENGINEER


def _approval_needed_message(state: BenchmarkState) -> str:
    """Shared by :meth:`BenchmarkService.run` and ``check_runnable``, so
    the synchronous and background-job paths refuse in exactly the same
    words rather than drifting apart.

    Only used to *enrich* a failure the state machine already decided to
    raise — never to pre-empt it. Checking approval state before
    permission would mean an unauthorized caller learns a benchmark's
    state (and gets a 409 instead of the 403 they should get) just by
    trying to run someone else's work.
    """
    return (
        "benchmark must be approved by an Approver before it can run "
        f"(current state: {state.value!r}); request a spec review, "
        "or have an admin clear it with admin_override if "
        "PLANBENCH_ADMIN_OVERRIDE_ENABLED is set"
    )


def require_algorithm(algorithm: str, config: dict | None = None) -> None:
    """Validate an algorithm id and its config, as domain errors."""
    try:
        validate_algorithm_config(algorithm, config)
    except UnknownAlgorithmError as exc:
        raise DomainValidationError(str(exc)) from exc
    except AlgorithmConfigError as exc:
        raise DomainValidationError(str(exc)) from exc


class MapService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(self, map_data: MapData) -> StoredMap:
        return self._repos.maps.create(map_data)

    def get(self, map_id: str) -> StoredMap:
        return self._repos.maps.get(map_id)

    def list(self) -> list[StoredMap]:
        return self._repos.maps.list()

    def update(self, map_id: str, map_data: MapData) -> StoredMap:
        return self._repos.maps.update(map_id, map_data)

    def delete(self, map_id: str) -> None:
        self._repos.maps.delete(map_id)

    def validate(self, map_data: MapData) -> list[str]:
        """Semantic checks beyond schema validation (schema ran at parse)."""
        errors: list[str] = []
        if not any(value == 0 for value in map_data.cells):
            errors.append("map has no free cells")
        return errors


class ScenarioService:
    def __init__(self, repos: RepositoryHub) -> None:
        self._repos = repos

    def create(self, map_id: str, scenario: Scenario) -> StoredScenario:
        stored_map = self._repos.maps.get(map_id)
        errors = self.validate_against_map(stored_map.map_data, scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.scenarios.create(map_id, scenario)

    def get(self, scenario_id: str) -> StoredScenario:
        return self._repos.scenarios.get(scenario_id)

    def list(self) -> list[StoredScenario]:
        return self._repos.scenarios.list()

    def update(self, scenario_id: str, map_id: str, scenario: Scenario) -> StoredScenario:
        stored_map = self._repos.maps.get(map_id)
        errors = self.validate_against_map(stored_map.map_data, scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.scenarios.update(scenario_id, map_id, scenario)

    def delete(self, scenario_id: str) -> None:
        self._repos.scenarios.delete(scenario_id)

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
        self, map_id: str, scenario_id: str, algorithm: str, config: dict | None = None
    ) -> StoredSimulation:
        require_algorithm(algorithm, config)
        stored_map = self._repos.maps.get(map_id)
        stored_scenario = self._repos.scenarios.get(scenario_id)
        errors = ScenarioService.validate_against_map(stored_map.map_data, stored_scenario.scenario)
        if errors:
            raise DomainValidationError("scenario is invalid for this map", errors)
        return self._repos.simulations.create(map_id, scenario_id, algorithm, config or {})

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
        stack_run: StackRun = run_stack(map_data, scenario, planner)
        logger.info(
            "simulation finished",
            extra={
                "context": {
                    "simulation_id": simulation_id,
                    "algorithm": stored.algorithm,
                    "status": stack_run.result.status.value,
                    "steps": stack_run.result.steps,
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
        admin_override_enabled: bool = False,
    ) -> None:
        self._repos = repos
        self._tracker = tracker or NullTracker()
        self._jobs = jobs
        self._reviews = reviews
        self._admin_override_enabled = admin_override_enabled

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
            role=_audit_role(user),
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

        The spec gate is a real gate: a benchmark still in DRAFT,
        REJECTED or PENDING_APPROVAL has not been reviewed by an
        Approver, and this raises before any episode executes rather
        than clearing the gate on the owner's behalf. The owner's own
        options from here are ``request_review`` (ask a named Approver)
        or, if the deployment allows it, ``admin_override``.
        """
        stored = self.get(benchmark_id)
        try:
            stored = self.transition(benchmark_id, Action.RUN, user)
        except InvalidStateError as exc:
            # Permission was already checked inside transition() — this
            # only fires for a caller who could otherwise run it, so
            # enriching the message here cannot leak state to anyone else.
            if stored.state in SELF_APPROVABLE:
                raise InvalidStateError(_approval_needed_message(stored.state)) from exc
            raise
        map_data = self._repos.maps.get(stored.map_id).map_data
        scenario = self._repos.scenarios.get(stored.scenario_id).scenario

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
            report = run_benchmark(map_data, scenario, stored.spec, on_run=store_episode)
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
                }
            },
        )
        self._repos.benchmarks.set_report(benchmark_id, report)
        # Tracking must never break a benchmark: build_tracker degrades to
        # a null tracker when MLflow is unavailable.
        self._tracker.log_benchmark(benchmark_id, report, {"created_by": stored.created_by})
        # Results now await the second human gate (Reviewer accept/reject).
        return self.transition(benchmark_id, Action.COMPLETE, user)

    def admin_override(
        self,
        benchmark_id: str,
        user: User,
        action: Action,
        comment: str,
    ) -> StoredBenchmark:
        """Clear the spec gate without an Approver — for a deployment with
        no second account to ask, not for routine use.

        Two independent checks before this reaches the state machine:
        the deployment must have opted in
        (``PLANBENCH_ADMIN_OVERRIDE_ENABLED``), and the caller must
        actually be an admin. The state machine itself would reject a
        non-admin via ``ADMIN_ONLY`` anyway, but failing here gives a
        message that explains *why*, rather than a generic
        "wrong capability".
        """
        if action not in (Action.ADMIN_OVERRIDE_APPROVE, Action.ADMIN_OVERRIDE_REJECT):
            raise DomainValidationError(f"not an admin override action: {action.value!r}")
        if not self._admin_override_enabled:
            raise PermissionDenied(
                "admin override is disabled on this deployment "
                "(set PLANBENCH_ADMIN_OVERRIDE_ENABLED=true to allow it)"
            )
        if not user.is_admin:
            raise PermissionDenied("admin override requires the admin flag")
        # capabilities() will independently compute ADMIN from
        # user.is_admin, which is exactly what ADMIN_ONLY requires — no
        # need to override it here.
        return self.transition(benchmark_id, action, user, comment=comment)

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
        try:
            next_state(stored.state, Action.RUN, self.capabilities(stored, user, Action.RUN))
        except TransitionError as exc:
            # Same ordering guarantee as run(): PermissionDenied from
            # next_state above always wins over this enrichment.
            if stored.state in SELF_APPROVABLE:
                raise TransitionError(_approval_needed_message(stored.state)) from exc
            raise

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
