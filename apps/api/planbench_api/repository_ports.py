"""The repository contract, independent of where the data actually lives.

Until M10 the only implementation was in-memory. Adding PostgreSQL
without writing these down would have meant the SQL classes "matching"
the dict-backed ones by luck: one renamed argument and the API would
break at runtime in whichever deployment happened to use the other
backend.

These Protocols are structural, so neither implementation has to inherit
anything — the in-memory classes already satisfied them before this file
existed. What the file adds is a single place that says what a
repository *is*, and a type error when an implementation drifts.

Storage split (decision D15) applies to both backends: large payloads —
episode trajectories, benchmark reports — go to the artifact store, and
the repository keeps metadata plus the URI. So a SQL row is small, and
replay reads the artifact rather than a blob column.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from planbench_api.accounts import (
    AccountEvent,
    AuthProvider,
    OAuthAccount,
    Role,
    StoredUser,
    User,
)
from planbench_api.approval import ApprovalRecord, BenchmarkState
from planbench_api.repositories import (
    StoredBenchmark,
    StoredEpisode,
    StoredMap,
    StoredScenario,
    StoredSimulation,
)
from planbench_api.review import ReviewRequest, ReviewStatus
from planbench_benchmark import BenchmarkReport, BenchmarkSpec, RunRecord
from planbench_schemas.map import MapData
from planbench_schemas.replanning import NO_REPLANNING, ReplanningConfig
from planbench_schemas.scenario import Scenario
from planbench_simulator.nav_stack import StackRun


@runtime_checkable
class MapRepositoryPort(Protocol):
    def create(self, map_data: MapData) -> StoredMap: ...
    def get(self, map_id: str) -> StoredMap: ...
    def list(self) -> list[StoredMap]: ...
    def update(self, map_id: str, map_data: MapData) -> StoredMap: ...
    def delete(self, map_id: str) -> None: ...


@runtime_checkable
class ScenarioRepositoryPort(Protocol):
    def create(self, map_id: str, scenario: Scenario) -> StoredScenario: ...
    def get(self, scenario_id: str) -> StoredScenario: ...
    def list(self) -> list[StoredScenario]: ...
    def update(self, scenario_id: str, map_id: str, scenario: Scenario) -> StoredScenario: ...
    def delete(self, scenario_id: str) -> None: ...


@runtime_checkable
class SimulationRepositoryPort(Protocol):
    def create(
        self,
        map_id: str,
        scenario_id: str,
        algorithm: str,
        config: dict,
        replanning: ReplanningConfig = NO_REPLANNING,
    ) -> StoredSimulation: ...
    def get(self, simulation_id: str) -> StoredSimulation: ...
    def list(self) -> list[StoredSimulation]: ...
    def set_finished(self, simulation_id: str, run: StackRun) -> StoredSimulation: ...


@runtime_checkable
class EpisodeRepositoryPort(Protocol):
    def create(
        self, benchmark_id: str, algorithm: str, seed: int, run: StackRun, record: RunRecord
    ) -> StoredEpisode: ...
    def get(self, episode_id: str) -> StoredEpisode: ...
    def list_for_benchmark(self, benchmark_id: str) -> list[StoredEpisode]: ...


@runtime_checkable
class UserRepositoryPort(Protocol):
    """Accounts and the provider identities linked to them.

    OAuth accounts live here rather than in their own repository because
    every operation on them is an operation on a user: no caller ever
    wants an OAuth row on its own.
    """

    def create(
        self,
        *,
        nickname: str = "",
        email: str = "",
        display_name: str = "",
        avatar_url: str = "",
        roles: frozenset[Role] | set[Role] = frozenset(),
        password_hash: str | None = None,
    ) -> User: ...
    def get(self, user_id: str) -> User: ...
    def get_stored(self, user_id: str) -> StoredUser: ...
    def find_by_nickname(self, nickname: str) -> User | None: ...
    def search_by_nickname(self, prefix: str, limit: int = 10) -> list[User]: ...
    def set_nickname(self, user_id: str, nickname: str) -> User: ...
    def update_profile(
        self,
        user_id: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User: ...
    def set_roles(
        self,
        user_id: str,
        roles: frozenset[Role] | set[Role],
        *,
        granted_by_user_id: str | None = None,
        reason: str = "",
    ) -> User: ...
    def set_disabled(self, user_id: str, disabled: bool) -> User: ...
    def record_sign_in(self, user_id: str) -> None: ...
    def list_with_role(self, role: Role) -> list[User]: ...
    def record_account_event(self, event: AccountEvent) -> AccountEvent: ...
    def list_account_events(self, user_id: str | None = None) -> list[AccountEvent]: ...
    def set_password(self, user_id: str, password_hash: str) -> User: ...
    def list(self) -> list[User]: ...
    def link_oauth(
        self,
        *,
        user_id: str,
        provider: AuthProvider,
        provider_account_id: str,
        provider_email: str = "",
    ) -> OAuthAccount: ...
    def find_oauth(
        self, provider: AuthProvider, provider_account_id: str
    ) -> OAuthAccount | None: ...
    def list_oauth(self, user_id: str) -> list[OAuthAccount]: ...


@runtime_checkable
class ReviewRepositoryPort(Protocol):
    def create(self, request: ReviewRequest) -> ReviewRequest: ...
    def get(self, request_id: str) -> ReviewRequest: ...
    def save(self, request: ReviewRequest) -> ReviewRequest: ...
    def list_for_benchmark(self, benchmark_id: str) -> list[ReviewRequest]: ...
    def list_for_reviewer(
        self, reviewer_user_id: str, status: ReviewStatus | None = None
    ) -> list[ReviewRequest]: ...
    def list_requested_by(self, user_id: str) -> list[ReviewRequest]: ...


@runtime_checkable
class BenchmarkRepositoryPort(Protocol):
    def create(
        self,
        spec: BenchmarkSpec,
        map_id: str,
        scenario_id: str,
        created_by: str,
        owner_user_id: str = "",
    ) -> StoredBenchmark: ...
    def get(self, benchmark_id: str) -> StoredBenchmark: ...
    def list(self) -> list[StoredBenchmark]: ...
    def set_state(
        self, benchmark_id: str, state: BenchmarkState, approval: ApprovalRecord | None = None
    ) -> StoredBenchmark: ...
    def set_report(self, benchmark_id: str, report: BenchmarkReport) -> StoredBenchmark: ...


@runtime_checkable
class RepositoryHubPort(Protocol):
    """What the application needs from a storage backend."""

    maps: MapRepositoryPort
    scenarios: ScenarioRepositoryPort
    simulations: SimulationRepositoryPort
    episodes: EpisodeRepositoryPort
    benchmarks: BenchmarkRepositoryPort
    users: UserRepositoryPort
    reviews: ReviewRepositoryPort


__all__ = [
    "BenchmarkRepositoryPort",
    "EpisodeRepositoryPort",
    "MapRepositoryPort",
    "RepositoryHubPort",
    "ReviewRepositoryPort",
    "ScenarioRepositoryPort",
    "SimulationRepositoryPort",
    "UserRepositoryPort",
]
