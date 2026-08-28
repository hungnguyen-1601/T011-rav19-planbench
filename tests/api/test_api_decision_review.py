"""Claim, acknowledge, decide — and the hole each step closes.

The rule this file exists for is the one that is easiest to get wrong
and hardest to notice: **an acknowledgement belongs to a claim, not to a
run.** Reviewer A can open the evidence, put the review down, and
reviewer B pick it up. If the check were "has anybody read this run?",
B could then sign it without opening anything, and the trail would show
a reading and a signature and look complete.
"""

from __future__ import annotations

import pytest
from conftest import ALICE, BOB, CAROL, ENGINEER, auth_headers
from fastapi.testclient import TestClient
from test_api_decisions import tiny_profile

API = "/api/v1"


@pytest.fixture
def profile_id(client: TestClient, alice_headers: dict[str, str]) -> str:
    response = client.post(f"{API}/task-profiles", json=tiny_profile(), headers=alice_headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def ranked_run(client: TestClient, alice_headers, app, tmp_path) -> dict:
    """A run that recommends somebody, so there is something to sign.

    The vertical slice's deployment, because it is the one both
    candidates clear every gate on — which is what makes a Decision Card
    possible at all. Most comparisons rank nobody, and a fixture that
    produced one of those would leave every signing test below asserting
    the wrong refusal.
    """
    import yaml
    from test_vertical_slice import write_profile

    profile_path = write_profile(tmp_path)
    app.state.decision_map_root = tmp_path
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    created = client.post(f"{API}/task-profiles", json=payload, headers=alice_headers)
    assert created.status_code == 201, created.text

    response = client.post(
        f"{API}/decisions",
        json={
            "task_profile_id": created.json()["id"],
            "candidates": [
                {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
            ],
            "episodes": 6,
        },
        headers=alice_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ranked"] is True, "these tests need something to sign"
    return body


def _submit(client, run_id, headers, reviewer: str = "", comment: str = ""):
    return client.post(
        f"{API}/decisions/{run_id}/submit",
        json={"reviewer": reviewer, "comment": comment},
        headers=headers,
    )


class TestAskingForAReview:
    def test_a_run_with_no_named_reviewer_goes_to_the_pool(
        self, client: TestClient, ranked_run, alice_headers
    ) -> None:
        """Naming somebody is optional, and usually the requester cannot.

        On a deployment with one reviewer it is ceremony; on one with
        several the person asking rarely knows who is free.
        """
        state = _submit(client, ranked_run["id"], alice_headers).json()
        assert state["submission"] == "submitted"
        assert state["available_to_pool"] is True
        assert state["requested_reviewer_user_id"] is None

    def test_a_named_reviewer_is_not_in_the_pool(
        self, client: TestClient, ranked_run, alice_headers
    ) -> None:
        state = _submit(client, ranked_run["id"], alice_headers, reviewer=BOB[0]).json()
        assert state["available_to_pool"] is False
        assert state["requested_reviewer_user_id"]

    def test_only_the_owner_may_send_their_run(
        self, client: TestClient, ranked_run, bob_headers
    ) -> None:
        assert _submit(client, ranked_run["id"], bob_headers).status_code == 403

    def test_an_engineer_without_review_rights_cannot_claim(
        self, client: TestClient, ranked_run, alice_headers
    ) -> None:
        _submit(client, ranked_run["id"], alice_headers)
        refused = client.post(
            f"{API}/decisions/{ranked_run['id']}/claim",
            headers=auth_headers(client, ENGINEER),
        )
        assert refused.status_code == 403

    def test_a_second_request_is_refused_while_one_is_live(
        self, client: TestClient, ranked_run, alice_headers
    ) -> None:
        """So "who is this waiting on?" has one answer."""
        _submit(client, ranked_run["id"], alice_headers)
        again = _submit(client, ranked_run["id"], alice_headers)
        assert again.status_code == 422
        assert "already waiting" in again.json()["error"]["message"]


class TestClaiming:
    def test_claiming_puts_it_in_review(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        _submit(client, ranked_run["id"], alice_headers)
        state = client.post(f"{API}/decisions/{ranked_run['id']}/claim", headers=bob_headers).json()
        assert state["submission"] == "in_review"
        assert state["claimed_by_user_id"]
        assert state["claimed_at"]

    def test_two_reviewers_cannot_both_hold_one_review(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers
    ) -> None:
        """The loser is told, rather than quietly sharing the work."""
        _submit(client, ranked_run["id"], alice_headers)
        assert (
            client.post(
                f"{API}/decisions/{ranked_run['id']}/claim", headers=bob_headers
            ).status_code
            == 200
        )
        second = client.post(f"{API}/decisions/{ranked_run['id']}/claim", headers=carol_headers)
        assert second.status_code == 409
        assert "already reviewing" in second.json()["error"]["message"]

    def test_a_directed_request_is_not_open_to_everybody(
        self, client: TestClient, ranked_run, alice_headers, carol_headers
    ) -> None:
        _submit(client, ranked_run["id"], alice_headers, reviewer=BOB[0])
        refused = client.post(f"{API}/decisions/{ranked_run['id']}/claim", headers=carol_headers)
        assert refused.status_code == 403

    def test_releasing_opens_it_to_the_pool_without_erasing_who_was_asked(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers
    ) -> None:
        """The bug this column exists for.

        A directed request whose reviewer released it used to stay
        addressed to them, so nobody else could pick it up — and the
        person who *was* asked is still part of what the requester said,
        so clearing it is not the fix either.
        """
        _submit(client, ranked_run["id"], alice_headers, reviewer=BOB[0])
        client.post(f"{API}/decisions/{ranked_run['id']}/claim", headers=bob_headers)
        released = client.post(
            f"{API}/decisions/{ranked_run['id']}/release", headers=bob_headers
        ).json()
        assert released["available_to_pool"] is True
        assert released["requested_reviewer_user_id"], "who was asked is part of the record"
        assert (
            client.post(
                f"{API}/decisions/{ranked_run['id']}/claim", headers=carol_headers
            ).status_code
            == 200
        )

    def test_taking_over_needs_a_reason(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers
    ) -> None:
        _submit(client, ranked_run["id"], alice_headers)
        client.post(f"{API}/decisions/{ranked_run['id']}/claim", headers=bob_headers)
        refused = client.post(
            f"{API}/decisions/{ranked_run['id']}/takeover",
            json={"reason": " "},
            headers=carol_headers,
        )
        assert refused.status_code == 422
        taken = client.post(
            f"{API}/decisions/{ranked_run['id']}/takeover",
            json={"reason": "bob is away this week"},
            headers=carol_headers,
        )
        assert taken.status_code == 200

    def test_a_directed_request_nobody_claimed_can_still_be_taken_over(
        self, client: TestClient, ranked_run, alice_headers, carol_headers
    ) -> None:
        """The other half of the stuck-request bug.

        Somebody asked for bob, bob never came back, and nothing had
        claimed it — so a takeover keyed on "who holds it" would have had
        nobody to take it from.
        """
        _submit(client, ranked_run["id"], alice_headers, reviewer=BOB[0])
        taken = client.post(
            f"{API}/decisions/{ranked_run['id']}/takeover",
            json={"reason": "bob has left the project"},
            headers=carol_headers,
        )
        assert taken.status_code == 200
        assert taken.json()["submission"] == "in_review"


class TestAcknowledgementBelongsToTheClaim:
    def _sent_and_claimed(self, client, run_id, owner_headers, reviewer_headers):
        _submit(client, run_id, owner_headers)
        assert (
            client.post(f"{API}/decisions/{run_id}/claim", headers=reviewer_headers).status_code
            == 200
        )

    def test_signing_without_acknowledging_is_refused(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        self._sent_and_claimed(client, ranked_run["id"], alice_headers, bob_headers)
        refused = client.post(
            f"{API}/decisions/{ranked_run['id']}/config-approval",
            json={"decision": "approve", "comment": "looks fine"},
            headers=bob_headers,
        )
        assert refused.status_code == 403
        assert "acknowledge" in refused.json()["error"]["message"]

    def test_the_whole_walk_works(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        self._sent_and_claimed(client, ranked_run["id"], alice_headers, bob_headers)
        assert (
            client.post(
                f"{API}/decisions/{ranked_run['id']}/review",
                json={"comment": "read the gate table"},
                headers=bob_headers,
            ).status_code
            == 200
        )
        signed = client.post(
            f"{API}/decisions/{ranked_run['id']}/config-approval",
            json={"decision": "approve", "comment": "clear on both objectives"},
            headers=bob_headers,
        )
        assert signed.status_code == 200, signed.text
        assert signed.json()["config_state"] == "approved"

    def test_a_reviewer_who_took_over_does_not_inherit_the_reading(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers
    ) -> None:
        """The hole this whole design exists to close.

        Bob reads it and puts it down; Carol picks it up. Carol has
        opened nothing. If acknowledgement were a property of the run,
        her signature would be admitted and the trail would show a
        reading followed by a signature, looking complete.
        """
        self._sent_and_claimed(client, ranked_run["id"], alice_headers, bob_headers)
        client.post(
            f"{API}/decisions/{ranked_run['id']}/review",
            json={"comment": "read it"},
            headers=bob_headers,
        )
        client.post(f"{API}/decisions/{ranked_run['id']}/release", headers=bob_headers)
        assert (
            client.post(
                f"{API}/decisions/{ranked_run['id']}/claim", headers=carol_headers
            ).status_code
            == 200
        )

        refused = client.post(
            f"{API}/decisions/{ranked_run['id']}/config-approval",
            json={"decision": "approve", "comment": "fine by me"},
            headers=carol_headers,
        )
        assert refused.status_code == 403
        assert "yours and under this claim" in refused.json()["error"]["message"]

    def test_signing_needs_a_comment(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        """It is the only part of the record that says why."""
        self._sent_and_claimed(client, ranked_run["id"], alice_headers, bob_headers)
        client.post(
            f"{API}/decisions/{ranked_run['id']}/review",
            json={"comment": "read"},
            headers=bob_headers,
        )
        refused = client.post(
            f"{API}/decisions/{ranked_run['id']}/config-approval",
            json={"decision": "approve", "comment": "   "},
            headers=bob_headers,
        )
        assert refused.status_code == 422

    def test_the_owner_cannot_acknowledge_their_own_run(
        self, client: TestClient, ranked_run, alice_headers
    ) -> None:
        """Under strict duties. Reading your own evidence is not a check."""
        _submit(client, ranked_run["id"], alice_headers)
        client.post(f"{API}/decisions/{ranked_run['id']}/claim", headers=alice_headers)
        refused = client.post(
            f"{API}/decisions/{ranked_run['id']}/review",
            json={"comment": "mine"},
            headers=alice_headers,
        )
        assert refused.status_code == 403


class TestAnUnrankedRunClosesAtAcknowledgement:
    def test_reading_it_is_the_whole_answer(
        self, client: TestClient, profile_id, alice_headers, bob_headers
    ) -> None:
        """Most comparisons rank nobody, and there is nothing to sign.

        Leaving those requests open would turn the queue into a list of
        things nobody can finish; calling them ``approved`` would put a
        verdict on a run that recommends nobody.
        """
        run = client.post(
            f"{API}/decisions",
            json={
                "task_profile_id": profile_id,
                "candidates": [
                    {"stack": "astar+dwa", "local_config": "dwa_coarse"},
                    {"stack": "rrtstar+dwa", "local_config": "dwa_coarse"},
                ],
                "episodes": 2,
            },
            headers=alice_headers,
        ).json()
        assert run["config_state"] == "not_applicable"
        _submit(client, run["id"], alice_headers)
        client.post(f"{API}/decisions/{run['id']}/claim", headers=bob_headers)
        client.post(
            f"{API}/decisions/{run['id']}/review",
            json={"comment": "both failed G3"},
            headers=bob_headers,
        )
        state = client.get(f"{API}/decisions/{run['id']}/review-state").json()
        assert state["submission"] == "closed"
        assert state["status"] == "acknowledged"


class TestCarolIsNotSpecial:
    """A guard against the fixtures making the tests pass.

    Every account in this suite carries reviewer, so a rule that
    accidentally admitted everybody would look right everywhere above.
    """

    def test_the_engineer_account_really_lacks_the_capability(self, client: TestClient) -> None:
        body = client.get(f"{API}/auth/me", headers=auth_headers(client, ENGINEER)).json()
        assert "run.review" not in body["capabilities"]
        assert "run.create" in body["capabilities"]

    def test_the_ordinary_accounts_carry_it(self, client: TestClient) -> None:
        for who in (ALICE, BOB, CAROL):
            body = client.get(f"{API}/auth/me", headers=auth_headers(client, who)).json()
            assert "run.review" in body["capabilities"], who[0]


class TestTheBenchmarkLaneKeepsItsOwnRules:
    """Two lanes, one table, two rulebooks.

    Rewriting the rules a stored benchmark was decided under would make
    its audit trail describe a process that never happened, so the claim
    workflow refuses to touch benchmark requests at all.
    """

    def test_a_benchmark_request_is_not_visible_to_the_decision_queue(
        self, client: TestClient, app
    ) -> None:
        from planbench_api.review import ReviewRequest, ReviewStatus, ReviewSubject

        app.state.repos.reviews.create(
            ReviewRequest(
                id="",
                benchmark_id="b1",
                subject_kind=ReviewSubject.BENCHMARK,
                subject_id="b1",
                requested_by_user_id="u1",
                reviewer_user_id="u2",
                requested_reviewer_user_id="u2",
                status=ReviewStatus.PENDING,
                created_at="2026-08-13T10:00:00Z",
            )
        )
        from planbench_api.decision_review import DecisionReviewService

        service = DecisionReviewService(
            app.state.repos.reviews, app.state.repos.users, app.state.repos.decision_runs
        )
        assert service.queue() == []
        assert service.current("b1") is None


class TestAClaimDoesNotOutliveTheRightToHoldIt:
    def test_losing_the_reviewer_role_puts_the_run_back_in_the_pool(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers, app
    ) -> None:
        """Otherwise the engineers waiting on it never learn why.

        Checked when the request is read rather than only where a role is
        revoked: revoking happens in one place, forgetting to release
        happens everywhere else.
        """
        from planbench_api.accounts import Role

        _submit(client, ranked_run["id"], alice_headers)
        assert (
            client.post(
                f"{API}/decisions/{ranked_run['id']}/claim", headers=bob_headers
            ).status_code
            == 200
        )
        bob = app.state.repos.users.find_by_nickname(BOB[0])
        app.state.repos.users.set_roles(bob.id, frozenset({Role.ENGINEER}))

        state = client.get(f"{API}/decisions/{ranked_run['id']}/review-state").json()
        assert state["submission"] == "submitted"
        assert state["claimed_by_user_id"] is None
        assert state["available_to_pool"] is True
        assert (
            client.post(
                f"{API}/decisions/{ranked_run['id']}/claim", headers=carol_headers
            ).status_code
            == 200
        )


class TestTheQueue:
    """Which pile a waiting run lands in, and for whom.

    The endpoint sorts rather than filters because the answer depends on
    who asked: one request is ``mine`` to its holder, ``directed`` to the
    person it names, ``pool`` to everybody else and ``sent`` to whoever
    submitted it. A flat list would leave every client re-deriving that.
    """

    def _queue(self, client, headers):
        answered = client.get(f"{API}/decisions/review-queue", headers=headers)
        assert answered.status_code == 200, answered.text
        return answered.json()

    def test_an_unclaimed_run_is_in_the_pool_and_in_the_owners_sent(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        run_id = ranked_run["id"]
        _submit(client, run_id, alice_headers, comment="please look")

        reviewer = self._queue(client, bob_headers)
        assert [row["run_id"] for row in reviewer["pool"]] == [run_id]
        assert reviewer["mine"] == [] and reviewer["directed"] == []
        assert reviewer["pool"][0]["request_comment"] == "please look"

        # The same request, from the other side. An engineer cannot act
        # on it; the only question they have is whether anybody took it.
        owner = self._queue(client, alice_headers)
        assert [row["run_id"] for row in owner["sent"]] == [run_id]
        assert owner["sent"][0]["submission"] == "submitted"

    def test_a_directed_request_reaches_only_the_person_it_names(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers
    ) -> None:
        run_id = ranked_run["id"]
        _submit(client, run_id, alice_headers, reviewer=BOB[0])

        named = self._queue(client, bob_headers)
        assert [row["run_id"] for row in named["directed"]] == [run_id]
        assert named["pool"] == []

        # Not in anybody else's pool: a directed request is a question
        # asked of one person, and putting it in the open pile would make
        # naming somebody meaningless.
        assert self._queue(client, carol_headers)["pool"] == []

    def test_claiming_moves_it_out_of_everybody_elses_list(
        self, client: TestClient, ranked_run, alice_headers, bob_headers, carol_headers
    ) -> None:
        run_id = ranked_run["id"]
        _submit(client, run_id, alice_headers)
        assert (
            client.post(f"{API}/decisions/{run_id}/claim", headers=bob_headers).status_code == 200
        )

        holder = self._queue(client, bob_headers)
        assert [row["run_id"] for row in holder["mine"]] == [run_id]
        assert holder["pool"] == []

        # Held by somebody else, so it is in no pile Carol can act on.
        # Taking it is still possible, but a takeover starts from the run
        # rather than from a queue.
        other = self._queue(client, carol_headers)
        assert other["mine"] == [] and other["pool"] == [] and other["directed"] == []

    def test_it_says_whether_the_holder_has_actually_read_it(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        """A queue showing only who holds a review lies by omission.

        "Bob has it" reads as "Bob is dealing with it" while Bob has
        opened nothing. The acknowledgement belongs to the claim, so this
        is the honest version of the same row.
        """
        run_id = ranked_run["id"]
        _submit(client, run_id, alice_headers)
        client.post(f"{API}/decisions/{run_id}/claim", headers=bob_headers)
        assert self._queue(client, bob_headers)["mine"][0]["acknowledged"] is False

        client.post(
            f"{API}/decisions/{run_id}/review", json={"comment": "read it"}, headers=bob_headers
        )
        assert self._queue(client, bob_headers)["mine"][0]["acknowledged"] is True

    def test_an_engineer_gets_their_sent_pile_and_nothing_to_act_on(
        self, client: TestClient, ranked_run, alice_headers, engineer_headers
    ) -> None:
        """Open to any reader, filled by capability.

        Refusing an engineer the endpoint would mean a second one
        returning the same rows under a different name — they need
        ``sent`` to see whether anybody picked their work up. The three
        reviewer piles come back empty because the rule that fills them
        is about who may claim.
        """
        _submit(client, ranked_run["id"], alice_headers)
        engineer = self._queue(client, engineer_headers)
        assert engineer["mine"] == []
        assert engineer["directed"] == []
        assert engineer["pool"] == []
        assert engineer["sent"] == []

    def test_an_answered_run_leaves_the_queue(
        self, client: TestClient, ranked_run, alice_headers, bob_headers
    ) -> None:
        run_id = ranked_run["id"]
        _submit(client, run_id, alice_headers)
        client.post(f"{API}/decisions/{run_id}/claim", headers=bob_headers)
        client.post(
            f"{API}/decisions/{run_id}/review", json={"comment": "read it"}, headers=bob_headers
        )
        signed = client.post(
            f"{API}/decisions/{run_id}/config-approval",
            json={"decision": "approve", "comment": "fine"},
            headers=bob_headers,
        )
        assert signed.status_code == 200, signed.text

        # Not "answered and still listed": a queue is what is outstanding,
        # and the record of what was decided lives on the run.
        assert self._queue(client, bob_headers)["mine"] == []
        assert self._queue(client, alice_headers)["sent"] == []

    def test_review_queue_is_a_route_and_not_read_as_a_run_id(
        self, client: TestClient, alice_headers
    ) -> None:
        """Registered ahead of ``/decisions/{run_id}``, which would eat it."""
        assert client.get(f"{API}/decisions/review-queue", headers=alice_headers).status_code == 200
        assert client.get(f"{API}/decisions/no-such-run", headers=alice_headers).status_code == 404
