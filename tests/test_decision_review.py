"""Two human acts on a decision run, kept apart (HĐ-14, phase 6.3).

The shape under test is the one thing about approval that is easy to get
wrong and expensive to fix later: **one flag would have been shorter and
would have meant two different things.**

Four of the first five comparisons this project ran produced no Decision
Card. With a single ``approved`` column, those rows force a choice and
both answers are bad — either they can be approved, in which case
"approved" means "somebody read the gate table" here and "this is the
config we deploy" there, or they cannot be touched at all, and a run that
eliminated four candidates has nowhere to record that anybody looked. So:
``review_state`` for every run, ``config_state`` only where a card
exists.

Both repository implementations run through the same assertions.
Duplicated logic is the price of having an in-memory hub and a SQL one;
duplicated logic that *disagrees* would be the bug, and the only way to
know is to ask both the same questions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from planbench_api.db.decision_repositories import (
    SqlDecisionRunRepository,
    SqlTaskProfileRepository,
)
from planbench_api.db.models import Base
from planbench_api.db.session import SessionFactory
from planbench_api.decisions import DecisionRunRepository, StoredDecisionRun
from planbench_api.errors import InvalidStateError, NotFoundError

CARD = {
    "recommended": {"candidate_id": "cand_winner", "stack": "rrtstar+dwa", "params_ref": None},
    "status": "CLEAR_RECOMMENDATION",
    "decision_utility": 0.852213,
    "evidence": {"delta_u_vs_second": 0.032081, "ci95": [0.03179, 0.037033], "n_episodes": 30},
    "pareto_label": "PARETO_FRONTIER",
    "manifest_ref": "manifest.json",
}


def make_run(
    run_id: str, *, card: dict | None, created_by: str | None = "alice"
) -> StoredDecisionRun:
    return StoredDecisionRun(
        id=run_id,
        task_profile_id="open_hall_v2",
        artifact_kind="decision_card" if card else "comparison",
        experiment_scope="local_controller_selection",
        contracts_version="6.5.0",
        created_at="2026-08-12T00:00:00+00:00",
        created_by=created_by,
        report={"artifact": "comparison_report"},
        card=card,
    )


@pytest.fixture(params=["memory", "sql"])
def repository(request, tmp_path: Path):
    """The same repository contract, both ways it is implemented."""
    if request.param == "memory":
        return DecisionRunRepository()
    sessions = SessionFactory(create_engine(f"sqlite:///{tmp_path / 'runs.db'}"))
    Base.metadata.create_all(sessions.engine)
    # The FK on decision_runs is real, so the deployment has to exist.
    SqlTaskProfileRepository(sessions).create({"id": "open_hall_v2", "environment": {}})
    return SqlDecisionRunRepository(sessions)


class TestTheStartingStates:
    def test_an_unranked_run_is_not_applicable_for_config_approval(self, repository) -> None:
        """The refusal is a *state*, not a check.

        Expressing it as a value means a second caller cannot forget it,
        and there is no path from ``not_applicable`` to ``approved``.
        """
        stored = repository.create(make_run("r1", card=None))
        assert stored.config_state == "not_applicable"
        assert stored.review_state == "unreviewed"

    def test_a_ranked_run_starts_pending(self, repository) -> None:
        stored = repository.create(make_run("r2", card=CARD))
        assert stored.config_state == "pending"
        assert stored.review_state == "unreviewed"

    def test_the_promotion_happens_in_the_dataclass_not_the_caller(self) -> None:
        """A caller that forgets ``config_state`` still gets it right —
        and, more to the point, a caller that *passes* the permissive
        value for a cardless run does not get to keep it."""
        assert make_run("r3", card=CARD).config_state == "pending"
        assert make_run("r4", card=None).config_state == "not_applicable"


class TestReviewingAppliesToEveryRun:
    def test_a_run_with_no_card_can_still_be_read(self, repository) -> None:
        """The property this whole split exists for. A comparison that
        eliminated everybody is a result somebody has to read, and
        without this it is the artifact nobody ever looked at again."""
        repository.create(make_run("r1", card=None))
        stored = repository.review("r1", actor_user_id="bob", username="bob", comment="đọc rồi")

        assert stored.review_state == "reviewed"
        assert stored.reviewed_by == "bob"
        assert stored.reviewed_at

    def test_the_person_who_ran_it_may_read_it(self, repository) -> None:
        """Reviewing claims you looked, not that you endorse — so the
        separation-of-duties bar that applies to approval does not apply
        here. Requiring a second pair of eyes to *read* would leave most
        runs unread, which is the failure mode, not the guard."""
        repository.create(make_run("r1", card=None, created_by="alice"))
        assert (
            repository.review(
                "r1", actor_user_id="alice", username="alice", comment=""
            ).review_state
            == "reviewed"
        )

    def test_reviewing_twice_is_refused_rather_than_re_stamped(self, repository) -> None:
        """The second name would overwrite the first, and the audit trail
        would then disagree with the row it describes."""
        repository.create(make_run("r1", card=None))
        repository.review("r1", actor_user_id="bob", username="bob", comment="")

        with pytest.raises(InvalidStateError, match="already reviewed"):
            repository.review("r1", actor_user_id="carol", username="carol", comment="")

    def test_reviewing_leaves_config_state_alone(self, repository) -> None:
        """Two acts, two columns. Reading a run does not deploy it."""
        repository.create(make_run("r1", card=CARD))
        stored = repository.review("r1", actor_user_id="bob", username="bob", comment="")
        assert stored.config_state == "pending"


class TestApprovingAConfigurationNeedsSomethingToApprove:
    def test_a_run_with_no_card_cannot_be_approved(self, repository) -> None:
        """Otherwise ``approved_config.yaml`` would name nobody, and
        "this was measured" would have become "this was endorsed"."""
        repository.create(make_run("r1", card=None))
        with pytest.raises(InvalidStateError, match="no Decision Card"):
            repository.decide_config(
                "r1", approve=True, actor_user_id="bob", username="bob", comment=""
            )

    def test_the_refusal_points_at_what_the_caller_can_do_instead(self, repository) -> None:
        """A refusal a reader cannot act on gets worked around."""
        repository.create(make_run("r1", card=None))
        with pytest.raises(InvalidStateError, match="review"):
            repository.decide_config(
                "r1", approve=True, actor_user_id="bob", username="bob", comment=""
            )

    def test_nobody_approves_their_own_run(self, repository) -> None:
        """HĐ-14. Whoever chose the candidates, the deployment and the
        episode count is not an independent check on the answer."""
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        with pytest.raises(InvalidStateError, match="own recommendation"):
            repository.decide_config(
                "r1", approve=True, actor_user_id="alice", username="alice", comment=""
            )

    def test_somebody_else_can(self, repository) -> None:
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        stored = repository.decide_config(
            "r1", approve=True, actor_user_id="bob", username="bob", comment="ok"
        )
        assert stored.config_state == "approved"
        assert stored.config_decided_by == "bob"
        assert stored.config_decided_at

    def test_rejecting_is_recorded_the_same_way(self, repository) -> None:
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        stored = repository.decide_config(
            "r1", approve=False, actor_user_id="bob", username="bob", comment="chưa đủ n"
        )
        assert stored.config_state == "rejected"

    @pytest.mark.parametrize("first", [True, False])
    def test_a_decision_is_not_re_decidable(self, repository, first: bool) -> None:
        """Both terminal, in both directions.

        Re-deciding would let a rejection be quietly flipped after the
        fact. The legitimate answer to "we were wrong" is a new run — it
        is cheap, it is dated, and it leaves both records standing.
        """
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        repository.decide_config(
            "r1", approve=first, actor_user_id="bob", username="bob", comment=""
        )
        with pytest.raises(InvalidStateError, match="already"):
            repository.decide_config(
                "r1", approve=not first, actor_user_id="carol", username="carol", comment=""
            )

    def test_approving_leaves_review_state_alone(self, repository) -> None:
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        stored = repository.decide_config(
            "r1", approve=True, actor_user_id="bob", username="bob", comment=""
        )
        assert stored.review_state == "unreviewed"


class TestTheAuditTrail:
    def test_nothing_happened_yet_is_an_empty_trail_not_an_error(self, repository) -> None:
        repository.create(make_run("r1", card=None))
        assert repository.events("r1") == []

    def test_every_act_lands_in_order_with_both_ends_of_the_change(self, repository) -> None:
        """``sequence`` rather than the timestamp, because two acts can
        share a clock reading and "who decided first" is exactly what an
        audit trail is asked."""
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        repository.review("r1", actor_user_id="bob", username="bob", comment="đọc")
        repository.decide_config(
            "r1", approve=True, actor_user_id="bob", username="bob", comment="duyệt"
        )

        trail = repository.events("r1")
        assert [event.sequence for event in trail] == [1, 2]
        assert [event.action for event in trail] == ["review", "approve_config"]
        assert (trail[0].previous_state, trail[0].new_state) == ("unreviewed", "reviewed")
        assert (trail[1].previous_state, trail[1].new_state) == ("pending", "approved")
        assert [event.comment for event in trail] == ["đọc", "duyệt"]

    def test_a_refused_act_writes_no_row(self, repository) -> None:
        """An audit trail that records attempts as if they were decisions
        would report an approval that never took effect."""
        repository.create(make_run("r1", card=CARD, created_by="alice"))
        with pytest.raises(InvalidStateError):
            repository.decide_config(
                "r1", approve=True, actor_user_id="alice", username="alice", comment=""
            )
        assert repository.events("r1") == []

    def test_the_name_is_kept_beside_the_id(self, repository) -> None:
        """Ids do not read back; nicknames survive a later rename."""
        repository.create(make_run("r1", card=None))
        repository.review("r1", actor_user_id="u_42", username="bob", comment="")
        event = repository.events("r1")[0]
        assert (event.actor_user_id, event.username) == ("u_42", "bob")


class TestUnknownRuns:
    def test_reviewing_one_that_does_not_exist(self, repository) -> None:
        with pytest.raises(NotFoundError):
            repository.review("nope", actor_user_id="bob", username="bob", comment="")

    def test_deciding_one_that_does_not_exist(self, repository) -> None:
        with pytest.raises(NotFoundError):
            repository.decide_config(
                "nope", approve=True, actor_user_id="bob", username="bob", comment=""
            )

    def test_asking_for_the_trail_of_one_that_does_not_exist(self, repository) -> None:
        with pytest.raises(NotFoundError):
            repository.events("nope")
