"""The audit record a paid round writes about itself.

Every mode that runs a round writes one — shadow included, because the
artifact is how a shadow round is read at all, and a mode that spent a
model call and kept no record of it would be spending for nothing.

It had never been written. `episode_analyst_mode` is `off` by default
and no deployment had turned it on, so the first round to reach this
line was the first one ever: the model answered, the guard read it, and
then `json.dumps` refused the payload because the annotations in it are
`EpisodeAnnotation` dataclasses. The request became a 500 *after* the
call had been made and paid for, and the reader saw nothing.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from planbench_analyst.episode_guard import CONTRAST, EpisodeAnnotation
from planbench_api.episode_analysis import write_artifact


def _annotations() -> dict[str, EpisodeAnnotation]:
    return {
        "hyp-1": EpisodeAnnotation(
            bearing=CONTRAST,
            contract=("contrast_support", "occurrence_evidence"),
            occurrence_evidence_refs=("obs:stuck_cluster:B@ep-004",),
        ),
        "hyp-2": EpisodeAnnotation(),
    }


class TestTheRoundCanWriteItsOwnRecord:
    def test_annotations_survive_the_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "round.json"
        write_artifact(
            target,
            {
                "model": {
                    "response": {"abstained": False, "proposals": []},
                    # Exactly what the service passes: the annotations as
                    # the guard produced them. Converting here instead
                    # would test the conversion and not the writer, and
                    # the writer is where every caller goes through.
                    "annotations": dict(_annotations()),
                },
                "audit": {"blocked": []},
                "verdict": {"basis": "outcome_only"},
            },
        )
        written = json.loads(target.read_text(encoding="utf-8"))
        kept = written["model"]["annotations"]["hyp-1"]
        assert kept["bearing"] == CONTRAST
        assert kept["contract"] == ["contrast_support", "occurrence_evidence"]
        assert kept["occurrence_evidence_refs"] == ["obs:stuck_cluster:B@ep-004"]

    def test_a_plain_encoder_is_what_refused_them(self) -> None:
        """Why the writer needs an encoder at all, pinned as the failure
        it was: `json.dumps` on its own will not take an annotation, and
        the round died writing the record of a call already paid for."""
        with pytest.raises(TypeError, match="EpisodeAnnotation"):
            json.dumps({"annotations": dict(_annotations())})

    def test_something_that_is_not_a_dataclass_still_refuses(self, tmp_path: Path) -> None:
        """A `str()` fallback would put an object's repr into an audit
        record and make it look like data."""
        with pytest.raises(TypeError, match="object"):
            write_artifact(tmp_path / "x.json", {"model": object()})

    def test_every_field_of_an_annotation_is_recorded(self) -> None:
        """The artifact is the only account of what the guard decided
        about each proposal. A conversion that quietly dropped a field
        would leave a record that reads complete and is not."""
        one = asdict(EpisodeAnnotation(bearing=CONTRAST, supersedes="hyp-0"))
        assert set(one) == {
            "bearing",
            "contract",
            "occurrence_evidence_refs",
            "mechanism_reference_refs",
            "supersedes",
        }
        assert one["supersedes"] == "hyp-0"
