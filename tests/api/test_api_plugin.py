"""Drafting a plugin from a paper, over real HTTP.

The mentor's rule, tested at the boundary: the LLM's output must be in
the host's bundle shape or the system does not take it. The suite runs
on the deterministic provider, which produces no structured output — so
the honest answer on this rig is a refusal, and the tests assert the
refusal is legible rather than pretending a model ran.
"""

from __future__ import annotations

import io

PAPER = (
    "We present Theta*, an any-angle variant of A* over an occupancy grid. "
    "Line-of-sight checks let a vertex inherit its parent's parent. "
    "We weight the heuristic by 1.2."
)


class TestTheRouteIsClosedAndWritesNothing:
    def test_requires_authentication(self, anonymous):
        assert anonymous.post("/api/v1/plugins/from-paper", json={"text": PAPER}).status_code == 401

    def test_upload_requires_authentication(self, anonymous):
        response = anonymous.post(
            "/api/v1/plugins/from-paper/upload",
            files={"file": ("p.txt", io.BytesIO(PAPER.encode()), "text/plain")},
        )
        assert response.status_code == 401

    def test_empty_text_is_refused_by_the_schema(self, client, alice_headers):
        response = client.post(
            "/api/v1/plugins/from-paper", json={"text": ""}, headers=alice_headers
        )
        assert response.status_code == 422

    def test_drafting_registers_nothing(self, client, alice_headers):
        before = client.get("/api/v1/candidates", headers=alice_headers).json()
        client.post("/api/v1/plugins/from-paper", json={"text": PAPER}, headers=alice_headers)
        assert client.get("/api/v1/candidates", headers=alice_headers).json() == before

    def test_no_write_verb_in_the_path(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert set(paths["/api/v1/plugins/from-paper"]) == {"post"}
        assert set(paths["/api/v1/plugins/from-paper/upload"]) == {"post"}


class TestTheVerdictIsHonest:
    def test_the_mock_provider_yields_a_refusal_not_a_fake_bundle(self, client, alice_headers):
        """The deterministic responder cannot produce a manifest. The
        right answer is `refused` with a reason — a fabricated bundle
        here would mean the endpoint invents plugins when no model ran."""
        body = client.post(
            "/api/v1/plugins/from-paper", json={"text": PAPER}, headers=alice_headers
        ).json()
        assert body["refused"]
        assert body["accepted"] is False
        assert body["manifest"] == {}

    def test_the_upload_path_gives_the_same_honest_answer(self, client, alice_headers):
        body = client.post(
            "/api/v1/plugins/from-paper/upload",
            files={"file": ("p.txt", io.BytesIO(PAPER.encode()), "text/plain")},
            headers=alice_headers,
        ).json()
        assert body["refused"]
        assert body["accepted"] is False

    def test_an_unreadable_upload_names_the_readable_kinds(self, client, alice_headers):
        response = client.post(
            "/api/v1/plugins/from-paper/upload",
            files={"file": ("p.docx", io.BytesIO(b"x"), "application/octet-stream")},
            headers=alice_headers,
        )
        assert response.status_code == 422
        assert ".pdf" in response.text
