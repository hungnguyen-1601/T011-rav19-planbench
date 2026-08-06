"""Turning a conversation into a benchmark, safely.

The assistant reads real records and asks for what is missing. It never
writes anything: `propose` returns a message, and only `confirm` — a
separate call a person triggers — creates a draft.

The reply is assembled here rather than left to the model, and that is
deliberate. What the user sees about their *own data* — which scenarios
exist, which models are compatible, what a benchmark actually scored —
is read from storage and rendered, so it cannot be hallucinated. The
language model's job is understanding the request; the numbers are the
platform's.
"""

from __future__ import annotations

import logging
import re

from planbench_api.accounts import User
from planbench_api.chat import (
    BenchmarkProposal,
    ChatMessage,
    ProposalStatus,
    Role,
    conversation_from_row,
    message_from_row,
    title_from,
)
from planbench_api.errors import DomainValidationError, NotFoundError
from planbench_api.model_registry import Compatibility
from planbench_api.repositories import new_id

logger = logging.getLogger("planbench.api.chat")

#: Default when the user says "a few runs" and nothing more precise.
DEFAULT_SEEDS = (1, 2, 3)
MAX_SEEDS = 20

#: How the assistant recognises a stack in ordinary language. Matching
#: on words rather than ids is the point: nobody types "astar+dwa".
STACK_WORDS: dict[str, tuple[str, ...]] = {
    "astar+dwa": ("dwa", "dynamic window", "cửa sổ động"),
    "astar+ppo": ("ppo", "reinforcement", "học tăng cường", "mô hình"),
    "astar+pure_pursuit": ("pure pursuit", "pure-pursuit", "bám đường"),
    # "dwa" alone stays A*+DWA: it is the older, deterministic stack and
    # the one people mean by default. RRT* has to be named to be chosen.
    "rrtstar+dwa": ("rrt", "rrt*", "rrt star", "rrt-star"),
}


def _seeds_in(text: str) -> tuple[int, ...]:
    """Read "3 times", "seeds 1 2 3", "chạy 5 lần" out of a sentence."""
    explicit = re.findall(r"\bseeds?\s*[:=]?\s*((?:\d+[\s,]*)+)", text, flags=re.I)
    if explicit:
        values = [int(value) for value in re.findall(r"\d+", explicit[0])]
        return tuple(dict.fromkeys(values))[:MAX_SEEDS]
    count = re.search(r"(\d+)\s*(?:times|runs|lần|seeds?)", text, flags=re.I)
    if count:
        number = max(1, min(int(count.group(1)), MAX_SEEDS))
        return tuple(range(1, number + 1))
    return ()


def _stacks_in(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    found = [
        stack for stack, words in STACK_WORDS.items() if any(word in lowered for word in words)
    ]
    return tuple(found)


class ChatService:
    """One conversation's worth of state, and the rules around it."""

    def __init__(self, repos, models, profiles, benchmarks) -> None:
        self._repos = repos
        self._models = models
        self._profiles = profiles
        self._benchmarks = benchmarks

    # -- conversations -------------------------------------------------

    def start(self, user: User, locale: str) -> dict:
        return self._repos.conversations.create(user.id, "", locale)

    def list(self, user: User) -> list[dict]:
        return self._repos.conversations.list_for_user(user.id)

    def require_own(self, conversation_id: str, user: User) -> dict:
        conversation = self._repos.conversations.get(conversation_id)
        if conversation["user_id"] != user.id:
            # Same message whoever asks: a conversation id is not a
            # secret, and confirming whose it is helps nobody.
            raise NotFoundError("conversation", conversation_id)
        return conversation

    def history(self, conversation_id: str, user: User) -> list[ChatMessage]:
        self.require_own(conversation_id, user)
        return [
            message_from_row(row) for row in self._repos.conversations.messages(conversation_id)
        ]

    def delete(self, conversation_id: str, user: User) -> None:
        self.require_own(conversation_id, user)
        self._repos.conversations.delete(conversation_id)

    def conversation(self, conversation_id: str, user: User):
        return conversation_from_row(self.require_own(conversation_id, user))

    # -- the turn ------------------------------------------------------

    def reply(self, conversation_id: str, user: User, text: str) -> ChatMessage:
        """Answer one message.

        Everything factual comes from storage. The assistant's job is to
        work out *what* was asked; what it then says about benchmarks,
        models and results is read, not recalled.
        """
        self.require_own(conversation_id, user)
        self._repos.conversations.add_message(conversation_id, Role.USER.value, text)
        self._repos.conversations.touch(conversation_id, title_from(text))

        proposal, content = self._understand(text, user)
        payload = {"proposal": proposal.model_dump(mode="json")} if proposal else None
        row = self._repos.conversations.add_message(
            conversation_id, Role.ASSISTANT.value, content, payload
        )
        self._repos.conversations.touch(conversation_id)
        return message_from_row(row)

    def _understand(self, text: str, user: User) -> tuple[BenchmarkProposal | None, str]:
        lowered = text.lower()
        wants_benchmark = any(
            word in lowered
            for word in ("benchmark", "compare", "so sánh", "kiểm thử", "test", "chạy", "run")
        )
        asks_results = any(
            word in lowered
            for word in ("result", "why", "kết quả", "vì sao", "tại sao", "phân tích", "analyse")
        )

        if asks_results and not wants_benchmark:
            return None, self._explain_latest(user)
        if wants_benchmark:
            return self._build_proposal(text, user)
        return None, self._capabilities_reply()

    # -- proposing -----------------------------------------------------

    def _build_proposal(self, text: str, user: User) -> tuple[BenchmarkProposal, str]:
        """Assemble a proposal from what was said plus what exists.

        Missing pieces become questions, never guesses. The one
        exception is seeds, where "three runs" is a safe default that is
        recorded in `assumptions` so the user sees it was assumed.
        """
        scenarios = self._repos.scenarios.list()
        maps = self._repos.maps.list()
        stacks = _stacks_in(text) or ("astar+dwa",)
        seeds = _seeds_in(text)
        assumptions: list[str] = []
        missing: list[str] = []
        warnings: list[str] = []

        if not seeds:
            seeds = DEFAULT_SEEDS
            assumptions.append(f"{len(DEFAULT_SEEDS)} runs (seeds {', '.join(map(str, seeds))})")

        scenario = self._pick_scenario(text, scenarios)
        if scenario is None:
            missing.append("scenario")

        model_id = ""
        model_label = ""
        profile_id = ""
        if "astar+ppo" in stacks:
            usable = self._models.usable_models()
            picked = self._pick_model(text, usable)
            if picked is None:
                missing.append("ppo_model")
                if not usable:
                    warnings.append("no_models_uploaded")
            else:
                model_id = picked.id
                model_label = picked.label
                profile_id = picked.robot_profile_id
                report = self._models.compatibility(picked.id)
                if report.status is Compatibility.INCOMPATIBLE:
                    warnings.append("model_incompatible")
                    missing.append("ppo_model")

        proposal = BenchmarkProposal(
            id=new_id(),
            name=title_from(text) or "New benchmark",
            map_id=scenario.map_id if scenario else (maps[0].id if maps else ""),
            scenario_id=scenario.id if scenario else "",
            scenario_name=scenario.scenario.name if scenario else "",
            stacks=stacks,
            seeds=seeds,
            robot_profile_id=profile_id,
            model_id=model_id,
            model_label=model_label,
            assumptions=tuple(assumptions),
            missing_fields=tuple(dict.fromkeys(missing)),
            warnings=tuple(warnings),
        )
        return proposal, self._proposal_text(proposal)

    def _pick_scenario(self, text: str, scenarios):
        lowered = text.lower()
        for stored in scenarios:
            if stored.scenario.name.lower() in lowered:
                return stored
        # One scenario in the workspace is not ambiguous; more than one
        # is, and guessing would be inventing a decision the user did
        # not make.
        return scenarios[0] if len(scenarios) == 1 else None

    def _pick_model(self, text: str, models):
        lowered = text.lower()
        for record in models:
            if record.name.lower() in lowered or record.label.lower() in lowered:
                return record
        return models[0] if len(models) == 1 else None

    def _proposal_text(self, proposal: BenchmarkProposal) -> str:
        """A key the client renders in the user's language.

        The assistant does not compose Vietnamese or English prose here:
        it names a situation, and the UI has both translations. That
        keeps the two languages from drifting apart in a place nobody
        would notice.
        """
        if "ppo_model" in proposal.missing_fields:
            return "chat.needModel"
        if "scenario" in proposal.missing_fields:
            return "chat.needScenario"
        return "chat.proposalReady"

    def _capabilities_reply(self) -> str:
        return "chat.help"

    # -- confirming ----------------------------------------------------

    def confirm(self, conversation_id: str, user: User, proposal_id: str) -> ChatMessage:
        """Create the benchmark a proposal describes.

        Deliberately a separate call: a person clicked. Every id in the
        proposal is re-checked against real records here — an assistant
        that invented one produces a validation error, not a benchmark
        pointing at nothing.
        """
        self.require_own(conversation_id, user)
        proposal = self._find_proposal(conversation_id, proposal_id)
        if proposal is None:
            raise NotFoundError("proposal", proposal_id)
        if not proposal.ready:
            raise DomainValidationError(
                "this proposal is not complete yet; answer the assistant's question first",
                list(proposal.missing_fields),
            )

        # Real records or nothing: NotFoundError here is the guard
        # against an id the assistant made up.
        self._repos.maps.get(proposal.map_id)
        self._repos.scenarios.get(proposal.scenario_id)

        algorithms = []
        for stack in proposal.stacks:
            config: dict = {}
            if stack == "astar+ppo":
                record = self._models.get(proposal.model_id)  # 404 if invented
                config = {
                    "model_id": record.id,
                    "model_version": record.version,
                    "robot_profile_id": proposal.robot_profile_id or record.robot_profile_id,
                }
            algorithms.append({"id": stack, "config": config})

        from planbench_benchmark import AlgorithmSpec

        created = self._benchmarks.create(
            name=proposal.name,
            map_id=proposal.map_id,
            scenario_id=proposal.scenario_id,
            algorithms=[AlgorithmSpec(**entry) for entry in algorithms],
            seeds=list(proposal.seeds),
            owner=user,
            description="Prepared with the PlanBench assistant.",
        )

        confirmed = proposal.model_copy(
            # The enum, not the string: a bare "confirmed" round-trips
            # through Pydantic as a plain str and warns on serialisation.
            update={"status": ProposalStatus.CONFIRMED, "benchmark_id": created.id}
        )
        row = self._repos.conversations.add_message(
            conversation_id,
            Role.ASSISTANT.value,
            # The benchmark is a draft. Running it is the user's move,
            # and the message says so rather than implying it started.
            "chat.draftCreated",
            {"proposal": confirmed.model_dump(mode="json")},
        )
        self._repos.conversations.touch(conversation_id)
        logger.info(
            "assistant draft confirmed",
            extra={"context": {"benchmark_id": created.id, "user_id": user.id}},
        )
        return message_from_row(row)

    def _find_proposal(self, conversation_id: str, proposal_id: str) -> BenchmarkProposal | None:
        for row in reversed(self._repos.conversations.messages(conversation_id)):
            payload = row.get("payload") or {}
            candidate = payload.get("proposal")
            if candidate and candidate.get("id") == proposal_id:
                return BenchmarkProposal.model_validate(candidate)
        return None

    # -- explaining ----------------------------------------------------

    def _explain_latest(self, user: User) -> str:
        """Point at the most recent finished benchmark.

        The *numbers* travel as a result card built from the stored
        report, not as prose — so nothing here can misquote them.
        """
        finished = [stored for stored in self._repos.benchmarks.list() if stored.report is not None]
        if not finished:
            return "chat.noResults"
        return "chat.explainLatest"

    def result_card(self, benchmark_id: str) -> dict | None:
        """The figures for one benchmark, read from its stored report."""
        try:
            stored = self._repos.benchmarks.get(benchmark_id)
        except NotFoundError:
            return None
        if stored.report is None:
            return None
        aggregates = [
            {
                "algorithm": aggregate.algorithm,
                "episodes": aggregate.episodes,
                "success_rate": aggregate.success_rate,
                "collision_rate": aggregate.collision_rate,
                "timeout_rate": aggregate.timeout_rate,
                "mean_travel_time": aggregate.mean_travel_time_successful,
                # The median and its interval travel with the mean so a
                # generated summary can quote the robust number; leaving
                # only the mean here would push every written report
                # towards the figure one stalled episode can dominate.
                "median_travel_time": aggregate.median_travel_time_successful,
                "ci95_travel_time": aggregate.ci95_travel_time_successful,
                "ci95_success_rate": aggregate.ci95_success_rate,
                "worst_min_clearance": aggregate.worst_min_clearance,
                "mean_latency": aggregate.mean_local_planning_latency,
            }
            for aggregate in stored.report.aggregates
        ]
        return {
            "benchmark_id": stored.id,
            "name": stored.spec.name,
            "state": stored.state.value,
            "conditions_checksum": stored.report.fairness.conditions_checksum,
            "aggregates": aggregates,
            # Seed adequacy and the paired tests are part of the figures,
            # not a footnote: a card that shows only success rates invites
            # "A beat B" from a five-seed run.
            "seed_count": stored.report.seed_count,
            "statistically_adequate": stored.report.statistically_adequate,
            "comparisons": [
                comparison.model_dump(mode="json") for comparison in stored.report.comparisons
            ],
        }

    def latest_finished_id(self) -> str:
        for stored in sorted(
            self._repos.benchmarks.list(), key=lambda item: item.created_at, reverse=True
        ):
            if stored.report is not None:
                return stored.id
        return ""


__all__ = ["DEFAULT_SEEDS", "STACK_WORDS", "ChatService"]
