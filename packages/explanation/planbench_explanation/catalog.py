"""The tool catalog, filled — one card per tool in the four classes — E5.

E0 defined what a card *is* and left the catalog empty except for the
one card its tests needed. This is the menu an external analyst actually
chooses from: sixteen tools across the four classes of design section
3.3, each declaring in typed form what it can establish, what it must
never be read as establishing, and which input pedigrees it accepts.

**A closed menu is the point.** The analyst is an LLM the platform does
not trust; the only actions it can take are requests for tools on this
list, and the only things its requests can establish are the
propositions these cards name. A tool that is not here cannot be asked
for, and a proposition no card supports cannot be promoted no matter
what any model says about it.

Three properties of this catalog are worth stating because they are
easy to lose in an edit:

**Most fact-query tools support nothing.** They return numbers, and a
number is not a verdict. ``get_objective_decomposition`` hands over the
ΔU decomposition; whether that decomposition means a component is to
blame is a question no fact query answers. Only two fact queries support
a proposition at all, both at ``observed``: reporting what a detector
saw, and reporting that two candidates differ on exactly one component.

**Evidence-navigation tools support nothing by construction** — the card
schema refuses a supported proposition on that class. They return
pointers: which episodes, which window, which segment. A pointer is
where to look, not what is true.

**``latency_vs_expanded_nodes`` is capped at ``associated`` while being
perfectly deterministic.** Counting expanded nodes and measuring tick
latency is arithmetic, and the arithmetic is exact. What it does not
show is that the expansions *caused* the latency rather than both
following from the same hard query. Determinism buys reproducibility,
not causality, and the cap is where that distinction is enforced instead
of hoped for.

The version is declared, not derived: a result names the menu it chose
from, and a claim adjudicated under ``1.0.0`` is not silently
re-adjudicated by a later menu.
"""

from __future__ import annotations

from planbench_explanation.tools import (
    ArgumentSpec,
    EvidencePolicy,
    MeasurementSpec,
    PropositionPolicy,
    ReferenceSpec,
    ToolCard,
    ToolCatalog,
    ToolIO,
    ToolPurpose,
)


def _argument(name: str, kind: str, description: str, *, required: bool = True) -> ArgumentSpec:
    return ArgumentSpec(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        required=required,
        description=description,
    )


_CANDIDATE = _argument("candidate_id", "string", "Which candidate's data to read.")
_PAIR = (
    _argument("candidate_a", "string", "First candidate of the compared pair."),
    _argument("candidate_b", "string", "Second candidate of the compared pair."),
)
_EPISODE = _argument(
    "episode_context_id",
    "string",
    "The paired episode context, the identity both candidates share.",
)
_REGION = _argument("region_id", "string", "A named region of the task map.")


def _measure(name: str, unit: str, description: str, *, required: bool = True) -> MeasurementSpec:
    return MeasurementSpec(
        name=name,
        unit=unit,  # type: ignore[arg-type]
        required=required,
        description=description,
    )


def _points_at(kind: str, description: str, *, required: bool = True) -> ReferenceSpec:
    return ReferenceSpec(
        kind=kind,  # type: ignore[arg-type]
        required=required,
        description=description,
    )


#: Bump MINOR when a card is added, MAJOR when an existing card's typed
#: policy changes. The version appears in every request and every
#: artifact header, so a change here is visible in the audit trail.
#:
#: **2.0.0** — E6a changed ``latency_vs_expanded_nodes`` from a
#: per-replan measurement to a per-episode one: different arguments,
#: different required evidence, different measurement names, a different
#: proposition. Leaving the version at 1.0.0 would have let a bundle
#: frozen against the old wire contract, and a gate decision recorded
#: for it, keep looking valid — which is precisely what the immutable
#: bundle exists to prevent. A contract is not edited in place.
#: ``gap_vs_footprint`` also moved to 2.0.0: it now compares a width
#: against a width, which changes the measurement names it returns.
#:
#: **3.1.0** — M1 adds ``get_candidate_measurements``: what a
#: candidate scored, which until now lived in the report and never
#: reached an analyst. A card added is a menu changed, so the version
#: moves and every bundle frozen against 3.0.0 needs a new gate.
#:
#: **3.0.0** — ``rrt_convergence`` reports a rate at **two** budgets
#: rather than one, because one rate cannot tell "the budget is too
#: small" from "the corridor is not there": both look like a low number.
#: Different measurement names, so a different wire contract, so a
#: different version.
TOOL_CATALOG_VERSION = "3.1.0"

_RECORDED = EvidencePolicy(allowed_input_provenance=("recorded",))
_RECORDED_OR_VERIFIED = EvidencePolicy(
    allowed_input_provenance=("recorded", "verified_reconstruction")
)
#: Replay of an old run cannot produce recorded inputs — the run predates
#: the sidecar. The card accepts the weaker pedigree and the provenance
#: ceiling then caps whatever it produces; refusing it outright would
#: mean no old run could ever be examined.
_REPLAYABLE = EvidencePolicy(
    allowed_input_provenance=("recorded", "verified_reconstruction", "reconstructed")
)


# --------------------------------------------------------------------------
# Fact-query — read what the run recorded. Ceiling ``observed``.
# --------------------------------------------------------------------------

OBJECTIVE_DECOMPOSITION = ToolCard(
    tool_id="get_objective_decomposition",
    tool_version="1.0.0",
    title="Read the paired ΔU decomposition for a candidate pair",
    tool_class="fact_query",
    purpose=ToolPurpose(
        does_not_verify={
            "complete_utility_attribution": (
                "The decomposition says how the weighted difference splits across "
                "objectives. It does not say which component of either stack produced "
                "that split, nor that the split accounts for the whole difference in "
                "outcome."
            )
        },
        notes=(
            "Returns the E1 waterfall: per-objective weight, mean Δ, contribution and "
            "marginal CI, plus both aggregation levels of the drill-down.",
        ),
    ),
    proposition_policy=PropositionPolicy(
        forbidden_inference_types=("complete_utility_attribution",),
        maximum_claim_level="observed",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("comparison_pair", "episode_decision_utility", "preference_profile"),
    io=ToolIO(
        arguments=(
            *_PAIR,
            _argument(
                "preference_profile",
                "string",
                "Which weight profile to decompose under; the run's own if omitted.",
                required=False,
            ),
        ),
        measurements=(
            _measure("delta_utility_mean", "ratio", "Paired mean ΔU over the episode set."),
            _measure("delta_utility_median", "ratio", "Paired median ΔU; not decomposable."),
            _measure("n_episodes", "count", "Paired episodes the decomposition covers."),
            _measure("contribution_u_r", "ratio", "Weighted contribution of reliability."),
            _measure("contribution_u_s", "ratio", "Weighted contribution of safety."),
            _measure("contribution_u_e", "ratio", "Weighted contribution of efficiency."),
            _measure("contribution_u_c", "ratio", "Weighted contribution of comfort."),
        ),
    ),
    failure_modes=("pair_not_comparable", "no_paired_episodes", "profile_unknown"),
)

EPISODE_OBSERVATIONS = ToolCard(
    tool_id="get_episode_observations",
    tool_version="1.0.0",
    title="Read the detector observations for an episode",
    tool_class="fact_query",
    purpose=ToolPurpose(
        verifies={
            "clearance_refusal": (
                "A detector saw the stack decline a passage on clearance grounds in "
                "this episode. This is the sighting, at the strength of a sighting."
            )
        },
        does_not_verify={
            "complete_utility_attribution": (
                "A detection describes what happened in one episode. It carries no "
                "share of the utility difference with it."
            ),
            "global_planner_attempt_attribution": (
                "Observing a refusal near a passage does not establish that the global "
                "planner routed the robot at that passage on purpose."
            ),
        },
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("clearance_refusal",),
        forbidden_inference_types=(
            "complete_utility_attribution",
            "global_planner_attempt_attribution",
        ),
        maximum_claim_level="observed",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("trace", "detector_version"),
    io=ToolIO(
        arguments=(_CANDIDATE, _EPISODE),
        measurements=(
            _measure("n_observations", "count", "Detection types that fired for this pairing."),
            _measure("episodes_seen", "count", "Episodes the detection appeared in."),
            _measure("episodes_total", "count", "Episodes it was looked for in."),
            _measure("prevalence", "ratio", "episodes_seen over episodes_total."),
        ),
        references=(_points_at("episode", "The episodes the detections fired in."),),
    ),
    failure_modes=("trace_unavailable", "episode_not_in_run"),
)

CANDIDATE_CONTRAST = ToolCard(
    tool_id="get_candidate_contrast",
    tool_version="1.0.0",
    title="Read the component lattice between two candidates",
    tool_class="fact_query",
    purpose=ToolPurpose(
        verifies={
            "component_specific_attribution": (
                "The two candidates differ in exactly one declared component and their "
                "recorded outcomes differ. That is an observation about a pair, not a "
                "demonstration that the component is responsible."
            )
        },
        does_not_verify={
            "universal_algorithm_superiority": (
                "A difference on one task profile under one preference profile says "
                "nothing about either stack in general."
            ),
            "complete_utility_attribution": (
                "Isolating an axis does not measure how much of the difference it accounts for."
            ),
        },
        notes=(
            "Returns the E3 lattice reading, which refuses to attribute in three of "
            "its four verdicts. Multi-axis pairs come back interaction_not_isolated.",
        ),
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("component_specific_attribution",),
        forbidden_inference_types=(
            "universal_algorithm_superiority",
            "complete_utility_attribution",
        ),
        maximum_claim_level="observed",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("candidate_components",),
    io=ToolIO(
        arguments=_PAIR,
        measurements=(
            _measure("n_findings", "count", "Lattice findings for this pair."),
            _measure(
                "n_differing_axes",
                "count",
                "Declared components the two candidates differ on; more than one and "
                "the reading refuses to attribute.",
            ),
        ),
    ),
    failure_modes=("components_not_declared", "candidate_not_in_run"),
)

MAP_REGION_FEATURES = ToolCard(
    tool_id="get_map_region_features",
    tool_version="1.0.0",
    title="Read measured geometry for a map region",
    tool_class="fact_query",
    purpose=ToolPurpose(
        does_not_verify={
            "global_planner_attempt_attribution": (
                "Measuring a passage says the passage is that wide. It does not say "
                "the planner ever routed the robot through it."
            )
        },
        notes=(
            "Passage width is reported only where the map bounds the route on both "
            "sides; a one-sided cross-section yields a lower bound, in a separate "
            "field, which cannot show a passage is too narrow.",
        ),
    ),
    proposition_policy=PropositionPolicy(
        forbidden_inference_types=("global_planner_attempt_attribution",),
        maximum_claim_level="observed",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("map_checksum", "region_geometry"),
    io=ToolIO(
        arguments=(
            _argument(
                "region_id",
                "string",
                "One named region; the whole route is measured when omitted.",
                required=False,
            ),
            _argument(
                "candidate_id",
                "string",
                "Measure along this candidate's route; the declared reference line if omitted.",
                required=False,
            ),
        ),
        measurements=(
            _measure(
                "narrowest_passage_m",
                "m",
                "Narrowest doubly-bounded cross-section along the route. Absent where "
                "the map never closes both sides.",
                required=False,
            ),
            _measure(
                "narrowest_lower_bound_m",
                "m",
                "Lower bound from one-sided cross-sections. Cannot show a passage is "
                "too narrow, only that it is at least this wide.",
                required=False,
            ),
            _measure("obstacle_density", "ratio", "Occupied cells over cells sampled."),
            _measure("samples_taken", "count", "Cross-sections measured along the route."),
            _measure(
                "samples_limited_by_coverage",
                "count",
                "Cross-sections the map bounded on one side only.",
            ),
        ),
        references=(
            _points_at(
                "map_region",
                "The region each reported cross-section belongs to.",
                required=False,
            ),
        ),
    ),
    failure_modes=("region_not_resolved", "map_coverage_insufficient"),
)

CANDIDATE_MEASUREMENTS = ToolCard(
    tool_id="get_candidate_measurements",
    tool_version="1.0.0",
    title="Read what one candidate actually scored",
    tool_class="fact_query",
    purpose=ToolPurpose(
        notes=(
            "The decomposition says how a pair differed; this says what either of "
            "them did. Until M1 these numbers lived in the report and never reached "
            "an analyst, so the only thing it could talk about was ΔU.",
            "Every rate arrives with its denominator. A success rate without one is "
            "the sentence this platform exists to refuse.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=("episode_decision_utility",),
    io=ToolIO(
        arguments=(
            ArgumentSpec(
                name="candidate_id",
                kind="string",
                description="Which candidate's measurements to read.",
            ),
        ),
        measurements=(
            _measure("success_rate", "ratio", "Episodes that reached the goal, over episodes run."),
            _measure("n_episodes", "count", "The denominator of every rate reported here."),
            _measure("collisions", "count", "Episodes that ended in contact.", required=False),
            _measure("latency_p99_ms", "ms", "Tail planning latency.", required=False),
            _measure("latency_median_ms", "ms", "Typical planning latency.", required=False),
            _measure("path_length_m", "m", "Median path length driven.", required=False),
            _measure("min_clearance_m", "m", "Smallest clearance observed.", required=False),
            _measure(
                "decision_utility",
                "ratio",
                "Set-level decision utility, as the card holds it.",
                required=False,
            ),
        ),
    ),
    failure_modes=("candidate_not_in_packet", "measurements_not_recorded"),
)

KNOWN_UNKNOWNS = ToolCard(
    tool_id="get_known_unknowns",
    tool_version="1.0.0",
    title="Read the gaps the platform declares about this case",
    tool_class="fact_query",
    purpose=ToolPurpose(
        notes=(
            "The packet already carries these; the tool exists so an analyst that "
            "lost them mid-round can re-read them rather than guess. The orchestrator "
            "enforces them regardless of whether the analyst asked.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=(),
    io=ToolIO(
        measurements=(
            _measure("n_known_unknowns", "count", "Declared gaps on this packet."),
            _measure(
                "n_blocked_claim_types",
                "count",
                "Distinct proposition types those gaps block.",
            ),
        ),
    ),
    failure_modes=(),
)


# --------------------------------------------------------------------------
# Evidence-navigation — where to look. Promotes nothing, by schema.
# --------------------------------------------------------------------------

FIND_EXEMPLARS = ToolCard(
    tool_id="find_exemplar_episodes",
    tool_version="1.0.0",
    title="Locate the preregistered exemplar episodes for a pair",
    tool_class="evidence_navigation",
    purpose=ToolPurpose(
        notes=(
            "The recipe is fixed before the numbers are seen — typical, strongest for "
            "each side, safety-critical — so the analyst cannot pick the episode that "
            "flatters a hypothesis it already has.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=("comparison_pair", "episode_decision_utility"),
    io=ToolIO(
        arguments=_PAIR,
        measurements=(
            _measure("n_exemplars", "count", "Episodes the preregistered recipe chose."),
        ),
        references=(
            _points_at(
                "episode",
                "The chosen episodes themselves — a count says how many to open, not "
                "which, and the count was all this card used to promise.",
            ),
        ),
    ),
    failure_modes=("pair_not_recorded", "no_paired_episodes"),
)

REPLAY_WINDOW = ToolCard(
    tool_id="get_replay_window",
    tool_version="1.0.0",
    title="Locate a replay window around an episode event",
    tool_class="evidence_navigation",
    purpose=ToolPurpose(
        does_not_verify={
            "global_planner_attempt_attribution": (
                "A window is a time range to watch. Watching it does not establish "
                "what any component intended."
            )
        },
    ),
    proposition_policy=PropositionPolicy(
        forbidden_inference_types=("global_planner_attempt_attribution",),
        maximum_claim_level="observed",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("trace",),
    io=ToolIO(
        arguments=(
            _CANDIDATE,
            _EPISODE,
            _argument("center_s", "number", "Centre of the window, in episode seconds."),
            _argument("half_width_s", "number", "Half-width of the window, in seconds."),
        ),
        measurements=(
            _measure("window_start_s", "s", "Window start, in episode seconds."),
            _measure("window_end_s", "s", "Window end, in episode seconds."),
            _measure("n_rows", "count", "Trace rows inside the window."),
        ),
        references=(_points_at("replay_window", "The window to open in the replay viewer."),),
    ),
    failure_modes=("trace_unavailable", "window_out_of_range"),
)

TRAJECTORY_SEGMENT = ToolCard(
    tool_id="get_trajectory_segment",
    tool_version="1.0.0",
    title="Locate a trajectory segment by arc length along the route",
    tool_class="evidence_navigation",
    purpose=ToolPurpose(
        does_not_verify={
            "global_planner_attempt_attribution": (
                "A segment shows where the robot went. Where it went is not what was "
                "planned for it."
            )
        },
        notes=(
            "Segments are addressed on the declared reference line so two runs can be "
            "compared at the same progress; the projection quality is declared with "
            "the segment rather than assumed.",
        ),
    ),
    proposition_policy=PropositionPolicy(
        forbidden_inference_types=("global_planner_attempt_attribution",),
        maximum_claim_level="observed",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("trace", "reference_line"),
    io=ToolIO(
        arguments=(
            _CANDIDATE,
            _EPISODE,
            _argument("from_progress_m", "number", "Segment start, as arc length on the line."),
            _argument("to_progress_m", "number", "Segment end, as arc length on the line."),
        ),
        measurements=(
            _measure("segment_length_m", "m", "Arc length of the segment on the line."),
            _measure("n_samples", "count", "Pose samples inside the segment."),
            _measure(
                "max_lateral_offset_m",
                "m",
                "Furthest the robot strayed from the reference line in the segment.",
            ),
        ),
        references=(_points_at("trajectory_segment", "The segment, addressed by arc length."),),
    ),
    failure_modes=("trace_unavailable", "projection_quality_insufficient"),
)

EVENT_NEIGHBORHOOD = ToolCard(
    tool_id="get_event_neighborhood",
    tool_version="1.0.0",
    title="Locate what else the trace recorded around an event",
    tool_class="evidence_navigation",
    purpose=ToolPurpose(
        notes=(
            "Returns neighbouring rows — replans, latency ticks, clearance samples — "
            "so an analyst can see the context of a detection without reading a whole "
            "episode.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=("trace",),
    io=ToolIO(
        arguments=(
            _CANDIDATE,
            _EPISODE,
            _argument("event_index", "integer", "Which recorded event to read around."),
            _argument(
                "radius_rows",
                "integer",
                "How many trace rows either side; a small default if omitted.",
                required=False,
            ),
        ),
        measurements=(
            _measure("n_rows_before", "count", "Rows returned before the event."),
            _measure("n_rows_after", "count", "Rows returned after the event."),
        ),
        references=(_points_at("trace_rows", "The neighbouring rows themselves."),),
    ),
    failure_modes=("trace_unavailable", "event_not_found"),
)


# --------------------------------------------------------------------------
# Mechanism-check — the only class that can reach past ``observed``.
# --------------------------------------------------------------------------

GAP_VS_FOOTPRINT = ToolCard(
    tool_id="gap_vs_footprint",
    tool_version="2.0.0",
    title="Check geometric passage feasibility against the inflated footprint",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={
            "geometric_infeasibility": (
                "The clearance the configured inflation requires exceeds the measured "
                "width of the passage, so no free cell remains for the planner."
            )
        },
        does_not_verify={
            "complete_utility_attribution": (
                "An infeasible passage explains a refusal at that passage. It does not "
                "account for the whole difference in utility."
            ),
            "global_planner_attempt_attribution": (
                "The check is about geometry. It does not establish that the planner "
                "attempted this passage."
            ),
        },
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("geometric_infeasibility",),
        forbidden_inference_types=(
            "complete_utility_attribution",
            "global_planner_attempt_attribution",
        ),
        maximum_claim_level="mechanism_verified",
    ),
    evidence_policy=_RECORDED_OR_VERIFIED,
    required_evidence=(
        "map_checksum",
        "region_geometry",
        "robot_footprint",
        "inflation_parameters",
        "inflation_implementation_version",
    ),
    io=ToolIO(
        arguments=(_CANDIDATE, _REGION),
        measurements=(
            _measure("passage_width_m", "m", "Measured cross-section of the passage."),
            _measure(
                "required_passage_width_m",
                "m",
                "Corridor this configuration needs: 2 * (radius + inflation margin). "
                "A width, compared against a width — the first card compared it "
                "against a radius.",
            ),
            _measure(
                "margin_m",
                "m",
                "Passage width minus required width; negative is the infeasible case.",
            ),
            _measure(
                "inflation_margin_m", "m", "The inflation margin per side that was configured."
            ),
        ),
        references=(_points_at("map_region", "The passage the check measured."),),
    ),
    failure_modes=(
        "region_not_resolved",
        "missing_footprint",
        "implementation_version_unknown",
        "ambiguous_passage_geometry",
    ),
)

REPLAY_GLOBAL_PLAN = ToolCard(
    tool_id="replay_global_plan",
    tool_version="1.0.0",
    title="Re-run the global planner on the recorded planning inputs",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={
            "geometric_infeasibility": (
                "Re-run on the same map, start, goal and parameters, the planner "
                "returns no path — the query itself is infeasible for this stack."
            )
        },
        does_not_verify={
            "global_planner_attempt_attribution": (
                "A replay shows what the planner does now on these inputs. What it "
                "attempted during the run is a different question, and one only the "
                "sidecar can answer."
            ),
            "complete_utility_attribution": (
                "Reproducing one failed query does not price the run's outcome."
            ),
        },
        notes=(
            "A run recorded before the planning-input sidecar can only be replayed "
            "from reconstructed inputs, which the provenance ceiling caps at "
            "associated however clean the replay is. Byte-comparing an output plan is "
            "a refuter only: matching bytes do not prove the same code ran.",
        ),
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("geometric_infeasibility",),
        forbidden_inference_types=(
            "global_planner_attempt_attribution",
            "complete_utility_attribution",
        ),
        maximum_claim_level="mechanism_verified",
    ),
    evidence_policy=_REPLAYABLE,
    required_evidence=(
        "map_checksum",
        "planning_inputs",
        "planner_parameters",
        "planner_implementation_version",
    ),
    io=ToolIO(
        arguments=(
            _CANDIDATE,
            _EPISODE,
            _argument("attempt_index", "integer", "Which planning attempt of the episode."),
        ),
        measurements=(
            _measure("attempts_replayed", "count", "Planning attempts re-run."),
            _measure(
                "attempts_recorded",
                "count",
                "Attempts the sidecar recorded; a mismatch with the replayed count is "
                "a refusal, not a rounding difference.",
            ),
            _measure("paths_found", "count", "Replayed attempts that returned a path."),
            _measure(
                "path_length_m",
                "m",
                "Length of the replayed path, where one was found.",
                required=False,
            ),
        ),
    ),
    failure_modes=(
        "planning_inputs_missing",
        "implementation_version_unknown",
        "attempt_count_mismatch",
        "nondeterministic_planner",
    ),
)

LATENCY_VS_EXPANDED_NODES = ToolCard(
    tool_id="latency_vs_expanded_nodes",
    tool_version="2.0.0",
    title="Relate search expansions to control-tick latency",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={
            "expansion_latency_association": (
                "Episodes of this candidate whose search expanded more nodes recorded "
                "higher planner latency, ranked across the run."
            )
        },
        does_not_verify={
            "candidate_latency_attribution": (
                "Which share of the latency belongs to the candidate rather than to "
                "the deployment's own compute or transport is exactly what H4's "
                "accounting has not yet split out."
            ),
            "complete_utility_attribution": (
                "An association with latency is not a share of the utility gap."
            ),
        },
        notes=(
            "Deterministic and exact, and capped at associated for that reason: the "
            "arithmetic reproduces, the causal reading does not follow from it.",
            "Across episodes, not across replans. HĐ-5's trace records "
            "planner_latency_ms per row and no expanded-node column, and that schema "
            "is frozen — so the per-tick version the first card promised cannot be "
            "computed from what runs record, and the card says what the data supports "
            "instead of what would have been nicer.",
            "Within one candidate. The benchmark separates a grid search's expanded "
            "nodes from a sampling planner's tree size because they count different "
            "things; ranking one against the other would measure the units.",
        ),
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("expansion_latency_association",),
        forbidden_inference_types=(
            "candidate_latency_attribution",
            "complete_utility_attribution",
        ),
        maximum_claim_level="associated",
    ),
    evidence_policy=_RECORDED,
    required_evidence=("episode_expanded_nodes", "episode_latency"),
    io=ToolIO(
        arguments=(_CANDIDATE,),
        measurements=(
            _measure("n_episodes", "count", "Episodes the association was ranked over."),
            _measure(
                "spearman_rho",
                "correlation",
                "Rank correlation of expanded nodes with planner latency across episodes.",
            ),
            _measure("median_expanded_nodes", "count", "Median search size per episode."),
            _measure("median_latency_ms", "ms", "Median planner latency per episode."),
        ),
    ),
    failure_modes=(
        "expansion_counts_missing",
        "insufficient_episodes",
        "no_variation_to_rank",
    ),
)

RRT_CONVERGENCE = ToolCard(
    tool_id="rrt_convergence",
    tool_version="2.0.0",
    title="Check whether the sampling budget reaches the corridor",
    tool_class="mechanism_check",
    purpose=ToolPurpose(
        verifies={
            "sampling_budget_insufficiency": (
                "At the configured budget the tree reaches the corridor on only some "
                "seeds, and the rate rises with the budget — the corridor is found by "
                "sampling luck rather than by the planner's design."
            )
        },
        does_not_verify={
            "universal_algorithm_superiority": (
                "A budget too small for this corridor says nothing about the planner on other maps."
            ),
            "complete_utility_attribution": (
                "Intermittent path failure is a mechanism, not a share of the gap."
            ),
        },
    ),
    proposition_policy=PropositionPolicy(
        supported_proposition_types=("sampling_budget_insufficiency",),
        forbidden_inference_types=(
            "universal_algorithm_superiority",
            "complete_utility_attribution",
        ),
        maximum_claim_level="mechanism_verified",
    ),
    evidence_policy=_RECORDED_OR_VERIFIED,
    required_evidence=(
        "map_checksum",
        "planning_inputs",
        "planner_parameters",
        "planner_implementation_version",
        "seed_set",
    ),
    io=ToolIO(
        arguments=(
            _CANDIDATE,
            _EPISODE,
            _argument(
                "budget_multiplier",
                "number",
                "Re-run at this multiple of the configured sample budget.",
                required=False,
            ),
        ),
        measurements=(
            _measure("seeds_run", "count", "Seeds the corridor was attempted on."),
            _measure("seeds_reaching_corridor", "count", "Seeds whose tree reached it."),
            _measure("success_rate_at_budget", "ratio", "Rate at the configured sample budget."),
            _measure(
                "success_rate_at_high_budget",
                "ratio",
                "Rate at the larger preregistered budget. The pair is the measurement: "
                "a rate that does not move with the budget points at the geometry.",
            ),
            _measure(
                "budget_multiplier", "ratio", "The larger budget, as a multiple of configured."
            ),
        ),
    ),
    failure_modes=(
        "planning_inputs_missing",
        "implementation_version_unknown",
        "seed_set_too_small",
        "corridor_not_identified",
    ),
)


# --------------------------------------------------------------------------
# Research-proposal — writes a specification, runs nothing.
# --------------------------------------------------------------------------

COMPONENT_SWAP_SPEC = ToolCard(
    tool_id="build_component_swap_spec",
    tool_version="1.0.0",
    title="Write a specification for swapping one component and re-running",
    tool_class="research_proposal",
    lane="research",
    execution_authorized=False,
    purpose=ToolPurpose(
        notes=(
            "The output is a document: which axis to vary, which to hold, how many "
            "episodes, which seeds, what would count as the effect. Running it is a "
            "decision a person makes in the research lane.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=("candidate_components", "task_profile_id"),
    io=ToolIO(
        arguments=(
            _argument("hypothesis_id", "string", "Which hypothesis the experiment would settle."),
            _argument("component", "string", "The single component to vary."),
        ),
    ),
    failure_modes=("components_not_declared", "axis_not_swappable"),
)

PARAMETER_INTERVENTION_SPEC = ToolCard(
    tool_id="build_parameter_intervention_spec",
    tool_version="1.0.0",
    title="Write a specification for varying one parameter and re-running",
    tool_class="research_proposal",
    lane="research",
    execution_authorized=False,
    purpose=ToolPurpose(
        notes=(
            "Names the parameter, the levels, the held-constant set and the "
            "preregistered outcome. An intervention nobody preregistered is an "
            "intervention whose result can be read after the fact.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=("candidate_components", "task_profile_id"),
    io=ToolIO(
        arguments=(
            _argument("hypothesis_id", "string", "Which hypothesis the experiment would settle."),
            _argument("parameter", "string", "The single parameter to vary."),
        ),
    ),
    failure_modes=("parameter_not_exposed", "level_out_of_range"),
)

TASK_PERTURBATION_SPEC = ToolCard(
    tool_id="build_task_perturbation_spec",
    tool_version="1.0.0",
    title="Write a specification for perturbing the task and re-running",
    tool_class="research_proposal",
    lane="research",
    execution_authorized=False,
    purpose=ToolPurpose(
        notes=(
            "Widening the passage, moving the goal, changing the obstacle schedule — "
            "each is a new task profile, and a new profile is a new run, not a "
            "re-reading of this one.",
        ),
    ),
    proposition_policy=PropositionPolicy(maximum_claim_level="observed"),
    evidence_policy=_RECORDED,
    required_evidence=("task_profile_id", "map_checksum"),
    io=ToolIO(
        arguments=(
            _argument("hypothesis_id", "string", "Which hypothesis the experiment would settle."),
            _argument("feature", "string", "The task feature to perturb."),
        ),
    ),
    failure_modes=("profile_not_parameterised", "perturbation_changes_identity"),
)


TOOL_CATALOG = ToolCatalog(
    catalog_version=TOOL_CATALOG_VERSION,
    cards=(
        OBJECTIVE_DECOMPOSITION,
        EPISODE_OBSERVATIONS,
        CANDIDATE_CONTRAST,
        MAP_REGION_FEATURES,
        CANDIDATE_MEASUREMENTS,
        KNOWN_UNKNOWNS,
        FIND_EXEMPLARS,
        REPLAY_WINDOW,
        TRAJECTORY_SEGMENT,
        EVENT_NEIGHBORHOOD,
        GAP_VS_FOOTPRINT,
        REPLAY_GLOBAL_PLAN,
        LATENCY_VS_EXPANDED_NODES,
        RRT_CONVERGENCE,
        COMPONENT_SWAP_SPEC,
        PARAMETER_INTERVENTION_SPEC,
        TASK_PERTURBATION_SPEC,
    ),
)
