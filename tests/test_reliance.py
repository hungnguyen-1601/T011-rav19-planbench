"""What a stored approval is still worth, and what it always says.

The distinction under test is the one the whole publication table exists
to make: *replaced* and *withdrawn* both leave a revision out of the
picker, and only the second says anything about that revision. An
approval made against it has to be able to tell them apart, because "a
newer one exists" is not a reason to stop trusting an older measurement
and "a reviewer pulled it back" is.
"""

from __future__ import annotations

import pytest

from planbench_api.reliance import (
    CODE_DISABLED,
    CODE_HELD,
    CODE_NOT_PINNED,
    CODE_UNPUBLISHED,
    Reliance,
    describe,
    of_run,
)


class _Publication:
    def __init__(self, unpublished_at=None, superseded_at=None):
        self.unpublished_at = unpublished_at
        self.superseded_at = superseded_at


class _Bundle:
    def __init__(self, status="active", reason=""):
        self.status = type("S", (), {"value": status})()
        self.disabled_at = "2026-08-27T00:00:00+00:00" if status == "disabled" else None
        self.disabled_by_user_id = "u1" if status == "disabled" else None
        self.disabled_reason = reason


class _Lookup:
    def __init__(self, bundle=None, publications=()):
        self._bundle = bundle
        self._publications = list(publications)

    def get(self, bundle_id):
        if self._bundle is None:
            raise KeyError(bundle_id)
        return self._bundle

    def publications_for_bundle(self, bundle_id):
        return self._publications


def _imported(**over):
    row = {
        "stack": "astar+org.vinai.vfh-plus",
        "plugin_id": "org.vinai.vfh-plus",
        "bundle_id": "b3",
        "revision": 3,
    }
    row.update(over)
    return row


BUILT_IN = {"stack": "astar+dwa", "plugin_id": None, "bundle_id": None}


class TestTheOrdinaryCase:
    def test_a_built_in_stack_is_always_active(self) -> None:
        """The code shipped with the deployment; nothing can withdraw it."""
        verdict, warning = of_run([BUILT_IN], _Lookup(), governance=True)
        assert verdict is Reliance.ACTIVE and warning is None

    def test_a_published_bundle_is_active(self) -> None:
        lookup = _Lookup(_Bundle(), publications=[_Publication()])
        verdict, _ = of_run([_imported()], lookup, governance=True)
        assert verdict is Reliance.ACTIVE


class TestReplacedIsNotWithdrawn:
    def test_a_superseded_revision_is_still_relied_on(self) -> None:
        """The distinction the publication table is shaped around.

        Somebody published revision 4. That says nothing about whether
        revision 3, which this approval measured, was any good — and an
        approval that quietly stopped counting every time a colleague
        uploaded something would be worth nothing.
        """
        lookup = _Lookup(
            _Bundle(), publications=[_Publication(superseded_at="2026-08-27T00:00:00+00:00")]
        )
        verdict, warning = of_run([_imported()], lookup, governance=True)
        assert verdict is Reliance.ACTIVE
        assert warning is None

    def test_a_withdrawn_revision_suspends_it(self) -> None:
        lookup = _Lookup(
            _Bundle(), publications=[_Publication(unpublished_at="2026-08-27T00:00:00+00:00")]
        )
        verdict, warning = of_run([_imported()], lookup, governance=True)
        assert verdict is Reliance.SUSPENDED
        assert warning["code"] == CODE_UNPUBLISHED


class TestTheTerminalCase:
    def test_disabling_revokes_it_and_carries_the_reason(self) -> None:
        """The sentence a person reads is the reason somebody gave.

        "Revoked" tells them nothing they could act on; "unsafe near
        glass" tells them whether their own deployment is affected.
        """
        lookup = _Lookup(_Bundle(status="disabled", reason="unsafe near glass"))
        verdict, warning = of_run([_imported()], lookup, governance=True)
        assert verdict is Reliance.REVOKED
        assert warning["code"] == CODE_DISABLED
        assert warning["reason"] == "unsafe near glass"
        assert describe(warning)["message"]

    def test_a_hold_suspends_rather_than_revokes(self) -> None:
        lookup = _Lookup(_Bundle(status="held"), publications=[_Publication()])
        verdict, warning = of_run([_imported()], lookup, governance=True)
        assert verdict is Reliance.SUSPENDED
        assert warning["code"] == CODE_HELD


class TestUnknownIsAnAnswer:
    def test_a_run_from_before_identity_was_recorded(self) -> None:
        """Not a failure. Claiming either extreme would be a guess.

        Saying ``active`` would vouch for code nobody can name; saying
        ``revoked`` would condemn a measurement that may be perfectly
        good. The honest answer is that the database cannot say.
        """
        verdict, warning = of_run([_imported(bundle_id=None)], _Lookup(), governance=True)
        assert verdict is Reliance.UNKNOWN
        assert warning["code"] == CODE_NOT_PINNED

    def test_a_bundle_that_has_vanished_from_the_store(self) -> None:
        verdict, _ = of_run([_imported()], _Lookup(bundle=None), governance=True)
        assert verdict is Reliance.UNKNOWN


class TestTheWorstCandidateDecides:
    def test_one_withdrawn_candidate_suspends_the_whole_run(self) -> None:
        """A comparison is only as reliable as its least reliable side."""
        lookup = _Lookup(
            _Bundle(), publications=[_Publication(unpublished_at="2026-08-27T00:00:00+00:00")]
        )
        verdict, _ = of_run([BUILT_IN, _imported()], lookup, governance=True)
        assert verdict is Reliance.SUSPENDED

    def test_revoked_outranks_suspended(self) -> None:
        lookup = _Lookup(_Bundle(status="disabled", reason="x"))
        verdict, warning = of_run([_imported(), _imported(bundle_id=None)], lookup, governance=True)
        assert verdict is Reliance.REVOKED
        assert warning["code"] == CODE_DISABLED


class TestBeforePublishingExists:
    def test_unpublished_is_not_reported_when_nobody_publishes(self) -> None:
        """With the flag off there is no such state to be in.

        Nobody has been asked to publish anything, so reporting every
        stored approval as suspended would be reporting a rule that is
        not in force.
        """
        lookup = _Lookup(_Bundle(), publications=[])
        verdict, warning = of_run([_imported()], lookup, governance=False)
        assert verdict is Reliance.ACTIVE
        assert warning is None

    def test_disabling_still_counts(self) -> None:
        """Because that state exists whether or not publishing does."""
        lookup = _Lookup(_Bundle(status="disabled", reason="x"))
        verdict, _ = of_run([_imported()], lookup, governance=False)
        assert verdict is Reliance.REVOKED


@pytest.mark.parametrize("code", [CODE_DISABLED, CODE_HELD, CODE_UNPUBLISHED, CODE_NOT_PINNED])
def test_every_code_carries_a_sentence(code) -> None:
    """A warning nobody can act on is a warning people learn to skip."""
    described = describe({"code": code})
    assert described["message"], code
