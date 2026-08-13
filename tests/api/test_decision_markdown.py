"""Exporting a selection run as Markdown.

The old flow had this for benchmarks and it retired with `/benchmarks`.
The capability did not: a Decision Card is read by people who will not
open the platform — somebody signing off a deployment, somebody reviewing
it six months later, somebody pasting it into a ticket.

**A document travels further than the screen it came from**, which makes
the caveats matter more here, not less. On screen a reader can hover a
tooltip or click through to the gate table; in a file they cannot. So the
three properties below are structural rather than cosmetic:

1. a run with no card still exports, because most runs have none;
2. null renders as "not measured", because HĐ-12 defines it that way and
   a blank Markdown cell reads as reassurance;
3. the recommendation's scope travels with the recommendation, because a
   document that arrives without it is one somebody will apply elsewhere.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from planbench_api.decision_markdown import decision_report_filename, render_decision_markdown

API = "/api/v1"


def run(**overrides):
    """A stored run, with only what the renderer reads."""
    base = {
        "id": "run_1",
        "task_profile_id": "open_hall_v2",
        "experiment_scope": "global_planner_selection",
        "contracts_version": "6.7.0",
        "created_at": "2026-08-13T10:00:00Z",
        "card": None,
        "review_state": "unreviewed",
        "reviewed_by": None,
        "reviewed_at": None,
        "config_state": "not_applicable",
        "config_decided_by": None,
        "config_decided_at": None,
        "report": {
            "identity": {
                "experiment_scope": "global_planner_selection",
                "git_sha": "abc1234",
                "anchor_config_version": "1",
                "created_at": "2026-08-13T10:00:00Z",
            },
            "sample": {"n_episodes": 30, "n_min_required": 6},
            "candidates": [
                {
                    "candidate_id": "c1",
                    "stack_label": "astar+dwa",
                    "local_controller_config": "dwa_coarse",
                    "local_observation_class": "lidar_only",
                    "n_distinct_episodes": 30,
                    "success_rate": 0.9,
                    "pooled_p99_latency_ms": 12.5,
                    "cleared_gates": True,
                    "blocking_gates": [],
                }
            ],
            "measurement_environment": {"benchmark_host": {}, "warning": None},
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestEveryRunExports:
    def test_a_run_with_no_card_still_produces_a_document(self) -> None:
        """Most runs have no card, and that is a result (HĐ-7).

        Refusing to render one would make the ordinary outcome the one
        nobody can hand to a reviewer — the same pressure that once
        produced a card bounding a collision probability off a single
        episode.
        """
        text = render_decision_markdown(run())
        assert "## No Decision Card" in text
        assert "The gate table above is the result." in text

    def test_the_gate_table_comes_before_the_card(self) -> None:
        """Six gates run before anything is scored, so they lead."""
        text = render_decision_markdown(run())
        assert text.index("## Gates") < text.index("## No Decision Card")

    def test_a_deployment_that_cannot_rank_says_so_as_its_own_case(self) -> None:
        """HĐ-8.4: no candidate would ever change this one.

        Distinct from "nobody survived", which is about the field.
        """
        report = run().report
        report["gate_only_deployment"] = "no cost anchor declared"
        text = render_decision_markdown(run(report=report))
        assert "HĐ-8.4" in text
        assert "no cost anchor declared" in text

    def test_the_filename_names_the_run(self) -> None:
        assert decision_report_filename("run_1") == "decision-run_1.md"


class TestTheCaveatsTravelWithTheNumbers:
    def test_an_unmeasured_margin_is_named_rather_than_blank(self) -> None:
        """A blank cell reads as reassurance; HĐ-12 makes null a finding."""
        card = {
            "recommended": {"candidate_id": "c1", "stack": "astar+dwa"},
            "alternative": None,
            "status": "recommended",
            "contracts_version": "6.7.0",
            "evidence": {
                "weight_stability_margin": None,
                "anchor_stability": None,
                "robustness_margin": None,
            },
        }
        text = render_decision_markdown(run(card=card))
        assert "None of the sensitivity margins were measured" in text
        assert "not the same as their" in text

    def test_a_measured_margin_is_printed_and_an_absent_one_is_still_named(self) -> None:
        card = {
            "recommended": {"candidate_id": "c1", "stack": "astar+dwa"},
            "alternative": None,
            "status": "recommended",
            "contracts_version": "6.7.0",
            "evidence": {
                "weight_stability_margin": 0.42,
                "anchor_stability": None,
                "robustness_margin": None,
            },
        }
        text = render_decision_markdown(run(card=card))
        assert "0.42" in text
        assert "not measured" in text

    def test_the_scope_travels_with_the_recommendation(self) -> None:
        """HĐ-1.4. A document without it is one applied somewhere else."""
        card = {
            "recommended": {"candidate_id": "c1", "stack": "astar+dwa"},
            "alternative": None,
            "status": "recommended",
            "contracts_version": "6.7.0",
            "evidence": {},
        }
        text = render_decision_markdown(run(card=card))
        assert "HĐ-1.4" in text
        assert "open_hall_v2" in text

    def test_an_interrupted_run_shows_both_counts(self) -> None:
        """245 alone reads as a deliberate 245-episode run."""
        report = run().report
        report["sample"] = {"n_episodes": 245, "n_episodes_requested": 300, "n_min_required": 6}
        text = render_decision_markdown(run(report=report))
        assert "245" in text
        assert "300" in text
        assert "Interrupted" in text

    def test_an_unpinned_host_warning_reaches_the_document(self) -> None:
        """Unpinned, every latency number measures this machine too."""
        report = run().report
        report["measurement_environment"]["warning"] = "CPU governor not pinned"
        text = render_decision_markdown(run(report=report))
        assert "Measurement environment" in text
        assert "CPU governor not pinned" in text

    def test_a_retired_candidate_names_the_sample_it_actually_got(self) -> None:
        report = run().report
        report["candidates"][0]["stopped_early"] = {
            "episodes_run": 12,
            "episodes_planned": 30,
            "gate": "G2",
            "rule": "collision bound exceeded",
        }
        text = render_decision_markdown(run(report=report))
        assert "12 of 30" in text
        assert "collision bound exceeded" in text

    def test_the_two_human_acts_stay_apart(self) -> None:
        """Reading and approving are different (HĐ-14)."""
        text = render_decision_markdown(run(review_state="reviewed", reviewed_by="alice"))
        assert "Review state" in text
        assert "Configuration decision" in text
        assert "separate acts (HĐ-14)" in text


class TestUnlikeComparisonsAreNamed:
    def test_one_observation_class_produces_no_warning(self) -> None:
        assert "were shown different things" not in render_decision_markdown(run())

    def test_two_classes_produce_one(self) -> None:
        """ΔU between differently-informed stacks prices the privilege.

        Worse on paper than on screen: the reader of a file cannot ask a
        follow-up question.
        """
        report = run().report
        report["candidates"].append(
            {
                **report["candidates"][0],
                "candidate_id": "c2",
                "stack_label": "astar+ppo",
                "local_observation_class": "full_static_map",
            }
        )
        text = render_decision_markdown(run(report=report))
        assert "were shown different things" in text
        assert "measuring the privilege" in text

    def test_an_undeclared_class_counts_as_its_own(self) -> None:
        """Silence cannot be shown to match what the others declared."""
        report = run().report
        report["candidates"].append(
            {**report["candidates"][0], "candidate_id": "c2", "local_observation_class": None}
        )
        text = render_decision_markdown(run(report=report))
        assert "were shown different things" in text
        assert "not measured" in text


class TestItSurvivesHostileContent:
    def test_a_pipe_in_a_value_does_not_break_the_table(self) -> None:
        """A stack label with a pipe would silently shift every column."""
        report = run().report
        report["candidates"][0]["stack_label"] = "astar|dwa"
        text = render_decision_markdown(run(report=report))
        assert r"astar\|dwa" in text

    def test_a_newline_in_a_value_stays_on_one_row(self) -> None:
        report = run().report
        report["candidates"][0]["local_controller_config"] = "dwa\ncoarse"
        text = render_decision_markdown(run(report=report))
        assert "dwa coarse" in text

    def test_a_run_with_no_report_at_all_still_renders(self) -> None:
        """A row stored before a field existed is not a crash."""
        text = render_decision_markdown(run(report={}))
        assert "# Selection run" in text
        assert "## No Decision Card" in text


class TestOverHttp:
    """The wiring only. Rendering is covered above, against the function.

    A test that drove a real selection to get one stored run would spend
    minutes of simulation to assert a Content-Disposition header — the
    render is a pure function of the stored row, and the row shape is
    what the cases above pin.
    """

    def test_the_route_exists_and_says_it_is_a_download(self) -> None:
        from planbench_api.routers.decisions import decision_report_markdown

        source = inspect.getsource(decision_report_markdown)
        assert "attachment; filename=" in source
        assert "text/markdown" in source
        # Not gated on approval: reading is the act approval follows
        # (HĐ-14), so a gate here would invert the order.
        #
        # Asserted against the compiled names rather than the source
        # text, because the docstring explains the rule and a substring
        # search would match its own explanation — the same trap the
        # replan-fairness test fell into.
        called = set(decision_report_markdown.__code__.co_names)
        assert not {name for name in called if "approv" in name}
        assert "get" in called

    def test_an_unknown_run_is_a_404(self, client) -> None:
        response = client.get(f"{API}/decisions/no_such_run/report.md")
        assert response.status_code == 404
