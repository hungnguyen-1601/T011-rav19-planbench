"""A reader may now type the question, and four things must stay true.

The analyst asked one fixed question, and every quality figure this
scope reports was measured on it: ten of eighteen episodes explained by
a majority of readings, one wrong statement in ninety. Letting a reader
change the question is worth having and is **not** covered by those
numbers, so the changes below are the ones that keep the rest honest.

* the question chooses what to answer and cannot add a fact — the packet
  is still the only evidence and every guard rule still runs;
* two different questions about one episode are two different questions,
  which the dedup key has to know or the second reader is served the
  first one's answer;
* the prompt checksum takes the wrapper and not the question, or every
  question would be its own system;
* and when the guard refuses everything, what the reader sees is the
  platform's fixed phrasing rather than the model's — which has to be
  said, most of all now that it will not be about what they asked.
"""

from __future__ import annotations

from planbench_analyst.episode_prompts import (
    READER_QUESTION_PREFACE,
    build_episode_user_turn,
    episode_prompt_checksum,
)
from planbench_api.episode_analysis import dedup_key


class TestTheQuestionReachesTheModel:
    def test_what_a_reader_typed_is_in_the_turn(self) -> None:
        turn = build_episode_user_turn(
            "packet", "catalog", reader_question="why is this one safer?"
        )
        assert "why is this one safer?" in turn
        assert READER_QUESTION_PREFACE in turn

    def test_empty_asks_the_question_the_scope_was_measured_on(self) -> None:
        """Not a degraded case: an empty box is how somebody asks for the
        answer the reported figures describe."""
        turn = build_episode_user_turn("packet", "catalog", reader_question="")
        assert READER_QUESTION_PREFACE not in turn
        assert turn == build_episode_user_turn("packet", "catalog")

    def test_whitespace_is_not_a_question(self) -> None:
        assert READER_QUESTION_PREFACE not in build_episode_user_turn(
            "packet", "catalog", reader_question="   \n  "
        )

    def test_it_comes_after_the_evidence_and_the_rules(self) -> None:
        """The model reads what it may say before it reads what it was
        asked. A question above the packet would be read as licence."""
        turn = build_episode_user_turn("PACKETBODY", "CATALOGBODY", reader_question="ask me")
        assert turn.index("PACKETBODY") < turn.index("ask me")
        assert turn.index("CATALOGBODY") < turn.index("ask me")

    def test_the_preface_keeps_the_packet_the_only_evidence(self) -> None:
        """The sentence that does the work, pinned as behaviour rather
        than wording: a question may not add a fact, and one the packet
        cannot answer is answered by naming what is missing."""
        assert "may not add a" in READER_QUESTION_PREFACE
        assert "nothing else" in READER_QUESTION_PREFACE


class TestTheChecksumTakesTheWrapperAndNotTheQuestion:
    def test_a_typed_question_does_not_change_the_prompt_identity(self) -> None:
        """A checksum that moved with each question would give every
        reader their own system, and no calibration could name one."""
        before = episode_prompt_checksum()
        build_episode_user_turn("packet", "catalog", reader_question="anything at all")
        assert episode_prompt_checksum() == before

    def test_the_wrapper_is_part_of_what_a_calibration_describes(self) -> None:
        assert READER_QUESTION_PREFACE.strip()
        assert "reader_question_preface" in _checksum_material()


def _checksum_material() -> str:
    from pathlib import Path

    return (
        Path(__file__).resolve().parents[1]
        / "services"
        / "analyst_service"
        / "planbench_analyst"
        / "episode_prompts.py"
    ).read_text(encoding="utf-8")


class TestTwoQuestionsAreTwoQuestions:
    """The key decides whether a request is answered afresh or served
    from the round already running. It knew the packet and the arm; it
    did not know the question, and could not have, until today."""

    def test_different_questions_do_not_share_an_answer(self) -> None:
        first = dedup_key(packet_checksum="p", runtime_config_checksum="c", question="why safer?")
        second = dedup_key(packet_checksum="p", runtime_config_checksum="c", question="why slower?")
        assert first != second

    def test_the_same_question_is_the_same_question(self) -> None:
        assert dedup_key(
            packet_checksum="p", runtime_config_checksum="c", question=" why safer? "
        ) == dedup_key(packet_checksum="p", runtime_config_checksum="c", question="why safer?")

    def test_no_question_hashes_as_it_always_did(self) -> None:
        """Artifacts written before a reader could type one stay
        addressable.

        Pinned against the digest the old two-field material produced,
        not against another call to today's function: comparing the new
        code with itself would pass however the key had changed, and the
        addresses already on disk would still be lost.
        """
        assert (
            dedup_key(packet_checksum="p", runtime_config_checksum="c")
            == "6a049fcc050492f5a8124fea8a5dba53b5f5705fa934cbc43e79d427c15bbaaf"
        )
        assert dedup_key(packet_checksum="p", runtime_config_checksum="c") == dedup_key(
            packet_checksum="p", runtime_config_checksum="c", question="   "
        )

    def test_the_packet_and_the_arm_still_separate_answers(self) -> None:
        assert dedup_key(packet_checksum="p", runtime_config_checksum="c") != dedup_key(
            packet_checksum="p", runtime_config_checksum="OTHER"
        )
