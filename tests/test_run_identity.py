"""Pinning what a run will execute, and refusing when it moved.

A stack name is a pointer. Following it twice — once when the request
arrives, once when the queued job starts — is how a run comes to measure
code nobody asked for while filing the result under an id that says
otherwise. These tests are about following it exactly once and keeping
the answer, which is what makes the second look a *check* rather than a
second question.
"""

from __future__ import annotations

import pytest

from planbench_api.run_identity import (
    IdentityError,
    RunPurpose,
    plugin_id_in,
    provider_fingerprint,
    recheck,
    resolve,
)


class _Bundle:
    def __init__(self, bundle_id, plugin_id, revision, status="active", checksum="c"):
        self.id = bundle_id
        self.plugin_id = plugin_id
        self.revision = revision
        self.checksum = checksum
        self.role = "local"
        self.disabled_reason = ""
        self.status = type("S", (), {"value": status})()


class _Lookup:
    """The three questions ``run_identity`` is allowed to ask."""

    def __init__(self, bundles, current=None):
        self._bundles = {bundle.id: bundle for bundle in bundles}
        self._current = current or {}

    def get(self, bundle_id):
        return self._bundles[bundle_id]

    def current(self, plugin_id):
        bundle_id = self._current.get(plugin_id)
        return self._bundles.get(bundle_id) if bundle_id else None

    def newest(self, plugin_id):
        matching = [b for b in self._bundles.values() if b.plugin_id == plugin_id]
        return max(matching, key=lambda b: b.revision, default=None)


REV3 = _Bundle("b3", "org.vinai.vfh-plus", 3)
REV4 = _Bundle("b4", "org.vinai.vfh-plus", 4)


class TestTellingAnImportedStackFromABuiltInOne:
    def test_a_built_in_stack_pins_nothing(self) -> None:
        assert plugin_id_in("astar+dwa") is None

    def test_an_imported_one_is_recognised_by_its_plugin_id(self) -> None:
        """Dots, because a plugin id has them and a built-in name does not.

        Asked without the registry on purpose: a backfill script runs
        with no runtime catalogue loaded, and it needs the same answer.
        """
        assert plugin_id_in("astar+org.vinai.vfh-plus") == "org.vinai.vfh-plus"

    def test_something_that_is_not_a_stack_at_all(self) -> None:
        assert plugin_id_in("dwa") is None


class TestProductionRunsOnlyWhatSomebodyPublished:
    def test_the_published_revision_is_what_gets_pinned(self) -> None:
        lookup = _Lookup([REV3, REV4], current={"org.vinai.vfh-plus": "b3"})
        pinned = resolve(
            purpose=RunPurpose.PRODUCTION,
            task_profile_id="t",
            specs=[("astar+dwa", "dwa_coarse"), ("astar+org.vinai.vfh-plus", "")],
            lookup=lookup,
            governance=True,
        )
        assert pinned.candidates[0].bundle_id is None
        assert pinned.candidates[1].revision == 3, "the newest is not the answer; the current is"

    def test_an_unpublished_algorithm_is_refused_with_what_to_do(self) -> None:
        lookup = _Lookup([REV4], current={})
        with pytest.raises(IdentityError) as refusal:
            resolve(
                purpose=RunPurpose.PRODUCTION,
                task_profile_id="t",
                specs=[("astar+org.vinai.vfh-plus", "")],
                lookup=lookup,
                governance=True,
            )
        assert "publishes one" in str(refusal.value)

    def test_naming_a_bundle_outright_is_refused(self) -> None:
        """That is what a validation run is, and it says so.

        Allowing it here would let a conclusion rest on a revision the
        requester chose by hand — which is exactly the thing publishing
        exists to take out of an individual's hands.
        """
        lookup = _Lookup([REV3, REV4], current={"org.vinai.vfh-plus": "b3"})
        with pytest.raises(IdentityError, match="validation run"):
            resolve(
                purpose=RunPurpose.PRODUCTION,
                task_profile_id="t",
                specs=[("astar+org.vinai.vfh-plus", "")],
                bundle_ids=["b4"],
                lookup=lookup,
                governance=True,
            )


class TestBeforePublishingExists:
    """With the flag off, "not published" is not a state anything can be in.

    Refusing on it would refuse runs that are perfectly ordinary on a
    deployment that has not turned publishing on — which is every
    deployment on the day this ships.
    """

    def test_an_imported_stack_still_pins_the_newest_runnable_one(self) -> None:
        lookup = _Lookup([REV3, REV4], current={})
        pinned = resolve(
            purpose=RunPurpose.PRODUCTION,
            task_profile_id="t",
            specs=[("astar+org.vinai.vfh-plus", "")],
            lookup=lookup,
            governance=False,
        )
        assert pinned.candidates[0].revision == 4

    def test_a_stack_naming_nothing_at_all_is_still_refused(self) -> None:
        with pytest.raises(IdentityError, match="nothing knows about"):
            resolve(
                purpose=RunPurpose.PRODUCTION,
                task_profile_id="t",
                specs=[("astar+org.other.missing", "")],
                lookup=_Lookup([]),
                governance=False,
            )


class TestAValidationRunWatchesWhatNobodyHasPublished:
    def test_it_may_name_the_bundle(self) -> None:
        lookup = _Lookup([REV3, REV4], current={"org.vinai.vfh-plus": "b3"})
        pinned = resolve(
            purpose=RunPurpose.VALIDATION,
            task_profile_id="t",
            specs=[("astar+org.vinai.vfh-plus", "")],
            bundle_ids=["b4"],
            lookup=lookup,
            governance=True,
        )
        assert pinned.candidates[0].revision == 4
        assert pinned.purpose is RunPurpose.VALIDATION


class TestRecheckingAtStart:
    """A check, never a second resolution.

    Re-resolving would run whatever is current now and say nothing.
    Comparing against the pin lets the job fail carrying the name of the
    thing that moved.
    """

    def _pinned(self, purpose=RunPurpose.PRODUCTION):
        lookup = _Lookup([REV3, REV4], current={"org.vinai.vfh-plus": "b3"})
        return (
            resolve(
                purpose=purpose,
                task_profile_id="t",
                specs=[("astar+org.vinai.vfh-plus", "")],
                lookup=lookup,
                governance=True,
            ),
            lookup,
        )

    def test_nothing_moved_and_it_passes(self) -> None:
        pinned, lookup = self._pinned()
        recheck(pinned, lookup, governance=True)

    def test_a_newer_revision_published_in_between_stops_the_job(self) -> None:
        pinned, lookup = self._pinned()
        lookup._current["org.vinai.vfh-plus"] = "b4"
        with pytest.raises(IdentityError) as refusal:
            recheck(pinned, lookup, governance=True)
        assert "no longer the published one" in str(refusal.value)

    def test_a_disabled_bundle_stops_the_job_and_says_why(self) -> None:
        pinned, lookup = self._pinned()
        lookup.get("b3").status = type("S", (), {"value": "disabled"})()
        lookup.get("b3").disabled_reason = "unsafe near glass"
        with pytest.raises(IdentityError) as refusal:
            recheck(pinned, lookup, governance=True)
        assert "unsafe near glass" in str(refusal.value)

    def test_a_held_bundle_stops_a_production_job(self) -> None:
        pinned, lookup = self._pinned()
        lookup.get("b3").status = type("S", (), {"value": "held"})()
        with pytest.raises(IdentityError, match="on hold"):
            recheck(pinned, lookup, governance=True)

    def test_a_validation_job_only_minds_being_disabled(self) -> None:
        """It exists to run something unpublished, so it cannot mind that."""
        pinned, lookup = self._pinned(purpose=RunPurpose.VALIDATION)
        lookup._current["org.vinai.vfh-plus"] = "b4"
        recheck(pinned, lookup, governance=True)
        lookup.get("b3").status = type("S", (), {"value": "disabled"})()
        with pytest.raises(IdentityError):
            recheck(pinned, lookup, governance=True)


class TestTheProviderFingerprint:
    def test_it_does_not_depend_on_the_order_providers_were_listed(self) -> None:
        assert provider_fingerprint(["lidar_2d", "pose"]) == provider_fingerprint(
            ["pose", "lidar_2d"]
        )

    def test_a_different_set_is_a_different_deployment(self) -> None:
        assert provider_fingerprint(["lidar_2d"]) != provider_fingerprint(["lidar_2d", "pose"])
