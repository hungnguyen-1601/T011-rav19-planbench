"""Reading a run the platform refused to write a decision card for.

A card is refused when fewer than two candidates clear the six gates,
and that refusal is about a **deployment** claim: nobody may be told
which stack to ship. It says nothing about whether one stack reached the
goal in a given episode and the other did not, which is a different
claim, settled by `build_verdict` on ``outcome_only`` without any
utility at all — and it is the claim a person opening one episode is
actually asking.

The episodes such a run contributes are the reason to read it: the ones
where the two sides disagree are the hardest explanations in the whole
set, because the question is not which was quicker but why one never
arrived. The ones where they agree are the control, and this file holds
down that they are included — an arm that explains the decided episodes
and also invents explanations for the undecided ones is worse than one
that does neither, and a set of only decided episodes cannot tell them
apart.

What it must not do is let this script pick, after seeing results, which
two candidates a run was "really" about.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


def _sweep():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "run_episode_experiments", REPO / "scripts" / "run_episode_experiments.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def report(*, candidates: int = 2, decided: int = 3, agreed: int = 10) -> dict[str, Any]:
    """A cardless report: episode rows and a sample, no pair, no card."""
    episodes = [f"ep-{index:03d}" for index in range(decided + agreed)]
    ids = [f"cand-{chr(ord('a') + index)}" for index in range(candidates)]
    rows = []
    for position, candidate_id in enumerate(ids):
        rows.append(
            {
                "candidate_id": candidate_id,
                "episodes": [
                    {
                        "episode_context_id": episode,
                        # The first `decided` episodes are where the two
                        # sides disagree: only the first candidate fails.
                        "success": not (index < decided and position == 0),
                        "failure_reason": "timeout" if index < decided and position == 0 else "",
                    }
                    for index, episode in enumerate(episodes)
                ],
            }
        )
    return {"candidates": rows, "sample": {"episode_context_ids": episodes}}


class TestWhichTwoCandidatesItReads:
    def test_two_candidates_leave_nothing_to_choose(self) -> None:
        assert _sweep().cardless_pair(report()) == ("cand-a", "cand-b")

    def test_the_order_is_the_id_and_not_the_outcome(self) -> None:
        """Ordering by who won would let the reading of a run decide how
        the run is read, which is the same move as choosing the pair."""
        payload = report()
        payload["candidates"].reverse()
        assert _sweep().cardless_pair(payload) == ("cand-a", "cand-b")

    def test_three_candidates_are_refused(self) -> None:
        sweep = _sweep()
        with pytest.raises(sweep.CardlessRefusal) as refusal:
            sweep.cardless_pair(report(candidates=3))
        assert "exactly two" in str(refusal.value)

    def test_one_candidate_is_refused_too(self) -> None:
        sweep = _sweep()
        with pytest.raises(sweep.CardlessRefusal):
            sweep.cardless_pair(report(candidates=1))


class TestWhichEpisodesItReads:
    def test_every_episode_the_two_sides_disagree_on(self) -> None:
        sweep = _sweep()
        chosen = sweep.cardless_episodes(report(decided=3, agreed=10), "cand-a", "cand-b")
        assert {"ep-000", "ep-001", "ep-002"} <= set(chosen)

    def test_a_fixed_sample_of_the_rest_comes_too(self) -> None:
        sweep = _sweep()
        chosen = sweep.cardless_episodes(report(decided=3, agreed=10), "cand-a", "cand-b")
        assert len(chosen) == 3 + sweep.CARDLESS_UNDECIDED_SAMPLE
        # Not because the undecided ones are interesting on their own:
        # they are what an arm has to decline on, and a set without them
        # cannot tell declining from having nothing to decline.
        assert set(chosen) - {"ep-000", "ep-001", "ep-002"}

    def test_the_sample_is_the_head_of_the_recorded_order(self) -> None:
        """Fixed rather than sampled: two readings of one artifact must
        put the same episodes in front of the model."""
        sweep = _sweep()
        first = sweep.cardless_episodes(report(), "cand-a", "cand-b")
        again = sweep.cardless_episodes(report(), "cand-a", "cand-b")
        assert first == again

    def test_a_run_where_nobody_disagrees_still_yields_the_control(self) -> None:
        sweep = _sweep()
        chosen = sweep.cardless_episodes(report(decided=0, agreed=10), "cand-a", "cand-b")
        assert len(chosen) == sweep.CARDLESS_UNDECIDED_SAMPLE
