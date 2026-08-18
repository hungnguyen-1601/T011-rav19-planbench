"""Reading a paper over HTTP, by paste and by upload.

The extraction itself is tested against the model in
``tests/test_agent_paper.py``. What matters here is the boundary: that
neither route writes anything, that a file too large or of the wrong
kind is refused at the door rather than after a minute of parsing, and
that a deployment without a PDF reader says so instead of blaming the
person who uploaded a perfectly good PDF.

The suite runs on the deterministic provider, so nothing here needs a
key.
"""

from __future__ import annotations

import io

PAPER = (
    "We evaluate in a warehouse with a differential-drive robot. "
    "Global paths come from A* on an 8-connected grid. "
    "For local control we use the Dynamic Window Approach. "
    "The controller runs at 20 Hz over a 2.0 second horizon."
)


def upload(client, headers, name: str, data: bytes):
    return client.post(
        "/api/v1/candidates/from-paper/upload",
        files={"file": (name, io.BytesIO(data), "application/octet-stream")},
        headers=headers,
    )


class TestBothRoutesAreClosed:
    def test_pasting_requires_authentication(self, client):
        assert client.post("/api/v1/candidates/from-paper", json={"text": PAPER}).status_code == 401

    def test_uploading_requires_authentication(self, client):
        assert upload(client, None, "paper.txt", PAPER.encode()).status_code == 401

    def test_empty_text_is_rejected_by_the_schema(self, client, alice_headers):
        response = client.post(
            "/api/v1/candidates/from-paper", json={"text": ""}, headers=alice_headers
        )
        assert response.status_code == 422


class TestNeitherRouteStoresAnything:
    """The draft is a proposal. If reading a paper could register a
    candidate, every number downstream would rest on an extraction
    nobody agreed to."""

    def test_reading_a_paper_leaves_the_candidate_list_alone(self, client, alice_headers):
        before = client.get("/api/v1/candidates", headers=alice_headers).json()
        client.post("/api/v1/candidates/from-paper", json={"text": PAPER}, headers=alice_headers)
        upload(client, alice_headers, "paper.txt", PAPER.encode())
        assert client.get("/api/v1/candidates", headers=alice_headers).json() == before

    def test_the_upload_route_is_a_post_with_no_write_verb_in_its_path(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        path = "/api/v1/candidates/from-paper/upload"
        assert set(paths[path]) == {"post"}


class TestWhatTheUploadRefuses:
    def test_a_file_it_cannot_read_names_the_ones_it_can(self, client, alice_headers):
        response = upload(client, alice_headers, "paper.docx", b"anything")
        assert response.status_code == 422, response.text
        assert ".pdf" in response.text

    def test_a_pdf_with_no_text_layer_is_explained_not_swallowed(self, client, alice_headers):
        """Either 422 ("no text in that PDF") or 503 ("install pypdf") —
        both name a next step. What must never happen is a draft built
        from bytes nobody could read."""
        response = upload(client, alice_headers, "scan.pdf", b"%PDF-1.4 no text here")
        assert response.status_code in (422, 503), response.text

    def test_an_empty_file_does_not_reach_the_model(self, client, alice_headers):
        response = upload(client, alice_headers, "paper.txt", b"")
        assert response.status_code == 200
        assert response.json()["refused"]


class TestWhatComesBack:
    def test_a_paste_and_an_upload_of_the_same_text_agree(self, client, alice_headers):
        """Two doors into one extraction. Different answers here would
        mean the door changed the reading."""
        pasted = client.post(
            "/api/v1/candidates/from-paper", json={"text": PAPER}, headers=alice_headers
        )
        uploaded = upload(client, alice_headers, "paper.txt", PAPER.encode())
        assert pasted.status_code == 200, pasted.text
        assert uploaded.status_code == 200, uploaded.text
        assert pasted.json() == uploaded.json()

    def test_it_publishes_the_stacks_a_draft_could_name(self, client, alice_headers):
        """So a reader seeing no stack can tell "the paper's method is
        not here" from "the model gave up"."""
        body = upload(client, alice_headers, "paper.txt", PAPER.encode()).json()
        assert body["offerable_stacks"]
        assert "astar+ppo" not in body["offerable_stacks"]


class TestPartialReadingsSaySo:
    """A reading of two thirds of a paper must not look like a reading
    of the paper.

    The tail past the character cap used to be dropped with no error and
    no field recording it, so a long paper came back with a stack,
    quoted parameters and an `assumptions` list computed over the part
    the model saw — rendered identically to a complete extraction.
    """

    def test_a_whole_document_reports_itself_as_whole(self, client, alice_headers):
        body = upload(client, alice_headers, "paper.txt", PAPER.encode()).json()
        assert body["chars_read"] == body["chars_total"]

    def test_a_cut_document_reports_both_numbers(self, client, alice_headers):
        from planbench_api.routers.decisions import MAX_PAPER_CHARS

        long_paper = PAPER + " padding." * 20_000
        body = upload(client, alice_headers, "paper.txt", long_paper.encode()).json()
        assert body["chars_total"] > body["chars_read"]
        assert body["chars_read"] == MAX_PAPER_CHARS

    def test_the_pasted_path_reports_them_too(self, client, alice_headers):
        """Two doors into one extraction; a field on one and not the
        other would make the reading's completeness depend on the door."""
        body = client.post(
            "/api/v1/candidates/from-paper", json={"text": PAPER}, headers=alice_headers
        ).json()
        assert body["chars_read"] == body["chars_total"] == len(PAPER)


class TestOversizeIsRefusedBeforeItIsRead:
    def test_a_file_past_the_limit_is_refused(self, client, alice_headers):
        from planbench_api.routers.decisions import MAX_UPLOAD_BYTES

        response = upload(client, alice_headers, "big.txt", b"x" * (MAX_UPLOAD_BYTES + 1))
        assert response.status_code == 422
        assert "MB" in response.text

    def test_the_refusal_names_the_limit_rather_than_just_refusing(self, client, alice_headers):
        """ "Invalid request" tells the reader nothing they can act on."""
        from planbench_api.routers.decisions import MAX_UPLOAD_BYTES

        response = upload(client, alice_headers, "big.txt", b"x" * (MAX_UPLOAD_BYTES + 1))
        assert str(MAX_UPLOAD_BYTES // (1024 * 1024)) in response.text
