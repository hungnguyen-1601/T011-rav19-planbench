"""Decision Card and manifest (CONTRACTS HĐ-12, HĐ-13).

The card is where every earlier phase either holds up or quietly lies.
These tests are mostly about the second possibility: a field that states
something the run never established, a recommendation that skipped a
gate, or a manifest that cannot rebuild what it claims to describe.

The JSON is validated against ``contracts/schemas/*.json`` rather than
against the Pydantic models. The models are this codebase's
implementation of HĐ-12; the schema files are the contract itself, and
checking output against your own implementation proves nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator
from task_profile_fakes import constraints, make_profile

from planbench_decision.anchors import load_anchors
from planbench_decision.candidate import Candidate
from planbench_decision.card import (
    CARD_SCHEMA_PATH,
    MANIFEST_SCHEMA_PATH,
    BenchmarkHost,
    CardError,
    Provenance,
    build_decision_card,
    build_manifest,
)
from planbench_decision.gates import assert_no_banned_language, evaluate_gates
from planbench_decision.objectives import DecisionSettings
from planbench_decision.pareto import ParetoError, label_field
from planbench_decision.sensitivity import (
    AnchorStability,
    ScoredField,
    WeightStability,
    weight_stability,
)
from planbench_decision.stats import build_evidence, recommend
from planbench_metrics.definitions import EpisodeMetricSet
from planbench_schemas.contracts import CONTRACTS_VERSION
from planbench_schemas.episode_context import EpisodeContext

STRUCTURAL: dict[str, object] = {
    "kind": "structural",
    "target_implementation": "cpp_ros2",
    "bytes_per_search_node": 40,
    "bytes_per_tree_node": 40,
    "bytes_per_costmap_cell": 1,
    "costmap_layers": 3,
    "fixed_overhead_mb": 8.0,
}

TUNING: dict[str, object] = {
    "tuning_trials_used": 30,
    "tuning_wall_clock_h": 24.0,
    "n_tunable_params": 12,
    "evidence_log": "artifacts/tuning/optuna.log",
}

MODULAR: dict[str, object] = {
    "type": "modular",
    "global_planner": {"name": "astar", "version": "v1"},
    "local_controller": {"name": "dwa", "version": "v1"},
    "params": {"astar": {"heuristic": "euclidean"}, "dwa": {"sim_time": 1.5}},
    "observation_requirements": ["lidar_2d"],
    "resource_profile": dict(STRUCTURAL),
    "tuning": dict(TUNING),
}

#: 10% accepted collision risk ⇒ N_min = 30 (see test_gates).
FAST_CONSTRAINTS = constraints(collision_probability_max=0.1)

PROVENANCE = Provenance(
    git_sha="0123456789abcdef0123456789abcdef01234567",
    benchmark_host=BenchmarkHost(cpu="AMD Ryzen 7 5800X", cores_allocated=4, threads=1),
    created_at=datetime(2026, 8, 10, 9, 30, tzinfo=UTC),
    docker_image_digest="sha256:" + "a" * 64,
)


def candidate(**overrides: object) -> Candidate:
    return Candidate.model_validate({**MODULAR, **overrides})


def profile(**overrides: object):  # type: ignore[no-untyped-def]
    payload: dict[str, object] = {"constraints": dict(FAST_CONSTRAINTS)}
    payload.update(overrides)
    return make_profile(**payload)


def anchors():  # type: ignore[no-untyped-def]
    return load_anchors().resolve(profile())


def context(seed: int) -> EpisodeContext:
    return EpisodeContext.model_validate(
        {"task_profile_id": "warehouse_a_v1", "mission_id": "m1", "seed": seed}
    )


def episode(owner: Candidate, ctx: EpisodeContext, **overrides: object) -> EpisodeMetricSet:
    payload: dict[str, object] = {
        "episode_context_id": ctx.episode_context_id,
        "candidate_id": owner.candidate_id,
        "success": True,
        "failure_reason": None,
        "collision_count": 0,
        "min_clearance": 0.45,
        "near_miss_rate": 0.05,
        "path_length_m": 44.0,
        "travel_time_s": 60.0,
        "l_ref_m": 40.0,
        "path_efficiency": 0.90,
        "t_ideal_s": 50.0,
        "time_efficiency": 0.80,
        "smoothness": 1.2,
        "stop_and_go_count": 2,
        "p99_latency_ms": 25.0,
        "peak_search_nodes": 412_000,
        "peak_tree_nodes": 0,
        "costmap_cells": 400_000,
        "memory_estimate_mb": 19.0,
        "peak_rss_mb": 340.0,
        "cpu_time_per_mission_s": 2.0,
    }
    payload.update(overrides)
    return EpisodeMetricSet.model_validate(payload)


class Run:
    """One complete comparison, from episodes to card and manifest.

    Assembled here rather than in each test because the interesting part
    of every test below is one deviation from a valid run, and the
    deviation is invisible if the other twenty lines are copied around
    it.
    """

    def __init__(
        self,
        field: list[tuple[Candidate, dict[str, object]]],
        *,
        task_profile: object = None,
        settings: DecisionSettings | None = None,
        n: int = 30,
    ) -> None:
        self.profile = task_profile if task_profile is not None else profile()
        self.settings = settings or DecisionSettings()
        self.anchors = load_anchors().resolve(self.profile)  # type: ignore[arg-type]
        self.contexts = [context(seed) for seed in range(n)]
        self.evidence = []
        self.gate_reports = {}
        #: Kept so a test can re-score this same field — the sensitivity
        #: sweeps need the metrics, not the scores.
        self.metrics_by_candidate: dict[str, list[EpisodeMetricSet]] = {}
        for owner, common in field:
            # Episodes differ from one another, because real ones do.
            # Built from identical values these were one episode repeated
            # thirty times, and G2 counts a replayed set as a single
            # independent sample (HĐ-7.1) — so the whole field would fail
            # the gate and there would be nothing to card.
            metrics = [
                episode(owner, ctx, **{"path_length_m": 44.0 + index * 0.01, **common})
                for index, ctx in enumerate(self.contexts)
            ]
            self.metrics_by_candidate[owner.candidate_id] = metrics
            report = evaluate_gates(
                owner,
                self.profile,
                metrics,
                self.contexts,
                # G4's real input is pooled over every control step; a
                # fixture built from per-episode metric sets has no such
                # pool, and every episode here shares one latency anyway.
                pooled_p99_latency_ms=max(m.p99_latency_ms for m in metrics),
            )
            self.gate_reports[owner.candidate_id] = report
            # HĐ-7: gates run *before* any scoring. An eliminated
            # candidate still gets a row on the card, but it is never
            # scored and never ranked — which is the whole reason a fast
            # candidate that collides cannot win.
            if report.passed:
                self.evidence.append(
                    build_evidence(owner, metrics, self.contexts, self.anchors, self.settings)
                )
        self.recommendation = recommend(self.evidence, seed=11)

    def card(self, **kwargs: object):  # type: ignore[no-untyped-def]
        payload: dict[str, object] = {
            "manifest_ref": "runs/2026-08-10/abc123/manifest.json",
        }
        payload.update(kwargs)
        return build_decision_card(
            self.recommendation,
            self.evidence,
            self.gate_reports,
            self.profile,  # type: ignore[arg-type]
            self.settings,
            "global_planner_selection",
            **payload,  # type: ignore[arg-type]
        )

    def manifest(self, **kwargs: object):  # type: ignore[no-untyped-def]
        kwargs.setdefault("evaluation_contexts", self.contexts)
        return build_manifest(
            self.recommendation,
            self.evidence,
            self.gate_reports,
            self.profile,  # type: ignore[arg-type]
            self.settings,
            self.anchors,
            PROVENANCE,
            **kwargs,  # type: ignore[arg-type]
        )


@pytest.fixture
def two_candidates() -> Run:
    """One clearly better candidate and one clearly worse."""
    return Run(
        [
            (candidate(), {"p99_latency_ms": 12.0}),
            (candidate(params={"astar": {"heuristic": "manhattan"}}), {"p99_latency_ms": 45.0}),
        ]
    )


class TestSchemasThemselves:
    def test_both_schema_files_ship_at_the_contract_path(self) -> None:
        """§16 maps the logical ``contracts/`` to this directory."""
        assert CARD_SCHEMA_PATH.is_file()
        assert MANIFEST_SCHEMA_PATH.is_file()

    @pytest.mark.parametrize("path", [CARD_SCHEMA_PATH, MANIFEST_SCHEMA_PATH])
    def test_they_are_valid_json_schema(self, path) -> None:  # type: ignore[no-untyped-def]
        """A malformed schema validates everything and catches nothing."""
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


class TestCardValidatesAgainstTheContract:
    def test_a_real_card_passes_the_shipped_schema(self, two_candidates: Run) -> None:
        """The phase DoD: the card validates against contracts/schemas."""
        validator = Draft202012Validator(json.loads(CARD_SCHEMA_PATH.read_text(encoding="utf-8")))
        errors = sorted(validator.iter_errors(two_candidates.card().to_json_dict()), key=str)
        assert errors == []

    def test_a_real_manifest_passes_the_shipped_schema(self, two_candidates: Run) -> None:
        validator = Draft202012Validator(
            json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        )
        errors = sorted(validator.iter_errors(two_candidates.manifest().to_json_dict()), key=str)
        assert errors == []

    def test_the_card_round_trips_through_json(self, two_candidates: Run) -> None:
        """A card that cannot be written to disk is not an artefact."""
        text = json.dumps(two_candidates.card().to_json_dict(), ensure_ascii=False)
        assert json.loads(text)["contracts_version"] == CONTRACTS_VERSION

    def test_the_schema_rejects_a_card_missing_the_mandated_label(
        self, two_candidates: Run
    ) -> None:
        """HĐ-9.3's label became a field at 2.2.0 exactly so that leaving
        it out is a validation error rather than an unremarkable card."""
        validator = Draft202012Validator(json.loads(CARD_SCHEMA_PATH.read_text(encoding="utf-8")))
        payload = two_candidates.card().to_json_dict()
        del payload["decision_mode_label"]
        assert list(validator.iter_errors(payload))


class TestWhatTheCardMaySay:
    def test_it_carries_the_mandated_mode_sentence(self, two_candidates: Run) -> None:
        assert two_candidates.card().decision_mode_label == (
            "Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được"
        )

    def test_pareto_is_uncertain_until_that_analysis_runs(self, two_candidates: Run) -> None:
        """HĐ-10.1's own name for "not enough data to conclude". Printing
        PARETO_FRONTIER here would assert something never checked."""
        assert two_candidates.card().pareto_label == "UNCERTAIN_DOMINANCE"

    def test_the_runner_up_is_not_promoted_to_alternative(self, two_candidates: Run) -> None:
        """HĐ-12: ``alternative`` may only be a PARETO_FRONTIER candidate.
        Second place on the ranking is a different claim."""
        card = two_candidates.card()
        assert card.alternative is None
        assert two_candidates.recommendation.runner_up_id

    def test_unmeasured_stability_is_null_not_zero(self, two_candidates: Run) -> None:
        """Null reads as "not measured"; a default reads as "measured and
        fine", and nobody downstream can tell those apart."""
        evidence = two_candidates.card().to_json_dict()["evidence"]
        assert evidence["weight_stability_margin"] is None
        assert evidence["anchor_stability"] is None
        assert evidence["robustness_margin"] is None

    def test_evidence_comes_from_the_paired_comparison(self, two_candidates: Run) -> None:
        comparison = two_candidates.recommendation.comparison
        evidence = two_candidates.card().evidence
        assert evidence.delta_u_vs_second == comparison.delta_median
        assert evidence.ci95 == comparison.ci95
        assert evidence.n_episodes == comparison.n_episodes == 30

    def test_a_fresh_card_is_always_pending(self, two_candidates: Run) -> None:
        """HĐ-14: approval is a human act; a builder that could stamp
        APPROVED would be a path around the self-approval ban."""
        assert two_candidates.card().approval.status == "PENDING"
        assert two_candidates.card().approval.by is None

    def test_the_g4_caveat_travels_on_every_card(self, two_candidates: Run) -> None:
        """HĐ-7.2's sim-only reservation, printed verbatim."""
        gates = two_candidates.card().to_json_dict()["gates"]
        assert all(
            row["G4"]["caveat"] == "G4 mới qua vòng sàng lọc — chưa xác nhận trên bo mạch đích"
            for row in gates
        )
        assert "verified_on_target" not in json.dumps(gates)

    def test_the_card_says_nothing_banned(self, two_candidates: Run) -> None:
        """§17 ban 10, on the whole document rather than field by field."""
        assert_no_banned_language(two_candidates.card().to_json_dict())

    def test_eliminated_candidates_stay_on_the_card(self) -> None:
        """HĐ-10.1: nobody disappears from the report. The most useful row
        is usually the fastest candidate being thrown out at a gate."""
        fast_but_blind = candidate(
            params={"astar": {"heuristic": "chebyshev"}},
            observation_requirements=["lidar_2d", "human_state_estimates"],
        )
        run = Run(
            [
                (candidate(), {"p99_latency_ms": 20.0}),
                (candidate(params={"astar": {"heuristic": "manhattan"}}), {"p99_latency_ms": 26.0}),
                (fast_but_blind, {"p99_latency_ms": 9.0}),
            ]
        )
        rows = {row["candidate_id"]: row for row in run.card().to_json_dict()["gates"]}
        assert fast_but_blind.candidate_id in rows
        assert rows[fast_but_blind.candidate_id]["G6"] == "fail"

    def test_scope_is_computed_from_the_data_not_the_wish(self) -> None:
        """HĐ-2.2: one mission can never support a deployment claim, and
        a robust claim additionally needs a neighborhood run."""
        single = Run(
            [
                (candidate(), {"p99_latency_ms": 12.0}),
                (candidate(params={"astar": {"heuristic": "manhattan"}}), {"p99_latency_ms": 45.0}),
            ],
            task_profile=make_profile(
                constraints=dict(FAST_CONSTRAINTS), claim_level="robust_deployment"
            ),
        )
        assert single.card().recommendation_scope == "MISSION_LEVEL"


class TestWhatTheCardRefuses:
    def test_a_candidate_that_failed_a_gate_cannot_be_recommended(self) -> None:
        """A gate is not a low score to be outweighed (HĐ-7).

        Here the leader on utility is also the one that collided, which
        is precisely the case a single blended score would get wrong.
        """
        colliding = candidate()
        clean = candidate(params={"astar": {"heuristic": "manhattan"}})
        run = Run([(colliding, {"p99_latency_ms": 9.0}), (clean, {"p99_latency_ms": 40.0})])
        broken = run.gate_reports[colliding.candidate_id].model_copy(
            update={
                "g2": run.gate_reports[colliding.candidate_id].g2.model_copy(
                    update={"result": "fail", "observed_collisions": 2}
                )
            }
        )
        run.gate_reports[colliding.candidate_id] = broken
        with pytest.raises(CardError, match="cannot be recommended"):
            run.card()

    def test_a_scored_candidate_with_no_gate_row_is_refused(self, two_candidates: Run) -> None:
        """Gates run before scoring; the reverse order is a bug that would
        otherwise produce a perfectly plausible card."""
        two_candidates.gate_reports.pop(two_candidates.recommendation.runner_up_id)
        with pytest.raises(CardError, match="no gate report"):
            two_candidates.card()

    def test_a_recommendation_outside_the_field_is_refused(self, two_candidates: Run) -> None:
        two_candidates.recommendation = two_candidates.recommendation.model_copy(
            update={"recommended_id": "deadbeefcafe"}
        )
        with pytest.raises(CardError, match="no evidence"):
            two_candidates.card()


class TestStabilityFields:
    """HĐ-11.5's three ``evidence`` fields, and the one way they can lie:
    by describing a different run than the card they sit on."""

    def test_they_stay_null_when_no_sweep_was_run(self, two_candidates: Run) -> None:
        """HĐ-12's own reading: null means "not measured". A default
        number would read as "measured, and fine"."""
        evidence = two_candidates.card().to_json_dict()["evidence"]
        assert evidence["weight_stability_margin"] is None
        assert evidence["anchor_stability"] is None
        assert evidence["robustness_margin"] is None

    def test_a_sweep_is_printed_when_it_was_run(self, two_candidates: Run) -> None:
        scored = ScoredField.from_survivors(
            [item.candidate for item in two_candidates.evidence],
            two_candidates.metrics_by_candidate,
            two_candidates.contexts,
            {item.candidate_id: True for item in two_candidates.evidence},
        )
        sweep = weight_stability(scored, two_candidates.anchors, two_candidates.settings)
        # The fixture's two candidates differ only in latency, so this
        # sweep is a real one; what matters here is that it reaches the
        # card rather than what value it takes.
        card = two_candidates.card(weight_stability=sweep)
        assert card.to_json_dict()["evidence"]["weight_stability_margin"] == sweep.margin

    def test_a_sweep_from_another_run_is_refused(self, two_candidates: Run) -> None:
        """The failure this guard exists for: a margin measured for a
        different field printed as if it described this one. Null reads
        as "not measured"; a wrong number reads as fact."""
        foreign = WeightStability(recommended_id="deadbeefcafe", margin=0.42, nearest_flip=None)
        with pytest.raises(CardError, match="cannot be carried onto another"):
            two_candidates.card(weight_stability=foreign)

    def test_the_same_guard_covers_the_anchor_sweep(self, two_candidates: Run) -> None:
        foreign = AnchorStability(recommended_id="deadbeefcafe", changed_at=(), sweep=0.10)
        with pytest.raises(CardError, match="cannot be carried onto another"):
            two_candidates.card(anchor_stability=foreign)


class TestParetoOnTheCard:
    """HĐ-10.1 and HĐ-12: the label, and the one field it gates."""

    def test_without_the_analysis_nothing_is_claimed(self, two_candidates: Run) -> None:
        """``UNCERTAIN_DOMINANCE`` is HĐ-10.1's own name for "not enough
        data to conclude", which is exactly right when the analysis did
        not run. ``alternative`` stays null for the same reason."""
        card = two_candidates.card()
        assert card.pareto_label == "UNCERTAIN_DOMINANCE"
        assert card.alternative is None

    def test_the_label_comes_from_the_analysis(self, two_candidates: Run) -> None:
        report = label_field(two_candidates.evidence, seed=11)
        card = two_candidates.card(pareto=report)
        assert card.pareto_label == report.label_of(card.recommended.candidate_id)

    def test_the_alternative_is_a_frontier_candidate(self, two_candidates: Run) -> None:
        report = label_field(two_candidates.evidence, seed=11)
        card = two_candidates.card(pareto=report)
        if card.alternative is not None:
            assert report.label_of(card.alternative.candidate_id) == "PARETO_FRONTIER"
            assert card.alternative.candidate_id != card.recommended.candidate_id

    def test_a_dominated_leader_cannot_be_recommended(self, two_candidates: Run) -> None:
        """The failure this guard exists for: the weighted sum puts a
        candidate on top that some rival beats on every objective at
        once. That recommendation is an artefact of the weights, and the
        card would be handing it over as advice (HĐ-10.1)."""
        winner = two_candidates.recommendation.recommended_id
        report = label_field(two_candidates.evidence, seed=11)
        forged = report.model_copy(update={"labels": {**report.labels, winner: "LIKELY_DOMINATED"}})
        with pytest.raises(CardError, match="dominated by"):
            two_candidates.card(pareto=forged)

    def test_an_unlabelled_candidate_is_refused(self, two_candidates: Run) -> None:
        """HĐ-10.1: nobody disappears from the report."""
        report = label_field(two_candidates.evidence, seed=11)
        dropped = report.model_copy(
            update={
                "labels": {
                    cid: label
                    for cid, label in report.labels.items()
                    if cid != two_candidates.recommendation.runner_up_id
                }
            }
        )
        with pytest.raises(ParetoError, match="carry no Pareto label"):
            two_candidates.card(pareto=dropped)


class TestManifest:
    def test_it_records_the_bootstrap_seed(self, two_candidates: Run) -> None:
        """Added at 2.2.0. Without it two people running this manifest get
        two different confidence intervals, and that difference is not
        wall-clock time — so HĐ-13's own acceptance test could not pass.
        """
        manifest = two_candidates.manifest()
        assert manifest.bootstrap == {"seed": 11, "n_resamples": 1000}

    def test_it_records_the_thresholds_that_produced_the_verdicts(
        self, two_candidates: Run
    ) -> None:
        """Added at 6.4.0, and the reason is the mirror image of
        ``sensor_noise``'s.

        ``episode_context_id`` hashes neither the noise nor the
        constraints (HĐ-3.1), but what follows from that differs.
        Changing the noise changes the **world**, so the episodes
        recorded before it belong to a different world and the deployment
        needs a new id. Changing a constraint changes the **verdict**,
        and the episodes stay exactly as valid — they are simply judged
        by another ruler.

        So a constraint may be edited in place, and the manifest is then
        the only thing standing between two cards that disagree and
        nobody able to say why: the same profile id under
        ``success_rate_min`` 0.95 and 1.00 would otherwise produce
        byte-identical manifests beside different gate tables.
        """
        manifest = two_candidates.manifest()
        assert manifest.constraints is not None
        assert manifest.constraints.success_rate_min > 0
        assert manifest.constraints.collision_probability_max > 0
        # And it survives serialisation, which is the form a rebuild
        # actually receives.
        assert "success_rate_min" in manifest.to_json_dict()["constraints"]

    def test_the_manifest_cannot_be_built_without_them(self) -> None:
        """Required, not optional-with-a-default. An optional field that
        is always null for the wrong reason is exactly how ``manifest``
        itself came to be stored as null on every ranked API run — the
        column existed, its nullability was tested, and it was empty."""
        from planbench_decision.card import Manifest

        assert Manifest.model_fields["constraints"].is_required()

    def test_it_records_the_anchor_version(self, two_candidates: Run) -> None:
        """HĐ-8.3 law 3: a recommendation computed under unknown anchors
        cannot be rebuilt."""
        assert two_candidates.manifest().anchor_config_version == "v1.2"

    def test_it_records_the_conditions_not_just_their_ids(self, two_candidates: Run) -> None:
        """HĐ-13's acceptance test: hand somebody the manifest and they
        rebuild the card.

        Ids alone cannot do that. ``episode_context_id`` is a hash of the
        conditions (HĐ-3.1) and hashes do not invert, so a manifest of
        ids proves *which* episodes ran but leaves a rebuild with no
        mission and no seed to recompute metrics from. That gap was
        invisible while the ``EpisodeContext`` objects were still in
        memory, which is every run the slice does in one process.
        """
        manifest = two_candidates.manifest()
        contexts = manifest.episode_contexts["evaluation"]
        assert len(contexts) == 30
        assert manifest.episode_contexts["neighborhood"] == ()
        # The ids are still there, derived rather than stored twice.
        assert manifest.context_ids("evaluation") == two_candidates.evidence[0].contexts
        # ...and each record carries what a rebuild actually needs.
        assert {context.mission_id for context in contexts} == {"m1"}
        assert sorted(context.seed for context in contexts) == list(range(30))

    def test_a_manifest_without_the_records_is_refused(self, two_candidates: Run) -> None:
        """Passing the scored ids but not their conditions used to be the
        normal case; it is now the failure the builder names."""
        with pytest.raises(CardError, match="no context record"):
            two_candidates.manifest(evaluation_contexts=two_candidates.contexts[:5])

    def test_the_record_order_is_stable(self, two_candidates: Run) -> None:
        """HĐ-13: a rebuild has to produce the same file byte for byte,
        which the caller's iteration order would not guarantee."""
        shuffled = list(reversed(two_candidates.contexts))
        assert (
            two_candidates.manifest(evaluation_contexts=shuffled).to_json_dict()
            == two_candidates.manifest().to_json_dict()
        )

    def test_it_lists_eliminated_candidates_too(self) -> None:
        """A rebuild has to reproduce the gate table, and a candidate
        thrown out at G6 is part of the result."""
        blind = candidate(
            params={"astar": {"heuristic": "chebyshev"}},
            observation_requirements=["lidar_2d", "human_state_estimates"],
        )
        run = Run(
            [
                (candidate(), {"p99_latency_ms": 12.0}),
                (candidate(params={"astar": {"heuristic": "manhattan"}}), {"p99_latency_ms": 45.0}),
                (blind, {"p99_latency_ms": 9.0}),
            ]
        )
        assert blind.candidate_id in run.manifest().candidates

    def test_it_carries_the_host_the_comparison_assumes(self, two_candidates: Run) -> None:
        """HĐ-7.4: one machine, one allocation, one thread count."""
        host = two_candidates.manifest().benchmark_host
        assert (host.cores_allocated, host.threads) == (4, 1)

    def test_two_builds_of_one_run_agree_everywhere_but_the_clock(
        self, two_candidates: Run
    ) -> None:
        """HĐ-13's acceptance criterion, as far as this layer can test it:
        the same inputs give the same manifest, and ``created_at`` is the
        only field allowed to move."""
        first = two_candidates.manifest().to_json_dict()
        second = two_candidates.manifest().to_json_dict()
        assert first == second

        later = two_candidates.manifest()
        moved = later.model_copy(
            update={"created_at": datetime(2026, 8, 11, 4, 0, tzinfo=UTC)}
        ).to_json_dict()
        assert {k: v for k, v in moved.items() if k != "created_at"} == {
            k: v for k, v in first.items() if k != "created_at"
        }

    def test_candidates_scored_over_different_sets_are_refused(self) -> None:
        """The manifest must not record an evaluation set that only some
        of the candidates actually ran."""
        a = candidate()
        b = candidate(params={"astar": {"heuristic": "manhattan"}})
        run = Run([(a, {"p99_latency_ms": 12.0}), (b, {"p99_latency_ms": 45.0})])
        shortened = run.evidence[1].model_copy(
            update={
                "episode_objectives": dict(list(run.evidence[1].episode_objectives.items())[:10])
            }
        )
        run.evidence[1] = shortened
        with pytest.raises(CardError, match="different context sets"):
            run.manifest()


class TestReproducibility:
    def test_the_same_inputs_give_the_same_card(self, two_candidates: Run) -> None:
        """HĐ-15.1 criterion 2 asks for six decimals; identical JSON is
        the stronger statement."""
        assert two_candidates.card().to_json_dict() == two_candidates.card().to_json_dict()

    def test_the_gate_table_order_does_not_depend_on_rank(self) -> None:
        """Sorted by id, so two candidates that tie cannot swap rows
        between two builds of the same run."""
        run = Run(
            [
                (candidate(), {"p99_latency_ms": 25.0}),
                (candidate(params={"astar": {"heuristic": "manhattan"}}), {"p99_latency_ms": 25.0}),
            ]
        )
        ids = [row["candidate_id"] for row in run.card().to_json_dict()["gates"]]
        assert ids == sorted(ids)
