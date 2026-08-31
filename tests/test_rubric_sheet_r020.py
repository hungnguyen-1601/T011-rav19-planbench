"""The r0.2.0 amendment: one judgement per episode, and a denominator
the sheet computes.

r0.1.0 scored statements. That measures precision — of the sentences an
arm wrote, how many hold and cite the packet — and precision has a
failure mode this experiment walked into: it is maximised by writing
nothing. On `holdout-b1` the arm abstained on nineteen of thirty-seven
blocks, every abstention was marked `should_have`, and none of it
reached the reported number, because a sentence never written has no
row.

R6 asks the question the experiment was for — *on this episode, did it
say why one side beat the other* — and these tests pin the two
decisions that make it answerable rather than merely asked: the
denominator is computed, and the marks already given are carried.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _sheet():  # type: ignore[no-untyped-def]
    """The sheet builder, imported by path — it is not a package."""
    spec = importlib.util.spec_from_file_location(
        "rubric_sheet_by_episode", REPO / "scripts" / "rubric_sheet_by_episode.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class _Fact:
    ref: str
    value: object


@dataclass(frozen=True)
class _View:
    facts: tuple[_Fact, ...]


def _packet(*pairs: tuple[str, str]) -> _View:
    return _View(tuple(_Fact(ref, value) for ref, value in pairs))


class TestTheDenominatorIsComputedRatherThanEyeballed:
    """Which episodes *had* an answer available is not the scorer's call.

    An arm that says nothing has two very different excuses — the packet
    held a mechanism and it missed one, or the packet held none and
    silence was correct — and telling them apart decides whether the
    silence counts against it. Asking the person scoring to re-derive
    that from the packet table, thirty times, puts the denominator in
    the same hands as the numerator.
    """

    def test_a_support_contrast_means_the_packet_could_answer(self) -> None:
        view = _packet(
            ("contrast:component_differs:2", "context"),
            ("contrast:detection_worse_on_loser:1", "support"),
        )
        assert _sheet().answerable(view) is True

    def test_context_alone_is_not_an_answer(self) -> None:
        """`context` says the two stacks differ somewhere.

        That is not a mechanism, and an arm that stays quiet in front of
        it is right to.
        """
        view = _packet(
            ("contrast:component_differs:2", "context"),
            ("contrast:divergence_precedes_outcome:3", "context"),
        )
        assert _sheet().answerable(view) is False

    def test_the_word_support_is_read_off_a_contrast_and_nothing_else(self) -> None:
        """Not a second opinion about the evidence.

        `support` is the strength the packet already assigned to a
        contrast, so the sheet and the platform cannot disagree about
        which of them carry weight. A detector firing is an observation,
        not a difference between the two sides.
        """
        assert _sheet().answerable(_packet(("obs:stuck_cluster:C5@ep", "support"))) is False

    def test_the_mark_says_which_side_of_that_line_an_episode_is_on(self) -> None:
        answerable = "\n".join(_sheet().episode_mark(_packet(("contrast:x:1", "support"))))
        silent_ok = "\n".join(_sheet().episode_mark(_packet(("contrast:x:1", "context"))))
        assert "packet co the tra loi why" in answerable
        assert "packet khong co contrast" in silent_ok
        assert "| R6 |" in answerable and "| R6 |" in silent_ok

    def test_an_episode_whose_packet_is_missing_gets_no_mark(self) -> None:
        """A blank R6 under no packet reads as a judgement nobody made.

        Better to ask nothing than to ask somebody to score blind.
        """
        assert _sheet().episode_mark(None) == []


class TestAnAmendedRubricDoesNotCostARereadOfWhatWasRead:
    """r0.2.0 changes no R1-R5 rule, so it must not ask for them again.

    Re-issuing thirty-seven blank blocks would mean re-deriving marks
    that already exist, with the previous answers visible on the next
    monitor — which is not an independent second scoring, it is a slower
    copy of the first one with room to drift.
    """

    def _scored_sheet(self) -> str:
        return "\n".join(
            [
                "# Cham tay",
                "",
                "# Episode `aaaa`",
                "",
                "| ref | strength | noi gi | so kem theo |",
                "|---|---|---|---|",
                "| `contrast:x:1` | **support** | mot cai gi do | - |",
                "",
                "### 001 - **khong de xuat gi**",
                "",
                "| R1 | R2 | R3 | R5 |",
                "|---|---|---|---|",
                "| n/a | n/a | n/a | should_have |",
                "",
                "# Episode `bbbb`",
                "",
                "| ref | strength | noi gi | so kem theo |",
                "|---|---|---|---|",
                "| `contrast:y:2` | **context** | khac | - |",
                "",
                "### 002",
                "",
                "| R1 | R2 | R3 | R5 |",
                "|---|---|---|---|",
                "| holds | yes | all | n/a |",
                "",
            ]
        )

    def test_each_block_gets_its_marks_back_under_its_own_episode(self, tmp_path: Path) -> None:
        path = tmp_path / "scored.md"
        path.write_text(self._scored_sheet(), encoding="utf-8")
        carried = _sheet().marks_already_given(path)
        assert carried[("aaaa", 1)] == ["n/a", "n/a", "n/a", "should_have"]
        assert carried[("bbbb", 2)] == ["holds", "yes", "all", "n/a"]

    def test_a_packet_row_is_not_mistaken_for_a_judgement(self, tmp_path: Path) -> None:
        """The packet is itself a four-column table.

        It is printed under the episode heading and above the blocks, so
        a reader that keeps collecting rows after a block is finished
        pulls contrast rows in as scores — thirty-seven real marks came
        back as sixty-one the first time this ran.

        Two resets stop that, at the heading and after each block is
        captured, and this pins the *outcome* rather than either one:
        the count goes wrong when both are gone, and each alone still
        covers a normally shaped sheet. Pinning them individually would
        pin the shape of the loop, which is not the thing that must hold.
        """
        path = tmp_path / "scored.md"
        path.write_text(self._scored_sheet(), encoding="utf-8")
        assert len(_sheet().marks_already_given(path)) == 2

    def test_carried_marks_are_written_back_into_the_new_block(self) -> None:
        block = "\n".join(
            _sheet().render_item(
                1,
                {"hypothesis_id": "-abstained-", "abstention_reason": "vi sao do"},
                ["n/a", "n/a", "n/a", "should_have"],
            )
        )
        assert "| n/a | n/a | n/a | should_have |" in block

    def test_a_block_with_nothing_carried_is_still_blank(self) -> None:
        block = "\n".join(
            _sheet().render_item(
                1, {"hypothesis_id": "-abstained-", "abstention_reason": "vi sao do"}, None
            )
        )
        assert "| n/a | n/a | n/a |  |" in block


class TestTheAmendmentIsRecordedRatherThanSlippedIn:
    """Changing a rubric after seeing results is the move this project
    forbids. What makes this one legitimate is the direction and the
    paper trail, so both are pinned rather than left to a report.
    """

    def test_the_preregistration_names_the_new_rubric(self) -> None:
        from planbench_analyst.preregistration_episode import EPISODE_PREREGISTRATION

        assert EPISODE_PREREGISTRATION.rubric == "r0.2.0"
        assert EPISODE_PREREGISTRATION.as_dict()["rubric"] == "r0.2.0"

    def test_the_sheet_and_the_preregistration_agree_on_which_rubric(self) -> None:
        """A sheet headed r0.1.0 scored against an r0.2.0 registration is
        two documents describing different experiments.
        """
        from planbench_analyst.preregistration_episode import EPISODE_PREREGISTRATION

        assert EPISODE_PREREGISTRATION.rubric == _sheet().RUBRIC

    def test_the_amendment_dates_itself_and_says_which_way_the_bar_moved(self) -> None:
        source = (
            REPO
            / "services"
            / "analyst_service"
            / "planbench_analyst"
            / "preregistration_episode.py"
        ).read_text(encoding="utf-8")
        assert "2026-08-30" in source, "an amendment without a date is not one"
        assert "harder rather than easier" in source
