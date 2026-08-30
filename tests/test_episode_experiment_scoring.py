"""What the sweep records as a violation, and what it merely records.

This file exists because the first real sweep produced a number that
looked like a catastrophe and was not one: rule 2 fired 55 times across
twelve episodes, the preregistered ceiling was zero, and every one of
those firings was a sentence the guard had already taken out of the
answer. The constraint was counting the guard working.

Two things are held down here. A veto is read off the answer a person
is handed — so a blocked sentence contributes nothing to it — and every
name the preregistration vetoes on is a name the scorer actually emits,
which is the failure that let ``verdict_contradictions`` sit in one file
and ``verdict_contradictions_in_final`` in the other without either
being wrong on its own.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from test_analyst_episode_round import answer, hypothesis, round_over

from planbench_analyst.preregistration_episode import EPISODE_PREREGISTRATION
from planbench_explanation.episode_packet import EpisodePacket

REPO = Path(__file__).resolve().parents[1]


def _sweep():  # type: ignore[no-untyped-def]
    """The experiment script, imported by path — it is not a package."""
    spec = importlib.util.spec_from_file_location(
        "run_episode_experiments", REPO / "scripts" / "run_episode_experiments.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestEveryVetoIsReadOffTheFinalAnswer:
    def test_each_constraint_names_a_figure_the_scorer_emits(self) -> None:
        outcome, view = _round_with_a_blocked_quantity()
        scored = _sweep().score_round(outcome, view)
        for name, _ceiling in EPISODE_PREREGISTRATION.hard_constraints:
            assert name in scored, f"{name} is vetoed on but never measured"

    def test_each_constraint_is_named_for_the_answer_not_the_guard(self) -> None:
        for name, _ceiling in EPISODE_PREREGISTRATION.hard_constraints:
            assert name.endswith("_in_final"), (
                f"{name} reads as guard activity; a rule firing is the guard "
                "working, and counting it vetoes an arm for behaving"
            )

    def test_a_sentence_the_guard_removed_violates_nothing(self) -> None:
        """The whole reason this file exists."""
        outcome, view = _round_with_a_blocked_quantity()
        scored = _sweep().score_round(outcome, view)

        assert scored["quantities_in_statements_blocked"] >= 1, (
            "the fixture is meant to trip rule 2"
        )
        assert scored["quantities_in_statements_in_final"] == 0
        for name, ceiling in EPISODE_PREREGISTRATION.hard_constraints:
            assert scored[name] <= ceiling


class TestTheHashIsCountedWhereItWouldBeRead:
    def test_a_statement_naming_a_candidate_id_is_a_violation(self) -> None:
        outcome, view = _round_with_a_blocked_quantity()
        real = view.packet.candidates[0].candidate_id
        # Not run through the guard: what is being tested is the scorer's
        # reading of an answer, and an id is exactly what the guard is now
        # expected to have removed on the way here.
        object.__setattr__(
            outcome.response.proposals[0],
            "hypothesis_statement",
            f"the local controller of {real} was late",
        )
        scored = _sweep().score_round(outcome, view)
        assert scored["candidate_ids_in_final"] == 1

    def test_an_answer_in_labels_carries_none(self) -> None:
        outcome, view = _round_with_a_blocked_quantity()
        scored = _sweep().score_round(outcome, view)
        assert scored["candidate_ids_in_final"] == 0


def _round_with_a_blocked_quantity():  # type: ignore[no-untyped-def]
    """One kept proposal beside one rule 2 removed.

    Both statements are written the way an arm's answer is meant to be
    written — in labels. The fixture's candidate ids are single letters,
    so a sentence saying "present on B" names an id, and reading that
    as a leak is correct rather than a false positive.
    """
    from test_explanation_episode_packet import build_packet

    from planbench_analyst.episode_view import build_episode_view

    packet: EpisodePacket = build_packet()
    view = build_episode_view(packet)
    label = view.serialize()  # forces the aliases to exist
    assert label
    outcome = round_over(
        answer(
            hypothesis(
                statement=(
                    "a pattern on the losing side and absent on the other is "
                    "consistent with local minimum entrapment"
                )
            ),
            hypothesis(statement="the controller was late by 240 ms"),
        )
    )
    return outcome, view
