"""SQL repositories, exercised against SQLite.

The point of these tests is **equivalence**: the SQL backend must be
indistinguishable from the in-memory one to everything above it. Most
cases therefore run against both backends via the same fixture and
assert the same thing, so a divergence fails rather than lurking until
someone deploys with a database.

What SQLite does *not* prove: PostgreSQL-specific behaviour (JSONB
operators, concurrent transactions, real connection pooling). Those need
a live PostgreSQL, which this environment has no way to start — see
docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import pytest
from payloads import bordered_map_payload, scenario_payload

from planbench_api.accounts import AccountLinkError, AuthProvider, NicknameError
from planbench_api.approval import Action, ApprovalRecord, BenchmarkState, Role
from planbench_api.artifacts import FileSystemArtifactStore
from planbench_api.db import SessionFactory, SqlRepositoryHub, create_all, create_db_engine
from planbench_api.db.session import DatabaseUnavailable, normalise_url
from planbench_api.errors import NotFoundError
from planbench_api.repositories import RepositoryHub
from planbench_api.repository_ports import (
    BenchmarkRepositoryPort,
    EpisodeRepositoryPort,
    MapRepositoryPort,
    ReviewRepositoryPort,
    ScenarioRepositoryPort,
    SimulationRepositoryPort,
    UserRepositoryPort,
)
from planbench_api.review import ReviewRequest, ReviewStage, ReviewStatus
from planbench_benchmark import AlgorithmSpec, BenchmarkSpec, RunRecord
from planbench_metrics import EpisodeMetrics
from planbench_planning import PlanResult
from planbench_schemas.episode import EpisodeResult, EpisodeStatus, TrajectoryPoint
from planbench_schemas.map import MapData
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun


@pytest.fixture
def sql_hub(tmp_path) -> SqlRepositoryHub:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'planbench.db'}")
    create_all(engine)
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    return SqlRepositoryHub(SessionFactory(engine), artifacts)


@pytest.fixture
def memory_hub(tmp_path) -> RepositoryHub:
    return RepositoryHub(FileSystemArtifactStore(tmp_path / "artifacts-memory"))


@pytest.fixture(params=["sql", "memory"])
def hub(request, sql_hub, memory_hub):
    """Both backends behind one fixture, so equivalence is the default."""
    return sql_hub if request.param == "sql" else memory_hub


def make_map(name: str = "sql-test-map") -> MapData:
    return MapData.model_validate(bordered_map_payload(name=name))


def make_scenario(name: str = "sql-test-scenario") -> Scenario:
    return Scenario.model_validate(scenario_payload(name=name))


def make_run(algorithm: str = "astar+dwa", status: EpisodeStatus = EpisodeStatus.SUCCESS):
    trajectory = tuple(
        TrajectoryPoint(
            time=index * 0.1,
            x=float(index),
            y=1.0,
            theta=0.0,
            linear_velocity=1.0,
            angular_velocity=0.0,
        )
        for index in range(4)
    )
    result = EpisodeResult(
        status=status,
        reason="goal reached",
        elapsed_time=0.3,
        steps=len(trajectory),
        trajectory=trajectory,
        events=(),
    )
    metrics = EpisodeMetrics(
        status=status,
        success=status is EpisodeStatus.SUCCESS,
        collision=False,
        travel_time=0.3,
        steps=len(trajectory),
        trajectory_length=3.0,
        average_speed=1.0,
        max_speed=1.0,
        smoothness=0.017,
        min_clearance=0.4,
    )
    plan = PlanResult(
        success=True,
        path=(),
        path_length=3.0,
        cost=3.0,
        planning_time_seconds=0.01,
        expanded_nodes=12,
        failure_reason="",
    )
    return StackRun(algorithm=algorithm, plan=plan, result=result, metrics=metrics)


def make_record(algorithm: str = "astar+dwa", seed: int = 1, index: int = 0) -> RunRecord:
    run = make_run(algorithm)
    return RunRecord(
        algorithm=algorithm,
        seed=seed,
        status=run.result.status,
        reason=run.result.reason,
        metrics=run.metrics,
        trajectory_points=len(run.result.trajectory),
        episode_index=index,
    )


class TestPorts:
    def test_both_backends_satisfy_the_ports(self, sql_hub, memory_hub):
        for backend in (sql_hub, memory_hub):
            assert isinstance(backend.maps, MapRepositoryPort)
            assert isinstance(backend.scenarios, ScenarioRepositoryPort)
            assert isinstance(backend.simulations, SimulationRepositoryPort)
            assert isinstance(backend.episodes, EpisodeRepositoryPort)
            assert isinstance(backend.benchmarks, BenchmarkRepositoryPort)
            assert isinstance(backend.users, UserRepositoryPort)
            assert isinstance(backend.reviews, ReviewRepositoryPort)


class TestMaps:
    def test_round_trips_the_whole_map(self, hub):
        original = make_map()
        stored = hub.maps.create(original)
        assert hub.maps.get(stored.id).map_data == original

    def test_cells_survive_exactly(self, hub):
        # A single flipped cell changes the checksum and would break
        # every fairness comparison built on this map.
        original = make_map()
        stored = hub.maps.get(hub.maps.create(original).id)
        assert stored.map_data.cells == original.cells
        assert stored.map_data.checksum() == original.checksum()

    def test_update_bumps_the_version_and_keeps_created_at(self, hub):
        stored = hub.maps.create(make_map())
        updated = hub.maps.update(stored.id, make_map(name="renamed"))
        assert updated.version == 2
        assert updated.created_at == stored.created_at
        assert updated.map_data.name == "renamed"

    def test_missing_map_raises_not_found(self, hub):
        with pytest.raises(NotFoundError):
            hub.maps.get("does-not-exist")

    def test_delete_removes_it(self, hub):
        stored = hub.maps.create(make_map())
        hub.maps.delete(stored.id)
        with pytest.raises(NotFoundError):
            hub.maps.get(stored.id)

    def test_deleting_twice_raises(self, hub):
        stored = hub.maps.create(make_map())
        hub.maps.delete(stored.id)
        with pytest.raises(NotFoundError):
            hub.maps.delete(stored.id)

    def test_list_is_ordered_by_creation(self, hub):
        ids = [hub.maps.create(make_map(name=f"map-{index}")).id for index in range(3)]
        assert [stored.id for stored in hub.maps.list()] == ids


class TestScenarios:
    def test_round_trips(self, hub):
        original = make_scenario()
        stored = hub.scenarios.create("map-1", original)
        assert hub.scenarios.get(stored.id).scenario == original

    def test_survives_its_map_being_deleted(self, hub):
        # Deleting a map must not erase the provenance of benchmarks that
        # already ran against it.
        stored_map = hub.maps.create(make_map())
        stored = hub.scenarios.create(stored_map.id, make_scenario())
        hub.maps.delete(stored_map.id)
        assert hub.scenarios.get(stored.id).map_id == stored_map.id

    def test_update_bumps_the_version(self, hub):
        stored = hub.scenarios.create("map-1", make_scenario())
        updated = hub.scenarios.update(stored.id, "map-2", make_scenario(name="v2"))
        assert (updated.version, updated.map_id, updated.scenario.name) == (2, "map-2", "v2")

    def test_missing_scenario_raises(self, hub):
        with pytest.raises(NotFoundError):
            hub.scenarios.get("nope")


class TestSimulations:
    def test_starts_created_then_finishes(self, hub):
        stored = hub.simulations.create("map-1", "scenario-1", "astar+dwa", {"a": 1})
        assert stored.state == "created" and stored.run is None

        run = make_run()
        finished = hub.simulations.set_finished(stored.id, run)
        assert finished.state == "finished"
        assert finished.run is not None
        assert finished.run.result.status is EpisodeStatus.SUCCESS

    def test_run_survives_a_reload(self, hub):
        stored = hub.simulations.create("map-1", "scenario-1", "astar+dwa", {})
        hub.simulations.set_finished(stored.id, make_run())
        reloaded = hub.simulations.get(stored.id)
        assert reloaded.run is not None
        assert len(reloaded.run.result.trajectory) == 4
        assert reloaded.run.metrics.trajectory_length == 3.0

    def test_config_round_trips(self, hub):
        stored = hub.simulations.create("m", "s", "astar+dwa", {"weight_goal": 2.0, "on": True})
        assert hub.simulations.get(stored.id).config == {"weight_goal": 2.0, "on": True}


class TestBenchmarks:
    def spec(self) -> BenchmarkSpec:
        return BenchmarkSpec(
            name="sql benchmark",
            algorithms=(AlgorithmSpec(id="astar+dwa"),),
            seeds=(1, 2),
        )

    def test_created_in_draft(self, hub):
        stored = hub.benchmarks.create(self.spec(), "map-1", "scenario-1", "op-alice")
        assert stored.state is BenchmarkState.DRAFT
        assert stored.approvals == []
        assert stored.spec.seeds == (1, 2)

    def test_state_transitions_persist(self, hub):
        stored = hub.benchmarks.create(self.spec(), "map-1", "scenario-1", "op-alice")
        hub.benchmarks.set_state(stored.id, BenchmarkState.PENDING_APPROVAL)
        assert hub.benchmarks.get(stored.id).state is BenchmarkState.PENDING_APPROVAL

    def test_running_records_a_start_time(self, hub):
        stored = hub.benchmarks.create(self.spec(), "map-1", "scenario-1", "op-alice")
        assert stored.started_at is None
        hub.benchmarks.set_state(stored.id, BenchmarkState.RUNNING)
        assert hub.benchmarks.get(stored.id).started_at is not None

    def test_approvals_accumulate_in_order(self, hub):
        # The audit trail is the deliverable here: order, content and the
        # identity of the actor all have to survive a reload.
        stored = hub.benchmarks.create(
            self.spec(), "map-1", "scenario-1", "alice", owner_user_id="user-alice"
        )
        steps = [
            (
                Action.SUBMIT,
                BenchmarkState.DRAFT,
                BenchmarkState.PENDING_APPROVAL,
                "alice",
                "user-alice",
                None,
            ),
            (
                Action.APPROVE,
                BenchmarkState.PENDING_APPROVAL,
                BenchmarkState.APPROVED,
                "bob",
                "user-bob",
                "request-1",
            ),
        ]
        for index, (action, previous, new, user, user_id, request_id) in enumerate(steps):
            hub.benchmarks.set_state(
                stored.id,
                new,
                ApprovalRecord(
                    benchmark_id=stored.id,
                    user=user,
                    user_id=user_id,
                    review_request_id=request_id,
                    role=Role.MEMBER,
                    action=action,
                    previous_state=previous,
                    new_state=new,
                    comment=f"step {index}",
                    timestamp=f"2026-07-30T00:0{index}:00+00:00",
                ),
            )
        reloaded = hub.benchmarks.get(stored.id)
        assert [record.action for record in reloaded.approvals] == [Action.SUBMIT, Action.APPROVE]
        assert [record.user for record in reloaded.approvals] == ["alice", "bob"]
        assert [record.user_id for record in reloaded.approvals] == ["user-alice", "user-bob"]
        assert [record.review_request_id for record in reloaded.approvals] == [None, "request-1"]
        assert [record.comment for record in reloaded.approvals] == ["step 0", "step 1"]
        assert reloaded.owner_user_id == "user-alice"

    def test_report_is_stored_with_its_artifact(self, hub, benchmark_report):
        stored = hub.benchmarks.create(self.spec(), "map-1", "scenario-1", "op-alice")
        updated = hub.benchmarks.set_report(stored.id, benchmark_report)
        assert updated.report_artifact_uri
        assert updated.finished_at is not None

        reloaded = hub.benchmarks.get(stored.id)
        assert reloaded.report is not None
        assert (
            reloaded.report.fairness.conditions_checksum
            == benchmark_report.fairness.conditions_checksum
        )

    def test_missing_benchmark_raises(self, hub):
        with pytest.raises(NotFoundError):
            hub.benchmarks.get("nope")


@pytest.fixture
def benchmark_report():
    from planbench_benchmark import AlgorithmAggregate, BenchmarkReport, FairnessRecord

    map_data, scenario = make_map(), make_scenario()
    return BenchmarkReport(
        spec=BenchmarkSpec(
            name="sql benchmark", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1, 2)
        ),
        fairness=FairnessRecord.build(map_data, scenario, (1, 2)),
        runs=(make_record(),),
        aggregates=(
            AlgorithmAggregate(
                algorithm="astar+dwa",
                episodes=2,
                success_rate=1.0,
                collision_rate=0.0,
                timeout_rate=0.0,
                stuck_rate=0.0,
                no_progress_rate=0.0,
                no_global_path_rate=0.0,
                mean_travel_time_successful=0.3,
            ),
        ),
    )


def owning_benchmark(hub, name: str = "owner") -> str:
    """An episode belongs to a benchmark, and SQL enforces that.

    The foreign key means a benchmark id has to exist before episodes
    can reference it — a constraint the in-memory backend cannot express.
    Creating the parent here keeps both backends on the same path.
    """
    spec = BenchmarkSpec(name=name, algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1, 2))
    return hub.benchmarks.create(spec, "map-1", "scenario-1", "op-alice").id


class TestEpisodes:
    def test_metadata_in_the_row_trajectory_in_the_artifact(self, sql_hub):
        # Decision D15 made observable: the row carries a URI, checksum
        # and size, and the trajectory is read back from storage.
        benchmark_id = owning_benchmark(sql_hub)
        stored = sql_hub.episodes.create(benchmark_id, "astar+dwa", 1, make_run(), make_record())
        assert stored.artifact_uri.startswith("file://")
        assert len(stored.artifact_checksum) == 64
        assert stored.artifact_bytes > 0

        reloaded = sql_hub.episodes.get(stored.id)
        assert len(reloaded.run.result.trajectory) == 4
        assert reloaded.run.plan.expanded_nodes == 12

    def test_round_trips_through_both_backends(self, hub):
        benchmark_id = owning_benchmark(hub)
        stored = hub.episodes.create(benchmark_id, "astar+dwa", 3, make_run(), make_record(seed=3))
        reloaded = hub.episodes.get(stored.id)
        assert reloaded.seed == 3
        assert reloaded.record.metrics.min_clearance == 0.4
        assert reloaded.run.result.status is EpisodeStatus.SUCCESS

    def test_listed_in_episode_index_order(self, hub):
        benchmark_id = owning_benchmark(hub)
        # Deliberately inserted out of order.
        for index in (2, 0, 1):
            hub.episodes.create(
                benchmark_id, "astar+dwa", index, make_run(), make_record(seed=index, index=index)
            )
        listed = hub.episodes.list_for_benchmark(benchmark_id)
        assert [episode.record.episode_index for episode in listed] == [0, 1, 2]

    def test_episodes_of_other_benchmarks_are_excluded(self, hub):
        first, second = owning_benchmark(hub, "first"), owning_benchmark(hub, "second")
        hub.episodes.create(first, "astar+dwa", 1, make_run(), make_record())
        hub.episodes.create(second, "astar+dwa", 1, make_run(), make_record())
        assert len(hub.episodes.list_for_benchmark(first)) == 1

    def test_sql_rejects_an_episode_with_no_benchmark(self, sql_hub):
        # The in-memory backend cannot express this, so the assertion is
        # SQL-only: an orphan episode is unreachable through the API and
        # would quietly bloat storage.
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            sql_hub.episodes.create("no-such-benchmark", "astar+dwa", 1, make_run(), make_record())

    def test_a_lost_artifact_is_reported_against_its_episode(self, sql_hub, tmp_path):
        # "File not found" alone would send the reader hunting through
        # the whole artifact tree.
        benchmark_id = owning_benchmark(sql_hub)
        stored = sql_hub.episodes.create(benchmark_id, "astar+dwa", 1, make_run(), make_record())
        path = (
            tmp_path / "artifacts" / "benchmarks" / benchmark_id / "episodes" / f"{stored.id}.json"
        )
        path.unlink()
        with pytest.raises(NotFoundError) as exc:
            sql_hub.episodes.get(stored.id)
        assert stored.id in str(exc.value)

    def test_missing_episode_raises(self, hub):
        with pytest.raises(NotFoundError):
            hub.episodes.get("nope")


class TestUrlHandling:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            # Managed providers hand out postgres:// URLs, which
            # SQLAlchemy rejects outright.
            ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
            ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
            ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
            ("sqlite:///./local.db", "sqlite:///./local.db"),
        ],
    )
    def test_normalises_the_url(self, given, expected):
        assert normalise_url(given) == expected

    def test_missing_driver_says_how_to_install_it(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fail_psycopg(name, *args, **kwargs):
            if name == "psycopg":
                raise ImportError("no psycopg")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fail_psycopg)
        with pytest.raises(DatabaseUnavailable, match="psycopg"):
            create_db_engine("postgresql://u:p@localhost/db")


class TestTransactions:
    def test_a_failed_write_leaves_nothing_behind(self, sql_hub):
        # set_report on a missing benchmark must not leave a partial row
        # or a dangling session.
        before = len(sql_hub.benchmarks.list())
        with pytest.raises(NotFoundError):
            sql_hub.benchmarks.set_state("nope", BenchmarkState.APPROVED)
        assert len(sql_hub.benchmarks.list()) == before

    def test_data_survives_a_new_hub_on_the_same_file(self, tmp_path):
        # The actual promise of persistence: a restart keeps the data.
        url = f"sqlite:///{tmp_path / 'restart.db'}"
        engine = create_db_engine(url)
        create_all(engine)
        artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
        first = SqlRepositoryHub(SessionFactory(engine), artifacts)
        map_id = first.maps.create(make_map()).id
        first.sessions.dispose()

        second = SqlRepositoryHub(SessionFactory(create_db_engine(url)), artifacts)
        assert second.maps.get(map_id).map_data.name == "sql-test-map"


class TestUserRepositories:
    """Accounts, across both backends.

    Nickname uniqueness is the one that has to be identical: the
    in-memory backend enforces it with a dict, SQL with a unique index on
    a case-folded column, and a difference between them would show up as
    "review requests go to the wrong person" only in production.
    """

    def test_round_trips_an_account(self, hub):
        created = hub.users.create(
            nickname="Alice", email="alice@example.com", display_name="Alice A"
        )
        loaded = hub.users.get(created.id)
        assert loaded.nickname == "Alice"  # capitalisation preserved
        assert loaded.email == "alice@example.com"
        assert loaded.is_admin is False

    def test_nicknames_are_unique_case_insensitively(self, hub):
        hub.users.create(nickname="Alice")
        with pytest.raises(NicknameError, match="already taken"):
            hub.users.create(nickname="alice")

    def test_lookup_is_case_insensitive(self, hub):
        created = hub.users.create(nickname="Alice")
        for spelling in ("alice", "ALICE", "AlIcE"):
            assert hub.users.find_by_nickname(spelling).id == created.id

    def test_an_account_can_exist_before_it_has_a_nickname(self, hub):
        """OAuth creates the account first; onboarding names it."""
        first = hub.users.create(email="a@example.com")
        second = hub.users.create(email="b@example.com")
        assert first.needs_nickname and second.needs_nickname
        # Two nameless accounts must not collide on the unique index.
        assert {first.id, second.id} == {user.id for user in hub.users.list()}

    def test_renaming_frees_the_old_nickname(self, hub):
        user = hub.users.create(nickname="alice")
        hub.users.set_nickname(user.id, "alicia")
        assert hub.users.find_by_nickname("alice") is None
        assert hub.users.find_by_nickname("alicia").id == user.id
        # And the freed name can be taken by somebody else.
        other = hub.users.create(nickname="alice")
        assert other.id != user.id

    def test_taking_somebody_elses_nickname_is_refused(self, hub):
        hub.users.create(nickname="alice")
        bob = hub.users.create(nickname="bob")
        with pytest.raises(NicknameError):
            hub.users.set_nickname(bob.id, "ALICE")

    def test_search_matches_a_prefix_only(self, hub):
        hub.users.create(nickname="alice")
        hub.users.create(nickname="alicia")
        hub.users.create(nickname="bob")
        assert [user.nickname for user in hub.users.search_by_nickname("ali")] == [
            "alice",
            "alicia",
        ]
        # Not a substring search: "lic" must not enumerate the members.
        assert hub.users.search_by_nickname("lic") == []

    def test_oauth_identities_are_unique_per_provider(self, hub):
        alice = hub.users.create(nickname="alice")
        bob = hub.users.create(nickname="bob")
        hub.users.link_oauth(
            user_id=alice.id,
            provider=AuthProvider.GOOGLE,
            provider_account_id="google-1",
            provider_email="alice@example.com",
        )
        with pytest.raises(AccountLinkError, match="already linked"):
            hub.users.link_oauth(
                user_id=bob.id, provider=AuthProvider.GOOGLE, provider_account_id="google-1"
            )

    def test_the_same_account_id_at_two_providers_is_two_identities(self, hub):
        alice = hub.users.create(nickname="alice")
        hub.users.link_oauth(
            user_id=alice.id, provider=AuthProvider.GOOGLE, provider_account_id="1"
        )
        hub.users.link_oauth(
            user_id=alice.id, provider=AuthProvider.GITHUB, provider_account_id="1"
        )
        assert {account.provider for account in hub.users.list_oauth(alice.id)} == {
            AuthProvider.GOOGLE,
            AuthProvider.GITHUB,
        }

    def test_relinking_the_same_identity_updates_rather_than_duplicates(self, hub):
        alice = hub.users.create(nickname="alice")
        for email in ("old@example.com", "new@example.com"):
            hub.users.link_oauth(
                user_id=alice.id,
                provider=AuthProvider.GOOGLE,
                provider_account_id="google-1",
                provider_email=email,
            )
        accounts = hub.users.list_oauth(alice.id)
        assert len(accounts) == 1
        assert accounts[0].provider_email == "new@example.com"

    def test_admin_can_be_granted_and_revoked(self, hub):
        user = hub.users.create(nickname="dave")
        assert hub.users.set_admin(user.id, True).is_admin is True
        assert hub.users.get(user.id).is_admin is True
        assert hub.users.set_admin(user.id, False).is_admin is False

    def test_password_hashes_are_not_on_the_public_user(self, hub):
        user = hub.users.create(nickname="alice", password_hash="not-a-real-hash")
        assert not hasattr(hub.users.get(user.id), "password_hash")
        assert hub.users.get_stored(user.id).password_hash == "not-a-real-hash"

    def test_missing_user_raises(self, hub):
        with pytest.raises(NotFoundError):
            hub.users.get("nope")


class TestReviewRepositories:
    def make_request(self, hub, benchmark_id: str, **kw) -> ReviewRequest:
        defaults = {
            "id": "",
            "benchmark_id": benchmark_id,
            "stage": ReviewStage.SPEC,
            "requested_by_user_id": "user-alice",
            "reviewer_user_id": "user-bob",
            "created_at": "2026-07-30T00:00:00+00:00",
        }
        return hub.reviews.create(ReviewRequest(**{**defaults, **kw}))

    @pytest.fixture
    def benchmark_id(self, hub) -> str:
        spec = BenchmarkSpec(
            name="reviewed", algorithms=(AlgorithmSpec(id="astar+dwa"),), seeds=(1,)
        )
        return hub.benchmarks.create(spec, "map-1", "scenario-1", "alice").id

    def test_round_trips(self, hub, benchmark_id):
        created = self.make_request(hub, benchmark_id, request_comment="fair?")
        loaded = hub.reviews.get(created.id)
        assert loaded.status is ReviewStatus.PENDING
        assert loaded.request_comment == "fair?"
        assert loaded.reviewed_at is None

    def test_answering_stamps_the_time_and_survives_a_reload(self, hub, benchmark_id):
        created = self.make_request(hub, benchmark_id)
        hub.reviews.save(created.answered(ReviewStatus.APPROVED, "looks fine"))
        loaded = hub.reviews.get(created.id)
        assert loaded.status is ReviewStatus.APPROVED
        assert loaded.review_comment == "looks fine"
        assert loaded.reviewed_at
        assert loaded.cancelled_at is None

    def test_cancelling_stamps_cancelled_at_not_reviewed_at(self, hub, benchmark_id):
        created = self.make_request(hub, benchmark_id)
        hub.reviews.save(created.answered(ReviewStatus.CANCELLED))
        loaded = hub.reviews.get(created.id)
        assert loaded.cancelled_at and loaded.reviewed_at is None

    def test_the_inbox_filters_by_reviewer_and_status(self, hub, benchmark_id):
        mine = self.make_request(hub, benchmark_id, reviewer_user_id="user-bob")
        self.make_request(
            hub, benchmark_id, stage=ReviewStage.RESULT, reviewer_user_id="user-carol"
        )
        answered = self.make_request(
            hub, benchmark_id, stage=ReviewStage.RESULT, reviewer_user_id="user-bob"
        )
        hub.reviews.save(answered.answered(ReviewStatus.APPROVED))

        assert {r.id for r in hub.reviews.list_for_reviewer("user-bob")} == {mine.id, answered.id}
        assert [r.id for r in hub.reviews.list_for_reviewer("user-bob", ReviewStatus.PENDING)] == [
            mine.id
        ]

    def test_sent_lists_only_my_requests(self, hub, benchmark_id):
        mine = self.make_request(hub, benchmark_id, requested_by_user_id="user-alice")
        self.make_request(
            hub, benchmark_id, stage=ReviewStage.RESULT, requested_by_user_id="user-zoe"
        )
        assert [r.id for r in hub.reviews.list_requested_by("user-alice")] == [mine.id]

    def test_missing_request_raises(self, hub):
        with pytest.raises(NotFoundError):
            hub.reviews.get("nope")
