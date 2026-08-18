"""H8: the conformance suite, the operator CLI, and the author guide.

The suite's own tests are written against **plugins that are wrong on
purpose**: a check that only ever sees correct input proves it does not
crash, not that it catches anything. Each defect below is one a real
author writes — a clock in the controller, an "optional" that is not, a
mutated request — and each has to be caught by name.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest
from planbench_plugin_sdk import (
    ChannelEnvelope,
    GlobalPlanRequest,
    GlobalPlanResponse,
    LocalResetRequest,
    LocalStepRequest,
    check_declarations,
    check_global_plugin,
    check_local_plugin,
    load_manifest,
    parse_manifest,
)

from planbench_simulator.host.cli import main
from tests.test_proof_plugins import EXAMPLES

OBSERVATION = "planbench://channel/legacy-observation@1"
LIDAR = "lidar_2d"
GUIDE = Path(__file__).resolve().parents[1] / "docs" / "plugin_author_guide.md"


def _manifest(**overrides):
    data = {
        "plugin_api": "1.1.0",
        "id": "org.test.plugin",
        "version": "0.1.0",
        "role": "local",
        "runtime": {
            "supported_lanes": ["python_in_process"],
            "production_lane": "python_in_process",
            "profiles": {
                "python_in_process": {
                    "protocol": "planbench-inproc/v1",
                    "codec": "python-object/v1",
                    "deadline_policy": "control-period",
                    "entry_point": "x:Y",
                }
            },
        },
        "requirements": {"all_of": [OBSERVATION], "optional": [LIDAR]},
        "supports": {
            "action_types": ["continuous-velocity@1"],
            "robot_dynamics": ["differential-drive@1"],
            "execution_models": ["synchronous-step@1"],
        },
        "requires_global_path": True,
    }
    data.update(overrides)
    return parse_manifest(data)


def _step_request() -> LocalStepRequest:
    return LocalStepRequest(
        state={"robot_state": None},
        channels=(
            ChannelEnvelope(
                capability=OBSERVATION,
                cadence="per_tick",
                produced_at=0.0,
                provenance="deployment",
                payload={"goal_bearing": 0.2},
            ),
            ChannelEnvelope(
                capability=LIDAR,
                cadence="per_tick",
                produced_at=0.0,
                provenance="deployment",
                payload=(2.0, 2.0),
            ),
        ),
    )


class _Good:
    name = "good"
    control_period = None

    def reset(self, request) -> None:
        self._seen = request

    def step(self, request):
        del request
        return {"linear_velocity": 0.4, "angular_velocity": 0.0}


class _NonDeterministic(_Good):
    name = "wobbly"
    _counter = itertools.count()

    def step(self, request):
        del request
        return {"linear_velocity": 0.1 * next(_NonDeterministic._counter), "angular_velocity": 0.0}


class _NeedsItsOptional(_Good):
    name = "liar"

    def step(self, request):
        for envelope in request.channels:
            if envelope.capability == LIDAR:
                return {"linear_velocity": 0.4, "angular_velocity": 0.0}
        raise LookupError("I actually need lidar_2d")


class _Mutator(_Good):
    """Mutates a channel's payload — the mutation that is actually possible.

    The request models are frozen, so reassigning a field already fails.
    What nothing stops is writing *into* a mutable payload: the host hands
    the same envelope object to every consumer granted it, so a dict
    scribbled on here is a different world for whoever reads it next.
    """

    name = "mutator"

    def step(self, request):
        for envelope in request.channels:
            if isinstance(envelope.payload, dict):
                envelope.payload["goal_bearing"] = 99.0
        return {"linear_velocity": 0.4, "angular_velocity": 0.0}


class TestTheSuiteCatchesRealMistakes:
    def test_a_correct_plugin_passes(self) -> None:
        report = check_local_plugin(_manifest(), _Good, _step_request())
        assert report.passed, report.render()
        assert report.render() == "conformance: no findings"

    def test_a_non_deterministic_plugin_is_caught(self) -> None:
        """Nothing at runtime detects this: the plugin does not fail, it
        makes the paired statistics measure noise."""
        report = check_local_plugin(_manifest(), _NonDeterministic, _step_request())
        assert not report.passed
        assert any(finding.check == "determinism" for finding in report.findings)

    def test_an_optional_that_is_not_optional_is_caught(self) -> None:
        """The host believes the label and would run this plugin on a
        deployment that offers nothing."""
        report = check_local_plugin(_manifest(), _NeedsItsOptional, _step_request())
        assert not report.passed
        assert any("declared optional" in finding.message for finding in report.findings)

    def test_a_plugin_that_mutates_its_request_is_caught(self) -> None:
        report = check_local_plugin(_manifest(), _Mutator, _step_request())
        assert not report.passed
        assert any(finding.check == "immutability" for finding in report.findings)

    def test_a_missing_role_method_is_caught(self) -> None:
        class _Half:
            name = "half"

            def reset(self, request) -> None:
                pass

        report = check_local_plugin(_manifest(), _Half, _step_request())
        assert not report.passed
        assert any(finding.check == "role" for finding in report.findings)

    def test_a_nameless_plugin_is_caught(self) -> None:
        class _Nameless(_Good):
            name = ""

        report = check_local_plugin(_manifest(), _Nameless, _step_request())
        assert any(finding.check == "name" for finding in report.findings)


class TestTheChecksAddedByReview:
    """Five gaps the H8 review found, each pinned by the defect it lets
    through when the check is absent."""

    def test_needing_one_of_two_optionals_is_caught(self) -> None:
        """Withholding them one at a time passes this plugin; the
        deployment that offers neither is exactly the one the label
        promised would work."""

        class _NeedsEither(_Good):
            def step(self, request):
                if not request.channels:
                    raise LookupError("I need at least one of them")
                return {"linear_velocity": 0.4, "angular_velocity": 0.0}

        manifest = _manifest(
            requirements={"all_of": [], "optional": [OBSERVATION, LIDAR]}
        )
        report = check_local_plugin(manifest, _NeedsEither, _step_request())
        assert not report.passed
        assert any(finding.check == "optional" for finding in report.findings)

    def test_reading_an_undeclared_channel_is_caught(self) -> None:
        """Works in a generous harness, fails on a deployment that grants
        precisely what was asked for — a manifest bug found here for the
        price of a line of JSON."""

        class _Greedy(_Good):
            def step(self, request):
                for envelope in request.channels:
                    if envelope.capability == LIDAR:
                        return {"linear_velocity": 0.4, "angular_velocity": 0.0}
                raise LookupError("undeclared: lidar_2d")

        manifest = _manifest(requirements={"all_of": [OBSERVATION], "optional": []})
        report = check_local_plugin(manifest, _Greedy, _step_request())
        assert not report.passed
        assert any(finding.check == "undeclared" for finding in report.findings)

    def test_a_constructor_that_raises_becomes_a_finding(self) -> None:
        """The module promises findings rather than exceptions, and a
        promise kept only for the failures somebody wrapped is not kept."""

        def _explodes():
            raise RuntimeError("bad config")

        report = check_local_plugin(_manifest(), _explodes, _step_request())
        assert not report.passed
        assert report.findings[0].check == "construction"

    def test_an_action_of_the_wrong_type_becomes_a_finding(self) -> None:
        class _Stringly(_Good):
            def step(self, request):
                del request
                return {"linear_velocity": "fast", "angular_velocity": 0.0}

        report = check_local_plugin(_manifest(), _Stringly, _step_request())
        assert not report.passed
        assert any(finding.check == "action" for finding in report.findings)

    def test_a_plugin_that_writes_into_its_reset_request_is_caught(self) -> None:
        """The deployment's declarations are shared: a plugin that edits
        them changes what the deployment says for everything measured
        after it."""

        class _ResetMutator(_Good):
            def reset(self, request) -> None:
                request.declared["envelope"] = "clobbered"

        report = check_local_plugin(
            _manifest(),
            _ResetMutator,
            _step_request(),
            LocalResetRequest(declared={"envelope": "original"}),
        )
        assert not report.passed
        assert any("reset() wrote" in finding.message for finding in report.findings)


class TestGlobalPluginsHaveTheirOwnSuite:
    """Running a global plugin through the local suite would crash on the
    first ``step()`` — a suite that fits two of three roles tells the
    third nothing."""

    @staticmethod
    def _request() -> GlobalPlanRequest:
        return GlobalPlanRequest(start=(0.0, 0.0), goal=(4.0, 4.0))

    def test_a_correct_global_plugin_passes(self) -> None:
        class _Straight:
            name = "straight"

            def plan(self, request):
                return GlobalPlanResponse(success=True, path=(request.start, request.goal))

        report = check_global_plugin(_manifest(role="global"), _Straight, self._request())
        assert report.passed, report.render()

    def test_a_non_deterministic_global_plugin_is_caught(self) -> None:
        counter = itertools.count()

        class _Wandering:
            name = "wandering"

            def plan(self, request):
                offset = float(next(counter))
                return GlobalPlanResponse(success=True, path=((0.0, offset), request.goal))

        report = check_global_plugin(_manifest(role="global"), _Wandering, self._request())
        assert not report.passed
        assert any(finding.check == "determinism" for finding in report.findings)

    def test_a_non_finite_waypoint_is_caught(self) -> None:
        """It fails much later, inside a follower, as a robot that stops
        for no stated reason."""

        class _Infinite:
            name = "infinite"

            def plan(self, request):
                del request
                return type("R", (), {"path": ((0.0, 0.0), (float("inf"), 1.0))})()

        report = check_global_plugin(_manifest(role="global"), _Infinite, self._request())
        assert not report.passed
        assert any(finding.check == "path" for finding in report.findings)

    def test_a_global_plugin_that_raises_becomes_a_finding(self) -> None:
        class _Broken:
            name = "broken"

            def plan(self, request):
                raise RuntimeError("no")

        report = check_global_plugin(_manifest(role="global"), _Broken, self._request())
        assert not report.passed
        assert any(finding.check == "plan" for finding in report.findings)


class TestStaticDeclarationChecks:
    def test_a_capability_both_required_and_optional_is_an_error(self) -> None:
        """The host cannot honour both readings and would pick one
        silently — which is the failure, not the ambiguity."""
        report = check_declarations(
            _manifest(requirements={"all_of": [LIDAR], "optional": [LIDAR]}), granted=[LIDAR]
        )
        assert not report.passed

    def test_a_global_plugin_requiring_a_path_is_an_error(self) -> None:
        report = check_declarations(
            _manifest(role="global", requires_global_path=True), granted=[OBSERVATION]
        )
        assert not report.passed
        assert any(finding.check == "role" for finding in report.findings)

    def test_unmet_requirements_are_a_warning_not_an_error(self) -> None:
        """A deployment that does not offer a capability is a fact about
        the deployment; the plugin is not wrong."""
        report = check_declarations(_manifest(), granted=[])
        assert report.passed
        assert report.findings and report.findings[0].severity == "warning"


class TestTheExampleBundlesConform:
    @pytest.mark.parametrize("bundle", ["social_nav", "corridor_planner", "remote_wanderer"])
    def test_every_shipped_example_passes_its_own_static_checks(self, bundle: str) -> None:
        """The guide points authors at these. An example that fails the
        suite it recommends teaches the wrong thing."""
        manifest, _ = load_manifest(EXAMPLES / bundle / ".planbench-plugin" / "plugin.json")
        report = check_declarations(manifest, granted=manifest.requirements.all_of)
        assert report.passed, report.render()


class TestTheOperatorCli:
    def test_list_shows_the_built_ins(self, capsys) -> None:
        code = main(["--no-entry-points", "list"])
        printed = capsys.readouterr().out
        assert "astar@v1" in printed
        assert "dwa@v1" in printed
        assert code == 0

    def test_list_reports_bundles_alongside_them(self, capsys) -> None:
        main(["--no-entry-points", "--bundles", str(EXAMPLES), "list"])
        printed = capsys.readouterr().out
        assert "org.planbench.example.corridor" in printed
        assert "astar@v1" in printed

    def test_check_explains_why_a_plugin_cannot_run(self, capsys) -> None:
        """The whole point: absence is indistinguishable between four
        different causes, so the tool has to name one."""
        code = main(
            [
                "--no-entry-points",
                "--bundles",
                str(EXAMPLES),
                "check",
                "org.planbench.example.social-nav",
            ]
        )
        printed = capsys.readouterr().out
        assert "registration      : registered_but_missing_provider" in printed
        assert "human_state_estimates" in printed
        assert code == 1

    def test_check_admits_the_oracle_under_research_and_says_so(self, capsys) -> None:
        code = main(
            [
                "--no-entry-points",
                "--bundles",
                str(EXAMPLES),
                "check",
                "org.planbench.example.social-nav",
                "--research",
            ]
        )
        printed = capsys.readouterr().out
        assert "evidence class    : oracle" in printed
        assert "oracle providers" in printed
        assert code == 0

    def test_an_unknown_plugin_lists_what_was_found(self, capsys) -> None:
        code = main(["--no-entry-points", "check", "org.nobody.nothing"])
        assert code == 1
        assert "discovered:" in capsys.readouterr().err

    def test_a_bad_bundles_path_is_refused_rather_than_ignored(self, capsys) -> None:
        """Silently scanning nothing would report an empty roster, which
        reads as "no plugins installed" — a wrong answer that looks
        like a right one."""
        assert main(["--bundles", "/no/such/place", "list"]) == 2
        assert "not a directory" in capsys.readouterr().err


class TestTheGuideStaysTrue:
    """A guide that drifts from the code teaches the old thing
    confidently, so the claims it makes are pinned here."""

    def test_it_documents_all_three_roles(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        for role in ("global", "local", "monolithic"):
            assert role in text

    def test_the_commands_it_prints_actually_run(self) -> None:
        """**Executed, not matched.** The first version of this test
        asserted the substring ``"cli list"`` appeared, and passed while
        the guide told authors to write ``cli list --bundles X`` — which
        argparse rejects, because ``--bundles`` belongs to the top-level
        command. A documentation test that cannot tell a working command
        from a broken one is documentation with a test-shaped ornament.
        """
        import shlex

        text = GUIDE.read_text(encoding="utf-8")
        commands = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("python -m planbench_simulator.host.cli")
        ]
        assert commands, "the guide no longer shows how to run the CLI"

        for command in commands:
            argv = shlex.split(command)[3:]  # drop "python -m <module>"
            # The guide's own placeholder paths are replaced with the
            # real example bundle; everything else is run verbatim.
            argv = [str(EXAMPLES) if arg == "/path/to/plugins" else arg for arg in argv]
            argv = [
                "org.planbench.example.corridor" if arg == "org.yourlab.my-planner" else arg
                for arg in argv
            ]
            # Exit code 1 means "cannot run", which is a valid answer;
            # 2 is argparse refusing the command line itself.
            assert main(argv) in (0, 1), f"the guide's command is not valid: {command}"

    def test_every_example_it_names_exists(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        for bundle in ("corridor_planner", "social_nav", "remote_wanderer"):
            assert bundle in text
            assert (EXAMPLES / bundle / ".planbench-plugin" / "plugin.json").is_file()

    def test_it_does_not_promise_a_security_sandbox(self) -> None:
        """The claim H7's review narrowed. A guide is where an author
        would go looking for permission to run untrusted code."""
        text = GUIDE.read_text(encoding="utf-8")
        assert "not* a security sandbox" in text or "not a security sandbox" in text
        assert "dropped\nprivileges" in text or "dropped privileges" in text
