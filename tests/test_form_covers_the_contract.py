"""The deployment form must not fall behind ``TaskProfile``.

**The failure this exists to catch leaves nothing else red.** Add a field
to the contract and the form simply stops offering it: the suite stays
green, the form still files a deployment, and the profile it produces is
silently missing the thing that was just added. Nobody finds out until a
run measures a world nobody described.

Why the check lives in the Python suite and reads a ``.tsx`` file: it is
the only place that can see *both* sides. `TaskProfile` is the contract
and pydantic can enumerate it; the form is TypeScript and the web tests
cannot import pydantic. A string search is coarse, and coarse is enough —
the form binds every field by its dotted path (``field("robot.radius",
…)``), so the path either appears in the file or the field is not bound.

A field may be missing **only** by being named in :data:`NOT_IN_THE_FORM`
with a reason. That list is the point of the test as much as the check
is: it turns "the form does not do that" from something a reader has to
discover into something somebody wrote down and can be argued with.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from planbench_schemas.task_profile import TaskProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
FORM_PATH = REPO_ROOT / "apps" / "web" / "src" / "components" / "DeploymentForm.tsx"

#: Contract fields the form deliberately does not offer, and why.
#:
#: Every entry is a decision somebody made, not a gap somebody left. A
#: field belongs here when offering it would be wrong or useless — never
#: because wiring it up was inconvenient.
NOT_IN_THE_FORM: dict[str, str] = {
    "capability_grants": (
        "H11 gave the deployment side a way to declare capabilities beyond the two v1 "
        "tokens, and shipped the backend only. A grant names a provider id, a version and "
        "a config whose schema the platform cannot yet validate — so a form control here "
        "would collect three strings nothing checks, and a typo in a provider id would "
        "produce a valid-looking profile with a fingerprint of its own. The field is "
        "declared in YAML until provider-schema validation exists; the report for H11 "
        "carries the same statement, and this entry is what stops it being a gap nobody "
        "wrote down."
    ),
    "replanning.max_replans": (
        "There is no budget any more and offering the field would put back exactly what "
        "removing it fixed. A shared cap is a number somebody chose; it binds differently for "
        "different stacks, and under a budget of three a stack that would have escaped on its "
        "fourth try is scored as a failure of the cap rather than of the planner. The switch "
        "beside this one turns replanning on and leaves it unlimited; the cost is that every "
        "replan is charged to the control step it delayed, so p99 latency and travel time "
        "price it and the ceiling grows out of the physics instead of being declared. The "
        "field survives in the schema only because the retiring benchmark flow stores specs "
        "that name one, and a stored run must keep describing the conditions it ran under."
    ),
    "robot.type": (
        "Literal['differential_drive'] — the only value the schema allows. A dropdown "
        "with one option is a control that cannot be used, and it would suggest there "
        "is a choice here when the simulator implements exactly one drive."
    ),
    "available_observations": (
        "Every shipped profile declares [lidar_2d] and no registered candidate needs "
        "anything else. The day one does, it arrives with G6's observation pricing "
        "(HĐ-6) attached, and the field is worth a control then rather than now."
    ),
    "constraints.cost_per_mission_max": (
        "Optional and defaulted to nothing on purpose: it is the scale business mode "
        "prices engineering effort against, and a form field pre-filled with a number "
        "would be the platform inventing a budget for the customer. Absent, the money "
        "anchor does not resolve and business mode refuses rather than guesses "
        "(HĐ-8.3 law 4, HĐ-9.3) — which is the honest behaviour, so the form leaves it "
        "absent."
    ),
    "min_episodes_before_stop": (
        "None means 'take the default', and the value actually used is recorded on the "
        "report either way. Offering the override in the form would put a knob on early "
        "stopping next to the thresholds it is not part of; the deployment_role field "
        "already decides whether early stopping happens at all."
    ),
}


def leaf_paths(model: type[BaseModel], prefix: str = "") -> list[str]:
    """Every settable field of a profile, as the dotted path YAML uses.

    Nested *models* are expanded — ``constraints`` is eight fields a form
    binds one by one. Collections are **not**: ``missions`` is bound as a
    whole by the placer, and expanding it would demand a text box per
    mission field for a control that already exists.
    """
    paths: list[str] = []
    for name, info in model.model_fields.items():
        path = f"{prefix}{name}"
        annotation = info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            paths.extend(leaf_paths(annotation, f"{path}."))
        else:
            paths.append(path)
    return paths


@pytest.fixture(scope="module")
def form_source() -> str:
    assert FORM_PATH.is_file(), f"the deployment form moved: {FORM_PATH}"
    return FORM_PATH.read_text(encoding="utf-8")


class TestTheFormKeepsUpWithTheContract:
    def test_every_field_is_offered_or_excused(self, form_source):
        """The check itself: bound, or written down as deliberately not."""
        missing = [
            path
            for path in leaf_paths(TaskProfile)
            if f'"{path}"' not in form_source and path not in NOT_IN_THE_FORM
        ]
        assert missing == [], (
            "these contract fields are in no form control and in no exclusion list:\n  "
            + "\n  ".join(missing)
            + "\n\nAdd an input for each, or add it to NOT_IN_THE_FORM with the reason "
            "it should not have one. A field in neither place is one a deployment can "
            "no longer declare through the UI, and nothing else in the suite notices."
        )

    def test_the_exclusion_list_has_no_ghosts(self, form_source):
        """An excuse for a field that no longer exists is worse than none.

        It reads as a live decision while describing nothing, and the next
        person to add a field with that name inherits an exemption nobody
        granted it.
        """
        known = set(leaf_paths(TaskProfile))
        ghosts = sorted(set(NOT_IN_THE_FORM) - known)
        assert ghosts == [], (
            f"NOT_IN_THE_FORM excuses fields the contract no longer has: {ghosts}. "
            "Remove them — an exemption outliving its field is one the next field of "
            "that name inherits for free."
        )

    def test_no_field_is_both_offered_and_excused(self, form_source):
        """Contradicting itself is how a list stops being read."""
        both = sorted(path for path in NOT_IN_THE_FORM if f'"{path}"' in form_source)
        assert both == [], (
            f"these are bound by the form *and* listed as deliberately absent: {both}. "
            "One of the two is out of date."
        )

    @pytest.mark.parametrize("path", sorted(NOT_IN_THE_FORM))
    def test_each_exclusion_gives_a_reason_worth_reading(self, path):
        """A one-word excuse is a gap with a label on it.

        The bar is deliberately low and still catches "todo" and "n/a":
        anybody who has to write two sentences either has a reason or
        notices that they do not.
        """
        reason = NOT_IN_THE_FORM[path]
        assert len(reason) > 80, f"{path}: the reason is too short to be one"
        assert not reason.lower().startswith(("todo", "later", "n/a")), (
            f"{path}: that is a plan, not a reason"
        )


class TestTheCheckItselfWorks:
    """A guard nobody has seen fail is a guard nobody should trust."""

    def test_it_notices_a_field_that_lost_its_control(self):
        """The whole scenario, simulated: a real field, an empty form."""
        missing = [path for path in leaf_paths(TaskProfile) if path not in NOT_IN_THE_FORM]
        assert "constraints.success_rate_min" in missing
        assert "environment.sensor_noise.lidar_range_sigma_m" in missing

    def test_it_expands_nested_models_but_not_collections(self):
        paths = set(leaf_paths(TaskProfile))
        # Expanded: a form binds these one input at a time.
        assert "hardware.ram_budget_breakdown.perception_stack_mb" in paths
        # Not expanded: bound as a whole by the mission placer.
        assert "missions" in paths
        assert not any(path.startswith("missions.") for path in paths)


TRAFFIC_UI = (REPO_ROOT / "apps" / "web" / "src" / "components" / "TrafficEditor.tsx").read_text(
    encoding="utf-8"
)
TRAFFIC_LIB = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "traffic.ts").read_text(encoding="utf-8")


class TestTrafficIsAuthorable:
    """`environment.dynamic_obstacles` is bound, and now all the way.

    This class replaced one called ``TestTrafficIsCarriedButNotYetAuthored``,
    which pinned the opposite: the form wrote the field when a library
    scenario was chosen and offered no way to write one from scratch. It
    checked that by asserting ``seed_time_offset`` and ``PeriodicMotion``
    were absent from ``DeploymentForm.tsx``, and it said whoever added
    them got to delete it. This is that deletion.

    **Those assertions would still pass, which is why they had to go.**
    The authoring lives in ``TrafficEditor.tsx`` and ``traffic.ts``, so a
    grep of the form alone would have stayed green while being false —
    the worst state a guard can be in, because nothing announces it.
    What is checked here instead is presence: every motion law the
    contract defines has a way into the document.
    """

    def test_the_form_writes_the_field(self, form_source) -> None:
        assert 'withValue(next, "environment.dynamic_obstacles"' in form_source

    def test_it_carries_what_a_scenario_declares(self, form_source) -> None:
        assert "scenario?.dynamic_obstacles ?? []" in form_source

    def test_it_mounts_an_editor_for_what_it_carried(self, form_source) -> None:
        assert "<TrafficEditor" in form_source

    def test_every_motion_law_has_a_way_in(self) -> None:
        """The check the old class could not make.

        ``Motion`` is a closed union of four, and a UI offering three of
        them makes the fourth unreachable without hand-editing YAML —
        which is the state the TypeScript mirror was already in, missing
        two of them, until this work.
        """
        from planbench_schemas.dynamic import Motion

        kinds = {
            option.model_fields["kind"].default
            for option in Motion.__origin__.__args__  # type: ignore[attr-defined]
        }
        assert kinds, "could not enumerate the motion union"
        for kind in kinds:
            assert f'"{kind}"' in TRAFFIC_LIB, f"{kind} has no way into a deployment"

    def test_the_head_start_is_offered_rather_than_left_at_zero(self) -> None:
        """A field the server refuses at zero must not open at zero with
        no way to fill it: that is a form writing documents it knows will
        be refused."""
        assert "seed_time_offset" in TRAFFIC_UI
        assert "seedTimeOffsetSuggest" in TRAFFIC_UI

    def test_the_verdict_still_comes_from_the_server(self, form_source) -> None:
        """The rule the old class protected, kept while the rest went.

        The form decides nothing. What changed is that it can now *ask* —
        the same check filing runs, reached without filing — and that it
        has somewhere to show a refusal addressed to ``environment``,
        which is where every traffic rule lands.
        """
        assert '"/task-profiles/validate"' in form_source
        assert 'entry.path.startsWith("environment.")' in form_source

    def test_the_scenario_editor_can_still_do_it_too(self) -> None:
        """`/scenarios` outlived P6 because it was the only thing that
        could draw an obstacle. It is not any more, which turns retiring
        it into a decision somebody takes rather than something to wait
        for. Until that decision it keeps working."""
        editor = (
            REPO_ROOT / "apps" / "web" / "src" / "app" / "scenarios" / "[id]" / "page.tsx"
        ).read_text(encoding="utf-8")
        assert "dynamic_obstacles" in editor
