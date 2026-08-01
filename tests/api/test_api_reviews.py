"""Optional peer review, end to end.

The property under test throughout: asking for a review must cost the
asker the ability to answer it. Everything else — the inbox, the badge,
the comments — is convenience around that one rule.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_api_benchmarks import create_benchmark, run_benchmark


def send_for_review(
    client: TestClient, benchmark_id: str, headers: dict, reviewer: str, stage: str = "spec", **kw
) -> dict:
    response = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/review-requests",
        json={"reviewer_nickname": reviewer, "stage": stage, **kw},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestSendingARequest:
    def test_by_nickname(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        request = send_for_review(
            client, benchmark["id"], alice_headers, "bob", comment="fair seeds?"
        )
        assert request["status"] == "pending"
        assert request["stage"] == "spec"
        assert request["request_comment"] == "fair seeds?"
        # It arrives.
        inbox = client.get("/api/v1/reviews/inbox", headers=bob_headers).json()
        assert inbox["pending"] == 1
        assert inbox["requests"][0]["request"]["id"] == request["id"]
        assert inbox["requests"][0]["requested_by"]["nickname"] == "alice"
        assert inbox["requests"][0]["benchmark_name"] == "api-benchmark"

    def test_the_nickname_lookup_is_case_insensitive(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        send_for_review(client, benchmark["id"], alice_headers, "BOB")
        assert client.get("/api/v1/reviews/inbox", headers=bob_headers).json()["pending"] == 1

    def test_an_unknown_nickname_is_rejected(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/review-requests",
            json={"reviewer_nickname": "nobody-here", "stage": "spec"},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "nobody-here" in response.json()["error"]["message"]

    def test_you_cannot_review_your_own_benchmark(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/review-requests",
            json={"reviewer_nickname": "alice", "stage": "spec"},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert "yourself" in response.json()["error"]["message"]

    def test_only_the_owner_may_send(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/review-requests",
            json={"reviewer_nickname": "carol", "stage": "spec"},
            headers=bob_headers,
        )
        assert response.status_code == 403

    def test_a_second_pending_request_for_the_same_stage_is_refused(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        """One pending request per stage: who it waits on has one answer."""
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        send_for_review(client, benchmark["id"], alice_headers, "bob")
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/review-requests",
            json={"reviewer_nickname": "carol", "stage": "spec"},
            headers=alice_headers,
        )
        assert response.status_code == 422

    def test_asking_is_recorded_in_the_audit_trail(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        detail = client.get(f"/api/v1/benchmarks/{benchmark['id']}", headers=alice_headers).json()
        actions = [entry["action"] for entry in detail["approvals"]]
        # Sending a spec for review is also submitting it, so the gate has
        # something to open — both entries carry the request id.
        assert actions == ["submit", "request_review"]
        assert {entry["review_request_id"] for entry in detail["approvals"]} == {request["id"]}
        assert detail["state"] == "pending_approval"


class TestSpecReviewBlocksTheRun:
    def test_the_owner_cannot_run_while_a_spec_review_is_pending(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        send_for_review(client, benchmark["id"], alice_headers, "bob")
        response = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"

    def test_approval_unblocks_the_run(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(
            client, created_map, created_scenario, alice_headers, seeds=[1]
        )
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        approved = client.post(
            f"/api/v1/reviews/{request['id']}/approve",
            json={"comment": "conditions look fair"},
            headers=bob_headers,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["request"]["status"] == "approved"

        run = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
        assert run.status_code == 200, run.text
        actions = [entry["action"] for entry in run.json()["benchmark"]["approvals"]]
        # A real second person approved, so no self_approved entry.
        assert "approve" in actions
        assert "self_approved" not in actions

    def test_rejection_sends_the_benchmark_back_to_draft(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        rejected = client.post(
            f"/api/v1/reviews/{request['id']}/reject",
            json={"comment": "two seeds is not enough"},
            headers=bob_headers,
        )
        assert rejected.status_code == 200
        assert rejected.json()["request"]["status"] == "rejected"
        detail = client.get(f"/api/v1/benchmarks/{benchmark['id']}", headers=alice_headers).json()
        assert detail["state"] == "draft"
        # And the owner is free again, because nothing is pending.
        assert client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers
        ).status_code in (200, 409)

    def test_cancelling_the_request_frees_the_owner(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = create_benchmark(
            client, created_map, created_scenario, alice_headers, seeds=[1]
        )
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        cancelled = client.post(f"/api/v1/reviews/{request['id']}/cancel", headers=alice_headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["request"]["status"] == "cancelled"
        assert cancelled.json()["request"]["cancelled_at"]
        run = client.post(f"/api/v1/benchmarks/{benchmark['id']}/run", headers=alice_headers)
        assert run.status_code == 200, run.text


class TestResultReviewBlocksAcceptance:
    def test_the_owner_cannot_self_accept_while_a_result_review_is_pending(
        self, client: TestClient, created_map, created_scenario, alice_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        send_for_review(client, benchmark["id"], alice_headers, "bob", stage="result")
        response = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/accept-result", json={}, headers=alice_headers
        )
        assert response.status_code == 403

    def test_the_reviewer_accepts_and_the_benchmark_is_accepted(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = run_benchmark(client, created_map, created_scenario, alice_headers, seeds=[1])
        request = send_for_review(
            client, benchmark["id"], alice_headers, "bob", stage="result", comment="agree?"
        )
        answered = client.post(
            f"/api/v1/reviews/{request['id']}/approve",
            json={"comment": "numbers check out"},
            headers=bob_headers,
        )
        assert answered.status_code == 200, answered.text
        detail = client.get(f"/api/v1/benchmarks/{benchmark['id']}", headers=alice_headers).json()
        assert detail["state"] == "accepted"
        entry = detail["approvals"][-1]
        assert entry["action"] == "accept_result"
        assert entry["user"] == "bob"
        assert entry["review_request_id"] == request["id"]
        assert entry["comment"] == "numbers check out"


class TestOnlyTheNamedReviewerMayAnswer:
    @pytest.fixture
    def pending(self, client: TestClient, created_map, created_scenario, alice_headers) -> dict:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        return send_for_review(client, benchmark["id"], alice_headers, "bob")

    def test_a_third_member_cannot_approve(
        self, client: TestClient, pending: dict, carol_headers
    ) -> None:
        response = client.post(
            f"/api/v1/reviews/{pending['id']}/approve", json={}, headers=carol_headers
        )
        assert response.status_code == 403
        assert "not sent to you" in response.json()["error"]["message"]

    def test_a_third_member_cannot_reject(
        self, client: TestClient, pending: dict, carol_headers
    ) -> None:
        response = client.post(
            f"/api/v1/reviews/{pending['id']}/reject", json={}, headers=carol_headers
        )
        assert response.status_code == 403

    def test_the_owner_cannot_answer_their_own_request(
        self, client: TestClient, pending: dict, alice_headers
    ) -> None:
        """The whole point: asking must cost you the ability to answer."""
        response = client.post(
            f"/api/v1/reviews/{pending['id']}/approve", json={}, headers=alice_headers
        )
        assert response.status_code == 403

    def test_the_owner_cannot_approve_from_the_benchmark_route_either(
        self, client: TestClient, pending: dict, alice_headers
    ) -> None:
        """Two doors, one lock."""
        response = client.post(
            f"/api/v1/benchmarks/{pending['benchmark_id']}/approve",
            json={},
            headers=alice_headers,
        )
        assert response.status_code == 403

    def test_a_request_can_only_be_answered_once(
        self, client: TestClient, pending: dict, bob_headers
    ) -> None:
        assert (
            client.post(
                f"/api/v1/reviews/{pending['id']}/approve", json={}, headers=bob_headers
            ).status_code
            == 200
        )
        again = client.post(f"/api/v1/reviews/{pending['id']}/reject", json={}, headers=bob_headers)
        assert again.status_code == 422
        assert "already approved" in again.json()["error"]["message"]

    def test_only_the_sender_can_cancel(
        self, client: TestClient, pending: dict, bob_headers
    ) -> None:
        response = client.post(f"/api/v1/reviews/{pending['id']}/cancel", headers=bob_headers)
        assert response.status_code == 403


class TestInboxAndComments:
    def test_sent_lists_what_i_asked_for(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        send_for_review(client, benchmark["id"], alice_headers, "bob")
        sent = client.get("/api/v1/reviews/sent", headers=alice_headers).json()
        assert len(sent) == 1
        assert sent[0]["reviewer"]["nickname"] == "bob"
        # And it is not in my own inbox.
        assert client.get("/api/v1/reviews/inbox", headers=alice_headers).json()["pending"] == 0

    def test_answering_clears_the_badge(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        client.post(f"/api/v1/reviews/{request['id']}/approve", json={}, headers=bob_headers)
        inbox = client.get("/api/v1/reviews/inbox", headers=bob_headers).json()
        assert inbox["pending"] == 0
        assert len(inbox["requests"]) == 1  # still readable, just answered

    def test_either_party_can_comment_without_deciding(
        self, client: TestClient, created_map, created_scenario, alice_headers, bob_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        asked = client.post(
            f"/api/v1/reviews/{request['id']}/comment",
            json={"comment": "why seed 7?"},
            headers=bob_headers,
        )
        assert asked.status_code == 200
        answered = client.post(
            f"/api/v1/reviews/{request['id']}/comment",
            json={"comment": "it is the failure case"},
            headers=alice_headers,
        )
        assert answered.status_code == 200
        body = answered.json()["request"]
        assert body["status"] == "pending"
        assert "bob: why seed 7?" in body["review_comment"]
        assert "alice: it is the failure case" in body["review_comment"]

    def test_an_outsider_cannot_comment(
        self, client: TestClient, created_map, created_scenario, alice_headers, carol_headers
    ) -> None:
        benchmark = create_benchmark(client, created_map, created_scenario, alice_headers)
        request = send_for_review(client, benchmark["id"], alice_headers, "bob")
        response = client.post(
            f"/api/v1/reviews/{request['id']}/comment",
            json={"comment": "hello"},
            headers=carol_headers,
        )
        assert response.status_code == 403


class TestAdminIntervention:
    def test_an_admin_can_unstick_a_pending_review_and_is_audited(
        self, client: TestClient, created_map, created_scenario, alice_headers, admin_headers
    ) -> None:
        """Somebody must be able to act when a reviewer has left."""
        benchmark = create_benchmark(
            client, created_map, created_scenario, alice_headers, seeds=[1]
        )
        send_for_review(client, benchmark["id"], alice_headers, "bob")
        approved = client.post(
            f"/api/v1/benchmarks/{benchmark['id']}/approve",
            json={"comment": "reviewer unavailable"},
            headers=admin_headers,
        )
        assert approved.status_code == 200, approved.text
        entry = approved.json()["approvals"][-1]
        assert entry["user"] == "dave"
        assert entry["role"] == "admin"
        assert entry["comment"] == "reviewer unavailable"
