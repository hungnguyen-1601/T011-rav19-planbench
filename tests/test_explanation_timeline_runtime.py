"""W1.3 — the timeline block reaches the packet on the runtime path.

M2 built the block and the scoring pass never asked for it: the packet
builder needs the deployment's thresholds to normalise a running number
against, ``_explanation_packet`` passed none, and the guard clause
returned early with an omission nobody read. Every production packet
carried an empty ``timelines`` while the fixtures carried a full one —
so an ablation of that input would have measured the fixtures against
themselves.

What is held here: the thresholds arrive from the profile, the
reference **length** does not (it is each episode's own line), the
projection is derived once by the platform's own rule, and the block's
cost in bytes is bounded and stated rather than assumed small.
"""

from __future__ import annotations

import json

from test_explanation_measurements import exemplar_set, trace

from planbench_explanation.packet_builder import (
    TIMELINE_MARKS,
    DeploymentThresholds,
    project_progress,
    timelines_from_traces,
)

#: The four numbers a run's profile states about itself. The fifth a
#: ``Deployment`` needs — the reference length — is the episode's.
THRESHOLDS = DeploymentThresholds(
    robot_radius_m=0.3,
    control_period_s=0.1,
    clearance_warning_m=0.15,
    max_linear_velocity=1.0,
)


def without_progress(episode_id: str = "ep-001"):  # type: ignore[no-untyped-def]
    """A trace as the scoring pass assembles it: no ``progress_m``."""
    built = trace(episode_id)
    columns = {name: value for name, value in built.columns.items() if name != "progress_m"}
    return built.model_copy(update={"columns": columns})


# --------------------------------------------------------------------------
# The join: profile thresholds, episode length
# --------------------------------------------------------------------------


def test_thresholds_alone_are_enough_to_build_a_timeline() -> None:
    """The runtime path has the profile and not a reference length, which
    is why it passed nothing and got nothing."""
    built, omissions = timelines_from_traces(
        [without_progress()], exemplar_set("ep-001"), None, thresholds=THRESHOLDS
    )
    assert omissions == ()
    (timeline,) = built
    assert {point.clock for point in timeline.points} == {"at_time", "at_progress"}


def test_a_run_with_neither_still_says_why_it_has_no_timeline() -> None:
    built, omissions = timelines_from_traces([trace()], exemplar_set("ep-001"), None)
    assert built == ()
    assert omissions


def test_the_reference_length_comes_from_the_episode_and_not_the_profile() -> None:
    """One length shared across a run would put a robot halfway down the
    map at 100% of a shorter neighbour's route."""
    placeholder = THRESHOLDS.for_length(1.0)
    built, _ = timelines_from_traces(
        [without_progress()], exemplar_set("ep-001"), placeholder, thresholds=None
    )
    (timeline,) = built
    reached = [point for point in timeline.points if point.clock == "at_progress"]
    # Against the placeholder metre the robot would be hundreds of times
    # "done"; against its own line the fraction is a fraction.
    assert all(point.progress_fraction <= 1.5 for point in reached)


# --------------------------------------------------------------------------
# The projection, once
# --------------------------------------------------------------------------


def test_a_trace_without_progress_gets_it_from_the_platforms_own_rule() -> None:
    projected = project_progress(without_progress())
    assert projected is not None
    updated, length = projected
    assert len(list(updated.columns["progress_m"])) == len(list(updated.columns["t"]))
    assert length > 0


def test_a_trace_that_already_carries_progress_is_left_alone() -> None:
    """Somebody upstream measured it against a line this cannot see;
    recomputing would be the second rule."""
    original = trace("ep-001")
    projected = project_progress(original)
    assert projected is not None
    updated, length = projected
    assert updated is original
    assert length == 0.0


def test_a_trace_that_cannot_be_projected_is_refused_rather_than_placed() -> None:
    broken = trace("ep-001", columns={"t": [0.0, 0.1], "x": [0.0, 0.5]})
    assert project_progress(broken) is None


def test_a_trace_that_cannot_be_projected_is_skipped_and_said_so() -> None:
    broken = trace("ep-001", columns={"t": [0.0, 0.1], "x": [0.0, 0.5]})
    built, omissions = timelines_from_traces(
        [broken], exemplar_set("ep-001"), None, thresholds=THRESHOLDS
    )
    assert built == ()
    assert any("missing a column" in item for item in omissions)


# --------------------------------------------------------------------------
# What the block costs
# --------------------------------------------------------------------------


def test_the_block_costs_what_it_was_budgeted_at() -> None:
    """M2 budgeted about fifty facts a packet against 15–54 before it.
    Two exemplar episodes at three marks on two clocks is twelve points
    at seven numbers each — measured here rather than assumed, because
    the packet is a prompt somebody pays for on every case."""
    built, _ = timelines_from_traces(
        [without_progress("ep-001"), without_progress("ep-002")],
        exemplar_set("ep-001", "ep-002"),
        None,
        thresholds=THRESHOLDS,
    )
    points = sum(len(item.points) for item in built)
    assert points <= 2 * 2 * len(TIMELINE_MARKS)
    encoded = json.dumps([item.model_dump(mode="json") for item in built], sort_keys=True)
    # Roughly 1.6 kB for two episodes. Held under four so a regression
    # that started carrying every trace row is a failing test rather
    # than a prompt bill.
    assert len(encoded.encode("utf-8")) < 4096


def test_the_same_episode_twice_does_not_pay_twice() -> None:
    """A one-row trace puts every wall-clock mark at the same instant,
    and three copies of one moment are not three readings."""
    single = without_progress("ep-001")
    single = single.model_copy(
        update={
            "columns": {
                name: (list(value)[:1] if isinstance(value, list | tuple) else value)
                for name, value in single.columns.items()
            }
        }
    )
    built, _ = timelines_from_traces([single], exemplar_set("ep-001"), None, thresholds=THRESHOLDS)
    if built:
        (timeline,) = built
        at_time = [point for point in timeline.points if point.clock == "at_time"]
        assert len({point.mark for point in at_time}) == len(at_time)
