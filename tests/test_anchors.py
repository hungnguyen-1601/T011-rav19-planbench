"""Anchors and normalisation (CONTRACTS HĐ-8).

The formula is three lines; the tests are about the two numbers fed into
it, because where ``good`` and ``bad`` come from decides the ranking as
surely as the weights do.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from task_profile_fakes import constraints, hardware, make_profile

from planbench_decision.anchors import (
    DEFAULT_ANCHORS_PATH,
    Anchor,
    AnchorError,
    AnchorSet,
    load_anchors,
    u,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def anchor_set(**anchors: dict[str, object]) -> AnchorSet:
    return AnchorSet(
        version="test",
        anchors={
            name: Anchor.model_validate(value)  # type: ignore[arg-type]
            for name, value in anchors.items()
        },
    )


class TestFormula:
    def test_higher_is_better(self) -> None:
        assert u(1.00, good=1.0, bad=0.65) == pytest.approx(1.0)
        assert u(0.65, good=1.0, bad=0.65) == pytest.approx(0.0)
        assert u(0.825, good=1.0, bad=0.65) == pytest.approx(0.5)

    def test_lower_is_better_needs_no_special_case(self) -> None:
        """The order of good/bad encodes the direction (HĐ-8.1)."""
        assert u(10.0, good=10.0, bad=50.0) == pytest.approx(1.0)
        assert u(50.0, good=10.0, bad=50.0) == pytest.approx(0.0)
        assert u(30.0, good=10.0, bad=50.0) == pytest.approx(0.5)

    def test_clipped_at_both_ends(self) -> None:
        """Beating the anchor is not extra credit: u stays in [0, 1] so
        one metric cannot outvote the weights."""
        assert u(1.5, good=1.0, bad=0.65) == 1.0
        assert u(0.1, good=1.0, bad=0.65) == 0.0

    def test_degenerate_scale_is_refused(self) -> None:
        with pytest.raises(AnchorError, match="good == bad"):
            u(1.0, good=0.5, bad=0.5)

    def test_non_finite_measurement_is_refused(self) -> None:
        with pytest.raises(AnchorError, match="non-finite"):
            u(float("nan"), good=1.0, bad=0.0)


class TestProjectAnchorFile:
    def test_ships_at_the_contract_path(self) -> None:
        assert DEFAULT_ANCHORS_PATH == REPO_ROOT / "contracts" / "metric_anchors.yaml"
        assert DEFAULT_ANCHORS_PATH.is_file()

    def test_loads_and_is_versioned(self) -> None:
        """HĐ-13 puts anchor_config_version in every manifest: a
        recommendation computed under unknown anchors cannot be rebuilt."""
        anchors = load_anchors()
        assert anchors.version == "v1.2"

    def test_resolves_against_the_contract_profile(self) -> None:
        resolved = load_anchors().resolve(make_profile())
        assert resolved.anchors["success_rate"] == (1.0, 0.95)
        assert resolved.anchors["p99_latency_ms"] == (10.0, 50.0)
        assert resolved.anchors["min_clearance"] == pytest.approx((0.26, 0.0))
        assert resolved.anchors["memory_estimate_mb"] == pytest.approx((819.25, 3277.0))

    def test_clearance_is_anchored_on_the_surface_scale(self) -> None:
        """HĐ-8.2. ``clearance_m`` is measured from the robot's surface —
        ``distance - robot_radius - obstacle_radius`` — so 0.0 *is* the
        collision boundary rather than a number anybody picked.

        Anchor v1.0 used ``radius * 1.05`` / ``radius * 2.0``, the right
        pair on a centre-to-obstacle scale, one radius away from this
        one. On the reference warehouse the two scales do not merely
        disagree: a 0.52 m robot in a 0.68 m aisle has 0.04 m of surface
        clearance, which lands under a ``bad`` of 0.273 on every episode,
        so ``U_S`` was a constant 0 for every candidate and the safety
        objective decided nothing at weight 0.10.
        """
        resolved = load_anchors().resolve(make_profile())
        good, bad = resolved.anchors["min_clearance"]
        assert bad == 0.0
        assert good == pytest.approx(make_profile().robot.radius)

        # The aisle that scored 0.00 under v1.0 now scores on-scale.
        assert resolved.u("min_clearance", 0.04) == pytest.approx(0.04 / 0.26, abs=1e-9)
        assert resolved.u("min_clearance", 0.04) > 0.0
        # Touching an obstacle still scores 0, and so does being inside it.
        assert resolved.u("min_clearance", 0.0) == 0.0
        assert resolved.u("min_clearance", -0.10) == 0.0

    def test_reproduces_the_contract_worked_example(self) -> None:
        """§6.2 scores K1 at U_R = 0.34 with success_rate 96.7% against a
        95% requirement. If this drifts, the anchors no longer mean what
        the contract says they mean."""
        resolved = load_anchors().resolve(make_profile())
        assert resolved.u("success_rate", 0.967) == pytest.approx(0.34, abs=0.005)

    def test_thresholds_follow_the_deployment_not_the_file(self) -> None:
        """The point of the ${...} references: a customer who demands
        99% gets scored on the surplus over 99%, from the same file."""
        strict = make_profile(constraints=constraints(success_rate_min=0.99))
        resolved = load_anchors().resolve(strict)
        assert resolved.anchors["success_rate"] == (1.0, 0.99)
        assert resolved.u("success_rate", 0.995) == pytest.approx(0.5)

    def test_gate_metrics_track_hardware_too(self) -> None:
        small_board = make_profile(
            hardware=hardware(
                total_ram_mb=4096,
                ram_budget_breakdown={
                    "os_and_middleware_mb": 1024,
                    "perception_stack_mb": 1024,
                    "localization_mapping_mb": 512,
                    "logging_and_reserve_mb": 512,
                },
                available_ram_mb=1024,
            )
        )
        resolved = load_anchors().resolve(small_board)
        assert resolved.anchors["memory_estimate_mb"] == pytest.approx((256.0, 1024.0))


class TestLawTwoGatedMetrics:
    """HĐ-8.3 law 2 — the failure it exists for: this file and the
    deployment drifting apart with nothing to show it."""

    def test_hardcoded_bad_on_a_gated_metric_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="feasibility gate"):
            anchor_set(success_rate={"good": 1.0, "bad": 0.90})

    def test_every_gated_metric_is_covered(self) -> None:
        for metric in ("success_rate", "p99_latency_ms", "memory_estimate_mb"):
            with pytest.raises(ValidationError, match="feasibility gate"):
                anchor_set(**{metric: {"good": 1.0, "bad": 0.5}})

    def test_ungated_metrics_may_use_literals(self) -> None:
        """Path efficiency has no gate; 0.65 comes from the physics of
        the task, not from a threshold anyone declared."""
        assert anchor_set(path_efficiency={"good": 1.0, "bad": 0.65}).anchors["path_efficiency"]

    def test_shipped_file_obeys_the_law(self) -> None:
        anchors = load_anchors()
        for metric in ("success_rate", "p99_latency_ms", "memory_estimate_mb"):
            assert anchors.anchors[metric].references("bad")


class TestLawFourDeclaredScales:
    """HĐ-8.3 law 4 — money has no physics to anchor against.

    Every other anchor in the shipped file gets its scale from outside
    the candidate set: the geometry of the robot, the physics of the
    route, or a threshold the deployment declared. There is no fact that
    makes one currency unit per mission expensive. A literal here would
    be the platform picking the customer's budget and then grading the
    customer against it — law 1's failure in a different costume.
    """

    def test_a_literal_money_bad_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="measured in money"):
            anchor_set(engineering_cost_per_mission={"good": 0.0, "bad": 5.0})

    def test_the_shipped_file_obeys_it(self) -> None:
        assert load_anchors().anchors["engineering_cost_per_mission"].references("bad")

    def test_a_site_that_declares_a_budget_gets_the_scale(self) -> None:
        resolved = load_anchors().resolve(
            make_profile(constraints=constraints(cost_per_mission_max=2.0))
        )
        assert resolved.anchors["engineering_cost_per_mission"] == (0.0, 2.0)
        assert resolved.u("engineering_cost_per_mission", 0.5) == pytest.approx(0.75)


class TestUndeclaredOptionalReferences:
    """One anchor file serves every deployment, so an anchor whose scale
    a given site never declared cannot be fatal to that site.

    It is not silently dropped either: the reason is kept, and scoring
    the metric names the missing declaration. The distinction that makes
    this safe is between a field the profile *has and left empty* and a
    field that does not exist — the second is a typo and stays fatal.
    """

    def test_a_technical_site_loads_the_file_without_declaring_money(self) -> None:
        resolved = load_anchors().resolve(make_profile())
        assert "engineering_cost_per_mission" not in resolved.anchors
        assert "engineering_cost_per_mission" in resolved.unresolved
        # Every other anchor resolved normally.
        assert resolved.anchors["success_rate"] == (1.0, 0.95)

    def test_scoring_it_names_the_missing_declaration(self) -> None:
        resolved = load_anchors().resolve(make_profile())
        with pytest.raises(AnchorError, match="cost_per_mission_max"):
            resolved.u("engineering_cost_per_mission", 0.5)

    def test_a_misspelled_field_is_still_fatal(self) -> None:
        """The failure this must not be confused with: quietly treating a
        typo as "this site declined to declare it"."""
        with pytest.raises(AnchorError, match="does not have"):
            anchor_set(
                path_efficiency={"good": 1.0, "bad": "${constraints.cost_per_mision_max}"}
            ).resolve(make_profile())

    def test_the_reason_survives_the_sensitivity_sweep(self) -> None:
        swept = load_anchors().resolve(make_profile()).scaled(1.10)
        with pytest.raises(AnchorError, match="cost_per_mission_max"):
            swept.u("engineering_cost_per_mission", 0.5)


class TestReferenceResolution:
    def test_plain_reference(self) -> None:
        resolved = anchor_set(
            success_rate={"good": 1.0, "bad": "${constraints.success_rate_min}"}
        ).resolve(make_profile())
        assert resolved.anchors["success_rate"][1] == 0.95

    def test_multiplied_reference(self) -> None:
        resolved = anchor_set(
            min_clearance={"good": "${robot.radius * 2.0}", "bad": "${robot.radius * 1.05}"}
        ).resolve(make_profile())
        assert resolved.anchors["min_clearance"] == pytest.approx((0.52, 0.273))

    def test_divided_reference(self) -> None:
        resolved = anchor_set(path_efficiency={"good": 1.0, "bad": "${robot.radius / 2}"}).resolve(
            make_profile()
        )
        assert resolved.anchors["path_efficiency"][1] == pytest.approx(0.13)

    def test_unknown_field_is_refused(self) -> None:
        with pytest.raises(AnchorError, match="does not have"):
            anchor_set(
                path_efficiency={"good": 1.0, "bad": "${constraints.success_rate_maximum}"}
            ).resolve(make_profile())

    def test_reference_to_a_block_is_refused(self) -> None:
        """A whole constraints block is not a number, and stringifying
        it would produce an anchor nobody can read."""
        with pytest.raises(AnchorError, match="not a number"):
            anchor_set(path_efficiency={"good": 1.0, "bad": "${constraints}"}).resolve(
                make_profile()
            )

    def test_arbitrary_expressions_are_not_evaluated(self) -> None:
        """The grammar is a field lookup and at most one multiply. Anchor
        files are user input; running them through eval would make a
        YAML upload arbitrary code execution."""
        for text in (
            "${__import__('os').system('echo hi')}",
            "${robot.radius + hardware.available_ram_mb}",
            "${robot.radius * 2 * 3}",
            "$robot.radius",
        ):
            with pytest.raises(AnchorError):
                anchor_set(path_efficiency={"good": 1.0, "bad": text}).resolve(make_profile())

    def test_private_attribute_is_refused(self) -> None:
        with pytest.raises(AnchorError):
            anchor_set(path_efficiency={"good": 1.0, "bad": "${_abc}"}).resolve(make_profile())


class TestFileValidation:
    def test_unknown_metric_name_is_refused(self) -> None:
        """A typo would sit in the file forever, scoring nothing, while
        the metric it meant to anchor silently has no scale."""
        with pytest.raises(ValidationError, match="no metric this system computes"):
            anchor_set(path_efficency={"good": 1.0, "bad": 0.65})

    def test_missing_version_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "anchors.yaml"
        path.write_text(
            "metric_anchors:\n  path_efficiency: {good: 1.0, bad: 0.65}\n", encoding="utf-8"
        )
        with pytest.raises(AnchorError, match="no anchor version"):
            load_anchors(path)

    def test_missing_file_is_named(self, tmp_path: Path) -> None:
        with pytest.raises(AnchorError, match="not found"):
            load_anchors(tmp_path / "nope.yaml")

    def test_wrong_top_level_shape_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "anchors.yaml"
        path.write_text("anchors: {}\n", encoding="utf-8")
        with pytest.raises(AnchorError, match="metric_anchors"):
            load_anchors(path)

    def test_extra_key_inside_an_anchor_is_refused(self) -> None:
        with pytest.raises(ValueError):
            anchor_set(path_efficiency={"good": 1.0, "bad": 0.65, "weight": 0.3})

    def test_resolution_collapsing_the_scale_is_refused(self) -> None:
        """A reference that happens to equal the other end leaves the
        metric with no scale, and every candidate scores the same."""
        with pytest.raises(AnchorError, match="no scale"):
            anchor_set(
                success_rate={"good": 0.95, "bad": "${constraints.success_rate_min}"}
            ).resolve(make_profile())


class TestSensitivitySweep:
    def test_scaling_moves_both_ends(self) -> None:
        """HĐ-8.3 law 3: the question is whether the scale was chosen
        well, not whether one end of it was."""
        resolved = load_anchors().resolve(make_profile())
        shifted = resolved.scaled(1.10)
        good, bad = resolved.anchors["p99_latency_ms"]
        assert shifted.anchors["p99_latency_ms"] == pytest.approx((good * 1.1, bad * 1.1))

    def test_version_records_the_shift(self) -> None:
        """A card produced under perturbed anchors must never be
        mistaken for one produced under the declared anchors."""
        resolved = load_anchors().resolve(make_profile())
        assert resolved.scaled(1.10).version == "v1.2±+10%"
        assert resolved.scaled(0.90).version == "v1.2±-10%"

    def test_a_physical_floor_does_not_move_under_the_sweep(self) -> None:
        """``min_clearance.bad`` is 0.0 — the collision boundary — so
        scaling leaves it alone and only ``good`` moves.

        That is the intended reading of HĐ-8.3 law 3 rather than a gap in
        it: the sweep asks whether the *chosen* end of a scale was chosen
        well, and on this metric only ``good`` was chosen. Perturbing the
        floor would be perturbing geometry.
        """
        resolved = load_anchors().resolve(make_profile())
        good, bad = resolved.scaled(1.10).anchors["min_clearance"]
        assert bad == 0.0
        assert good == pytest.approx(resolved.anchors["min_clearance"][0] * 1.10)

    def test_non_positive_factor_is_refused(self) -> None:
        with pytest.raises(AnchorError, match="must be positive"):
            load_anchors().resolve(make_profile()).scaled(0.0)


class TestUnanchoredMetric:
    def test_scoring_an_unanchored_metric_is_refused(self) -> None:
        """Defaulting to 0 or 1 would let a metric enter the utility with
        a scale nobody chose."""
        resolved = load_anchors().resolve(make_profile())
        with pytest.raises(AnchorError, match="no anchor for"):
            resolved.u("smoothness", 0.3)
