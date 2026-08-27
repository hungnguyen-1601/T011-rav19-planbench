"""A7 — freezing an analyst, calibrating it, and running it over frames.

A bundle is the claim "this exact system was graded", so most of what is
held here is what freezing refuses: a tree with edits in it, an image
named by a tag, a calibration that got lucky once, a model that changed
under us half way through.

The last section runs the container lane end to end without a container:
a fake platform answers frames over two in-memory streams, and the same
runner drives it. That is the seam paying for itself — if the loop only
worked in one lane, this would not pass.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from test_analyst_packet_view import observation, packet

from planbench_analyst.bundle_builder import (
    CALIBRATION_RUNS,
    CalibrationRun,
    FreezeRefusal,
    ModelIdentity,
    calibrate,
    freeze_bundle,
    working_tree_is_clean,
)
from planbench_analyst.stdio_lane import FrameHost, FrameProvider, FrameStream, run_from_frames
from planbench_analyst.stdio_protocol import Frame, decode, encode
from planbench_explanation.budget import PLATFORM_BUDGET_CAP
from planbench_explanation.catalog import TOOL_CATALOG_VERSION
from planbench_explanation.integration import MockToolHost
from planbench_explanation.protocol import (
    ANALYST_RUNNER_PROTOCOL_VERSION,
    AnalysisRequest,
    ToolRequest,
    ToolResult,
)

DIGEST = "sha256:" + "c" * 64
IDENTITY = ModelIdentity(model_id="claude-opus-5", model_revision="2026-05-01")


def clean_repo(tmp_path: Path) -> Path:
    """A real git repository with one commit and nothing outstanding."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)  # noqa: S603,S607
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)  # noqa: S603,S607
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)  # noqa: S603,S607
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)  # noqa: S603,S607
    subprocess.run(["git", "commit", "-qm", "one"], cwd=tmp_path, check=True)  # noqa: S603,S607
    return tmp_path


def frozen(root: Path, **overrides):  # type: ignore[no-untyped-def]
    fields = {
        "root": root,
        "bundle_id": "bundle-a7",
        "container_digest": DIGEST,
        "identity": IDENTITY,
        "generation_parameters": {"temperature": 0.0},
        "rag_index_version": "kb-index-3",
        "retrieval_config_checksum": "d" * 64,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
        "created_at": "2026-08-26T12:00:00Z",
    }
    fields.update(overrides)
    return freeze_bundle(**fields)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# What freezing refuses
# --------------------------------------------------------------------------


def test_a_clean_tree_freezes(tmp_path: Path) -> None:
    bundle = frozen(clean_repo(tmp_path))
    assert bundle.agent_code_digest.startswith("git:")
    assert len(bundle.agent_code_digest) == len("git:") + 40
    assert bundle.runner_protocol_version == ANALYST_RUNNER_PROTOCOL_VERSION
    assert bundle.requested_budget == PLATFORM_BUDGET_CAP


def test_a_tree_with_edits_cannot_be_frozen(tmp_path: Path) -> None:
    """The digest would name a commit that does not describe the code,
    and the edits are usually the interesting part."""
    root = clean_repo(tmp_path)
    (root / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert not working_tree_is_clean(root)
    with pytest.raises(FreezeRefusal, match="working tree"):
        frozen(root)


def test_an_untracked_file_counts_as_dirty(tmp_path: Path) -> None:
    """It is code the digest does not cover and the image may still copy in."""
    root = clean_repo(tmp_path)
    (root / "new_module.py").write_text("y = 1\n", encoding="utf-8")
    with pytest.raises(FreezeRefusal, match="working tree"):
        frozen(root)


def test_a_rehearsal_may_freeze_a_dirty_tree_and_says_it_is_one(tmp_path: Path) -> None:
    root = clean_repo(tmp_path)
    (root / "a.py").write_text("x = 3\n", encoding="utf-8")
    assert frozen(root, allow_dirty=True).agent_code_digest.startswith("git:")


@pytest.mark.parametrize("digest", ["latest", "sha256:short", "", "docker.io/analyst:1"])
def test_an_image_named_by_anything_but_a_digest_is_refused(tmp_path: Path, digest: str) -> None:
    """A tag moves, and a bundle whose image moved cannot be re-run."""
    with pytest.raises(FreezeRefusal, match="image digest"):
        frozen(clean_repo(tmp_path), container_digest=digest)


def test_generation_parameters_are_frozen_as_pointers(tmp_path: Path) -> None:
    """Two configurations differing only in nesting must not share an
    identity — see the collision the flattening exists to prevent."""
    nested = frozen(clean_repo(tmp_path), generation_parameters={"thinking": {"type": "enabled"}})
    assert list(nested.generation_parameters) == ["/thinking/type"]


def test_two_bundles_of_one_configuration_share_an_identity(tmp_path: Path) -> None:
    root = clean_repo(tmp_path)
    assert frozen(root).identity_checksum == frozen(root, bundle_id="other").identity_checksum


def test_a_different_budget_is_a_different_system(tmp_path: Path) -> None:
    root = clean_repo(tmp_path)
    tighter = PLATFORM_BUDGET_CAP.model_copy(update={"max_model_calls": 2})
    tight_bundle = frozen(root, requested_budget=tighter)
    assert frozen(root).identity_checksum != tight_bundle.identity_checksum


# --------------------------------------------------------------------------
# Calibration takes the worst, and never retries
# --------------------------------------------------------------------------


def scorer(scores, violations=None, identities=None):  # type: ignore[no-untyped-def]
    """A ``score_once`` that walks a script, one call per run."""
    calls = {"n": 0}

    def once():  # type: ignore[no-untyped-def]
        index = calls["n"]
        calls["n"] += 1
        if isinstance(scores[index], Exception):
            raise scores[index]
        return (
            scores[index],
            (violations or [0] * len(scores))[index],
            (identities or [IDENTITY] * len(scores))[index],
        )

    return once


def test_three_runs_and_the_report_carries_the_worst(tmp_path: Path) -> None:
    """Not the best — that is a system that got lucky once — and not the
    mean, which hides the run that failed."""
    bundle = frozen(clean_repo(tmp_path))
    record = calibrate(
        bundle,
        scorer([{"precision": 0.94}, {"precision": 0.81}, {"precision": 0.90}]),
        root=tmp_path,
    )
    assert record.passed
    assert record.worst == {"precision": 0.81}
    assert record.report()["runs"] == CALIBRATION_RUNS


def test_a_structural_violation_anywhere_ends_it(tmp_path: Path) -> None:
    bundle = frozen(clean_repo(tmp_path))
    record = calibrate(
        bundle,
        scorer([{"precision": 0.95}] * 3, violations=[0, 1, 0]),
        root=tmp_path,
    )
    assert not record.passed


def test_a_run_that_raised_is_recorded_and_not_retried(tmp_path: Path) -> None:
    """A retry is another draw reported as though the first had not
    happened."""
    bundle = frozen(clean_repo(tmp_path))
    record = calibrate(
        bundle,
        scorer([{"precision": 0.95}, RuntimeError("timed out"), {"precision": 0.95}]),
        root=tmp_path,
    )
    assert not record.passed
    assert len(record.scores) == 2
    assert record.errors and "timed out" in record.errors[0]


def test_a_model_that_changed_under_us_is_caught(tmp_path: Path) -> None:
    """A provider that re-points an alias mid-calibration produces a
    report about two systems, and nothing in the numbers would show it."""
    bundle = frozen(clean_repo(tmp_path))
    other = ModelIdentity(model_id="claude-opus-5", model_revision="2026-06-01")
    record = calibrate(
        bundle,
        scorer([{"precision": 0.95}] * 3, identities=[IDENTITY, other, IDENTITY]),
        root=tmp_path,
    )
    assert record.identity_drift
    assert not record.passed


def test_the_report_names_the_bundle_and_both_budgets(tmp_path: Path) -> None:
    bundle = frozen(clean_repo(tmp_path))
    record = CalibrationRun(bundle=bundle, source_hash="a" * 64, identity=IDENTITY)
    report = record.report()
    assert report["bundle_identity_checksum"] == bundle.identity_checksum
    assert report["requested_budget_checksum"] == PLATFORM_BUDGET_CAP.checksum


# --------------------------------------------------------------------------
# The container lane, without a container
# --------------------------------------------------------------------------


def fake_platform(answers: list[dict]) -> tuple[io.StringIO, io.StringIO]:
    """The platform side of the wire, scripted.

    Written as frames rather than as mocks: what is being tested is that
    the container speaks the protocol, and a mock would test that it
    calls a method.
    """
    inbound = io.StringIO()
    for index, payload in enumerate(answers, start=1):
        inbound.write(
            encode(
                Frame(
                    message_type=payload.pop("message_type"),
                    analysis_run_id="analysis-a7",
                    bundle_id="bundle-a7",
                    sequence=index,
                    payload=payload,
                )
            )
            + "\n"
        )
    inbound.seek(0)
    return inbound, io.StringIO()


def test_the_container_asks_for_a_completion_rather_than_calling_a_model() -> None:
    inbound, outbound = fake_platform(
        [
            {
                "message_type": "model_response",
                "text": "",
                "structured": {"abstained": True, "abstention_reason": "nothing", "hypotheses": []},
                "stop_reason": "end_turn",
                "model": "claude-opus-5",
                "usage": {"input_tokens": 11, "output_tokens": 3},
                "provider_turn": None,
            }
        ]
    )
    stream = FrameStream(
        analysis_run_id="analysis-a7", bundle_id="bundle-a7", outbound=outbound, inbound=inbound
    )
    provider = FrameProvider(stream=stream, model_id="claude-opus-5")
    response = provider.complete(
        __import__("planbench_agent.provider", fromlist=["LLMRequest"]).LLMRequest(
            system="s", messages=()
        )
    )
    assert response.input_tokens == 11
    sent = decode(outbound.getvalue().splitlines()[0])
    assert sent.message_type == "model_request"
    assert "api_key" not in sent.payload


def test_the_container_asks_for_a_check_rather_than_running_one() -> None:
    built = packet(observations=[observation()])
    analysis = AnalysisRequest(
        analysis_run_id="analysis-a7",
        analyst_bundle_id="bundle-a7",
        packet=built,
        catalog=__import__("planbench_explanation.catalog", fromlist=["TOOL_CATALOG"]).TOOL_CATALOG,
    )
    host = MockToolHost(analysis)
    request = ToolRequest(
        request_id="req-001",
        analysis_run_id="analysis-a7",
        case_packet_checksum=analysis.case_packet_checksum,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        analyst_bundle_id="bundle-a7",
        sequence=1,
        tool_id="get_known_unknowns",
        tool_version="1.0.0",
        hypothesis_id="hyp-1",
    )
    served = ToolResult(
        request_id="req-001",
        tool_id="get_known_unknowns",
        tool_version="1.0.0",
        execution_status="not_checkable",
        input_provenance="missing",
        failure_code="tool_unavailable",
    )
    inbound, outbound = fake_platform(
        [{"message_type": "tool_result", "result": served.model_dump(mode="json")}]
    )
    stream = FrameStream(
        analysis_run_id="analysis-a7", bundle_id="bundle-a7", outbound=outbound, inbound=inbound
    )
    result = FrameHost(stream=stream).call(request)
    assert result.request_id == "req-001"
    assert decode(outbound.getvalue().splitlines()[0]).message_type == "tool_request"
    assert host.session is not None


def test_a_whole_round_runs_over_frames_with_no_container() -> None:
    """The seam paying for itself: the same runner, a different lane."""
    built = packet(observations=[observation()])
    inbound, outbound = fake_platform(
        [
            {"message_type": "hello"},
            {
                "message_type": "analysis_request",
                "packet": built.model_dump(mode="json"),
                "available_evidence": [],
                "effective_budget": PLATFORM_BUDGET_CAP.model_dump(mode="json"),
                "model_id": "claude-opus-5",
                "generation_parameters": {"temperature": 0.0},
            },
            {
                "message_type": "model_response",
                "text": "",
                "structured": {
                    "abstained": True,
                    "abstention_reason": "no detection maps to a check",
                    "hypotheses": [],
                },
                "stop_reason": "end_turn",
                "model": "claude-opus-5",
                "usage": {"input_tokens": 900, "output_tokens": 40},
                "provider_turn": None,
            },
            {"message_type": "declaration_ack"},
        ]
    )
    log = io.StringIO()
    stream = FrameStream(
        analysis_run_id="", bundle_id="", outbound=outbound, inbound=inbound, log=log
    )
    assert run_from_frames(stream) == 0

    sent = [decode(line) for line in outbound.getvalue().splitlines()]
    kinds = [frame.message_type for frame in sent]
    assert kinds[-2:] == ["final_response", "done"]
    final = sent[-2].payload
    assert final["response"]["abstained"] is True
    assert final["cost"]["model_calls"] == 1
    # Every log line went to stderr; stdout carried protocol only.
    assert "round" in log.getvalue()
    assert all(frame.message_type for frame in sent)
