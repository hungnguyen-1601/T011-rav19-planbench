"""What a real scoring run leaves behind for the explanation layer.

Every other test in this area feeds hand-built reports, which is fine for
the rules and useless for the wiring: a fixture can spell a field the
pipeline never writes, and both sides pass. Two rounds of review turned
on exactly that — the first cut of the exemplar recipe read a field that
does not carry what its name suggests, and the fixtures agreed with it.

So this runs the comparison for real, on six episodes, and asks the
report the questions the explanation layer will ask it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_vertical_slice import write_profile

from planbench_benchmark import selection
from planbench_explanation.exemplars import compared_pair, select_exemplars_from_report

#: The same pair the early-stop run uses: two global planners over one
#: local controller, which is what ``global_planner_selection`` means.
CANDIDATES = (("astar+dwa", "dwa_coarse"), ("rrtstar+dwa", "dwa_coarse"))


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """One real comparison, shared by every test here."""
    workspace: Path = tmp_path_factory.mktemp("explanation_wiring")
    return selection.run_comparison(
        profile_path=write_profile(workspace),
        candidate_specs=CANDIDATES,
        scope="global_planner_selection",
        episodes=6,
        trace_root=workspace / "traces",
        run_root=workspace / "runs",
        reuse=False,
        quiet=True,
        map_base_dir=workspace,
    )


def test_the_run_records_the_pair_its_statistics_compared(
    report: dict[str, object],
) -> None:
    """The field the exemplar recipe reads, written by the pipeline.

    Its absence was invisible for a round: the recipe read the card's
    ``alternative`` instead, and every fixture obligingly put the
    runner-up there.
    """
    pair = report["comparison_pair"]
    assert isinstance(pair, dict)
    assert pair["recommended_candidate_id"]
    assert pair["runner_up_candidate_id"]
    assert pair["recommended_candidate_id"] != pair["runner_up_candidate_id"]

    card = report["decision_card"]
    assert isinstance(card, dict)
    assert pair["recommended_candidate_id"] == card["recommended"]["candidate_id"]


def test_the_cards_alternative_is_empty_on_a_run_like_this(
    report: dict[str, object],
) -> None:
    """Which is why the pair cannot be read from it (HĐ-12).

    ``alternative`` may only name a PARETO_FRONTIER candidate. No Pareto
    analysis runs here — as on most runs — so it is null while a perfectly
    good winner and runner-up exist.
    """
    card = report["decision_card"]
    assert isinstance(card, dict)
    assert card["alternative"] is None
    assert compared_pair(report) is not None


def test_every_scored_episode_carries_its_own_utility(
    report: dict[str, object],
) -> None:
    """Episode-level utility, per episode — the ΔU three roles need.

    Not the card's number: that one is set level and cannot be taken
    apart afterwards.
    """
    candidates = report["candidates"]
    assert isinstance(candidates, list)
    for entry in candidates:
        rows = entry["episodes"]
        assert rows, entry["candidate_id"]
        for row in rows:
            assert row["episode_decision_utility"] is not None
            assert 0.0 <= row["episode_decision_utility"] <= 1.0


def test_the_recipe_runs_on_the_real_report_end_to_end(
    report: dict[str, object],
) -> None:
    """The whole point: no fixture, no hand-built dictionary."""
    chosen = select_exemplars_from_report(report)

    pair = report["comparison_pair"]
    assert (chosen.candidate_a, chosen.candidate_b) == (
        pair["recommended_candidate_id"],  # type: ignore[index]
        pair["runner_up_candidate_id"],  # type: ignore[index]
    )
    assert chosen.n_episodes == 6
    episodes = {item.episode_context_id for item in chosen.exemplars}
    known = {row["episode_context_id"] for row in report["candidates"][0]["episodes"]}  # type: ignore[index]
    assert episodes <= known
