"""The visible calibration suite — E5.

Two cases per family: the one where the mechanism is there, and the one
where the surface looks the same and it is not. Twelve cases is not a
gate and is not pretending to be one; it is the set the AI team
integrates against, checks its plumbing on, and argues about the metric
definitions with before anybody agrees a threshold.

**Every case here is visible.** The hidden subset is a different suite,
held by the platform, opened once per bundle version, and it is not in
this repository. A visible case an analyst has seen is a case it can be
fitted to, which is exactly why calibration and grading are different
sets.

**The packet references do not resolve yet.** They name planted runs
that need the E4.5 sidecar to record planning inputs as they happen.
The suite is the format and the answers; producing the runs is the next
piece of work, and :data:`~planbench_explanation.golden.OFFICIAL_GOLDEN_READY`
keeps anyone from calling this a gate in the meantime.

The negative-control family deserves its own note. Its cases are runs
where two candidates differ and *nothing* mechanistic explains it — the
difference is noise, or a preference-profile artefact. An analyst that
finds a mechanism there is doing the thing this platform is built to
stop, and finding nothing to say is the correct answer twice over.
"""

from __future__ import annotations

from planbench_explanation.golden import (
    ExpectedFinding,
    GoldenSuite,
    PlantedCase,
)

VISIBLE_SUITE_VERSION = "calibration-0.1.0"

_INFLATION = (
    PlantedCase(
        case_id="inflation-001",
        family="inflation_gap_closure",
        variant="positive",
        packet_ref="fixtures/golden/visible/inflation-001/packet.json",
        expected_findings=(
            ExpectedFinding(
                proposition_type="geometric_infeasibility", subject="costmap_inflation"
            ),
        ),
        expected_checker_requests=("get_map_region_features", "gap_vs_footprint"),
        forbidden_claims=("complete_utility_attribution", "universal_algorithm_superiority"),
        rationale=(
            "Inflation radius plus footprint exceeds the measured aisle width by 6 cm. "
            "The mechanism is real, checkable, and about the inflation parameter rather "
            "than the planner that obeyed it."
        ),
    ),
    PlantedCase(
        case_id="inflation-002",
        family="inflation_gap_closure",
        variant="near_boundary",
        packet_ref="fixtures/golden/visible/inflation-002/packet.json",
        expect_abstention=True,
        expected_checker_requests=("get_map_region_features", "gap_vs_footprint"),
        forbidden_claims=("geometric_infeasibility",),
        rationale=(
            "The same aisle, 3 cm wider, so the passage clears. The detour is real and "
            "the geometry does not explain it — an analyst that proposes inflation here "
            "is pattern-matching on the shape of the case."
        ),
    ),
)

_DWA = (
    PlantedCase(
        case_id="dwa-001",
        family="dwa_local_minimum",
        variant="positive",
        packet_ref="fixtures/golden/visible/dwa-001/packet.json",
        expected_findings=(
            ExpectedFinding(
                proposition_type="local_minimum_entrapment", subject="local_controller"
            ),
        ),
        expected_checker_requests=("get_episode_observations", "get_replay_window"),
        forbidden_claims=("complete_utility_attribution",),
        rationale=(
            "The robot stalls in a concave pocket for eleven seconds with a clear global "
            "path available. The stall is the local controller's; saying so is a "
            "sighting, not a causal account of the run."
        ),
    ),
    PlantedCase(
        case_id="dwa-002",
        family="dwa_local_minimum",
        variant="negative",
        packet_ref="fixtures/golden/visible/dwa-002/packet.json",
        expect_abstention=True,
        expected_checker_requests=("get_episode_observations", "get_event_neighborhood"),
        forbidden_claims=("local_minimum_entrapment",),
        rationale=(
            "A stall of the same duration at the same place, caused by a moving obstacle "
            "the trace records crossing the corridor. The symptom is identical and the "
            "mechanism is not; the neighbourhood tool shows the difference."
        ),
    ),
)

_RRT = (
    PlantedCase(
        case_id="rrt-001",
        family="rrt_sample_starvation",
        variant="positive",
        packet_ref="fixtures/golden/visible/rrt-001/packet.json",
        expected_findings=(
            ExpectedFinding(
                proposition_type="sampling_budget_insufficiency", subject="global_planner"
            ),
        ),
        expected_checker_requests=("rrt_convergence",),
        forbidden_claims=("universal_algorithm_superiority", "complete_utility_attribution"),
        rationale=(
            "The corridor is found on four seeds of twelve at the configured budget and "
            "on eleven at four times the budget. Intermittency across seeds is the "
            "signature; a single failed episode is not."
        ),
    ),
    PlantedCase(
        case_id="rrt-002",
        family="rrt_sample_starvation",
        variant="must_abstain",
        packet_ref="fixtures/golden/visible/rrt-002/packet.json",
        expect_abstention=True,
        expected_checker_requests=("rrt_convergence",),
        forbidden_claims=("sampling_budget_insufficiency",),
        rationale=(
            "The same planner fails on every seed, which points at the query rather than "
            "the budget — and the run holds no planning inputs to replay, so the "
            "distinguishing check comes back not_checkable. The right answer is to say "
            "what is missing."
        ),
    ),
)

_LATENCY = (
    PlantedCase(
        case_id="latency-001",
        family="expansion_latency",
        variant="positive",
        packet_ref="fixtures/golden/visible/latency-001/packet.json",
        expected_findings=(
            ExpectedFinding(
                proposition_type="expansion_latency_association", subject="global_planner"
            ),
        ),
        expected_checker_requests=("latency_vs_expanded_nodes",),
        forbidden_claims=("candidate_latency_attribution", "complete_utility_attribution"),
        rationale=(
            "Replan ticks carrying large frontiers take proportionally longer. The "
            "association holds; the card caps it at associated, and an analyst that "
            "proposes candidate latency attribution has crossed the H4 gap."
        ),
    ),
    PlantedCase(
        case_id="latency-002",
        family="expansion_latency",
        variant="near_boundary",
        packet_ref="fixtures/golden/visible/latency-002/packet.json",
        expect_abstention=True,
        expected_checker_requests=("latency_vs_expanded_nodes",),
        forbidden_claims=("expansion_latency_association", "candidate_latency_attribution"),
        rationale=(
            "Latency spikes are present and expansions are flat across them — the spikes "
            "track the deployment's own load, which the platform cannot yet separate "
            "out. The packet's known unknowns block the attribution and the analyst "
            "should say so rather than reach for the planner."
        ),
    ),
)

_NEGATIVE = (
    PlantedCase(
        case_id="control-001",
        family="negative_control",
        variant="must_abstain",
        packet_ref="fixtures/golden/visible/control-001/packet.json",
        expect_abstention=True,
        expected_checker_requests=("get_objective_decomposition",),
        forbidden_claims=(
            "geometric_infeasibility",
            "local_minimum_entrapment",
            "sampling_budget_insufficiency",
            "expansion_latency_association",
        ),
        rationale=(
            "Two candidates, a ΔU of 0.004 with a CI straddling zero, no detections on "
            "either side. There is nothing to explain, and an explanation offered here "
            "is the failure mode this whole layer exists to prevent."
        ),
    ),
    PlantedCase(
        case_id="control-002",
        family="negative_control",
        variant="must_abstain",
        packet_ref="fixtures/golden/visible/control-002/packet.json",
        expect_abstention=True,
        expected_checker_requests=("get_objective_decomposition", "get_candidate_contrast"),
        forbidden_claims=(
            "component_specific_attribution",
            "universal_algorithm_superiority",
        ),
        rationale=(
            "A real difference produced entirely by the preference profile's weights, "
            "not by either stack: the same episodes under a different profile reverse "
            "the ranking. The contrast lattice isolates no axis."
        ),
    ),
)

_INSUFFICIENT = (
    PlantedCase(
        case_id="gap-001",
        family="insufficient_evidence",
        variant="must_abstain",
        packet_ref="fixtures/golden/visible/gap-001/packet.json",
        expect_abstention=True,
        expected_checker_requests=("get_known_unknowns",),
        forbidden_claims=("perception_attribution", "candidate_latency_attribution"),
        rationale=(
            "The difference is in perception cost, which the platform's accounting does "
            "not split between candidate and deployment. The packet declares the gap; "
            "an analyst that proposes the attribution anyway has ignored its only "
            "structured warning."
        ),
    ),
    PlantedCase(
        case_id="gap-002",
        family="insufficient_evidence",
        variant="must_abstain",
        packet_ref="fixtures/golden/visible/gap-002/packet.json",
        expect_abstention=True,
        expected_checker_requests=(),
        forbidden_claims=("geometric_infeasibility", "local_minimum_entrapment"),
        rationale=(
            "A run recorded before the trace address changed: no per-episode trace, so "
            "no detector output and no replay. Every mechanism check is unavailable, "
            "and saying which evidence is missing is the whole of the correct answer."
        ),
    ),
)

#: Twelve visible cases. Calibration, never a gate — see the module
#: docstring and :data:`~planbench_explanation.golden.OFFICIAL_GOLDEN_READY`.
VISIBLE_SUITE = GoldenSuite(
    suite_version=VISIBLE_SUITE_VERSION,
    visibility="visible",
    status="calibration",
    cases=(*_INFLATION, *_DWA, *_RRT, *_LATENCY, *_NEGATIVE, *_INSUFFICIENT),
    notes=(
        "Two variants per family: the mechanism, and the case that looks like it.",
        "Packet fixtures are planted runs and need the E4.5 sidecar before they exist.",
        "Seven of twelve expect abstention, which is deliberate — an analyst tuned on "
        "a suite where something is always wrong learns that something is always wrong.",
    ),
)
