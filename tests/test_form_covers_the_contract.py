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


class TestTrafficIsCarriedButNotYetAuthored:
    """`environment.dynamic_obstacles` is bound — and only halfway.

    It used to sit in `NOT_IN_THE_FORM`, excused as deferred. That excuse
    expired the day the form started writing the field: choosing a
    library scenario now carries its traffic into the deployment, which
    is what makes `sudden_stop` produce a deployment with the cart in it
    rather than an empty lane.

    **The guard is binary and the truth is not**, so the nuance lives
    here instead of in a sentence nothing checks: the form *carries*
    traffic, it does not let anybody *author* it. A reader who saw the
    field disappear from the excuse list could otherwise conclude the
    form can draw a cart. It cannot — that is still the YAML tab, and
    still the reason `/scenarios` is kept alive.
    """

    def test_the_form_writes_the_field(self, form_source) -> None:
        assert 'withValue(next, "environment.dynamic_obstacles"' in form_source

    def test_it_carries_what_a_scenario_declares(self, form_source) -> None:
        assert "scenario?.dynamic_obstacles ?? []" in form_source

    def test_it_offers_no_way_to_author_one(self, form_source) -> None:
        """The half that is still missing, pinned so it cannot be forgotten.

        A motion kind picker, a speed, a period, a `seed_time_offset`
        that must clear a full period — none of it is here. If any of
        those ever appear, this test fails and whoever added them gets to
        delete it, which is the point.
        """
        for authoring in ("SuddenStopMotion", "PeriodicMotion", "seed_time_offset", "motion:"):
            assert authoring not in form_source, (
                f"the form now authors traffic ({authoring}); update this test"
            )

    def test_the_scenario_editor_is_still_the_place_that_can(self) -> None:
        """Why `/scenarios` survived P6, stated as a test rather than a note."""
        editor = (
            REPO_ROOT / "apps" / "web" / "src" / "app" / "scenarios" / "[id]" / "page.tsx"
        ).read_text(encoding="utf-8")
        assert "dynamic_obstacles" in editor
