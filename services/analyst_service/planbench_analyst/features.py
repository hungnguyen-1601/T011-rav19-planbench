"""Which inputs a round was actually run with — W1.7.

Every arm of the input ablation is a *configuration*, and a
configuration that is not part of the run's identity is one two runs can
disagree about while looking identical in the artifact. That is the
failure this module exists to prevent: a bundle graded with the timeline
block in the prompt and replayed without it would produce two different
answers under one checksum, and the second reading would look like model
variance.

So the flags are one frozen object, they go into
:func:`~planbench_analyst.identity.runtime_config_checksum`, and every
one of them is independent. A pair that only moves together is one arm
wearing two names, and E3's two-by-two would have two cells nobody could
fill.

**Two flags here are declared and not yet implemented**, and they refuse
rather than doing nothing. ``filter_tool_menu`` and ``auto_route_checker``
are W3's, named now because W3 changes what ``checker_selection`` means
and a preregistration written against a checksum that could not express
the change would have to be rewritten after the fact. A flag that
accepted ``True`` and quietly changed nothing would be worse than its
absence: the arm would report as run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

__all__ = ["FeatureRefusal", "RoundFeatures"]


class FeatureRefusal(ValueError):
    """A feature combination this build cannot honour."""


@dataclass(frozen=True)
class RoundFeatures:
    """The inputs and behaviours one round is run with.

    Defaults are **what the platform did before W1.7** rather than what
    a baseline should be: the packet's own blocks are shown, the two
    retrieval inputs are not. A default that changed behaviour would
    silently re-run every existing measurement under a new arm.

    A baseline is therefore stated, not assumed — B1 names its arm
    vector explicitly, and that vector is in the checksum.
    """

    #: M1: what each candidate scored. In the packet already; the flag
    #: decides whether the analyst is shown it.
    measurements: bool = True
    #: M2: how the exemplar episodes went while they were going.
    timelines: bool = True
    #: The curated knowledge base, offered by retrieval and resolved by
    #: the platform.
    knowledge: bool = False
    #: M3: the natures of the algorithms this packet ran.
    traits: bool = False
    #: W2: show the platform's shortlist of mechanisms.
    candidate_shortlist: bool = False
    #: W2: and, separately, how each one could be checked. Separate
    #: because E4a measures the prior and E4b the hint, and bundled, a
    #: gain in either would be reported as a gain in both.
    verification_options: bool = False
    #: W3: hide tools whose evidence this run cannot serve.
    filter_tool_menu: bool = False
    #: W3: route to a checker deterministically after the model declares.
    auto_route_checker: bool = False

    def __post_init__(self) -> None:
        pending = [
            name
            for name in ("filter_tool_menu", "auto_route_checker")
            if getattr(self, name)
        ]
        if pending:
            raise FeatureRefusal(
                f"{sorted(pending)} is declared for W3 and not implemented in this "
                "build. Refused rather than ignored: a flag that accepts True and "
                "changes nothing reports an arm as run that was never run."
            )

    @property
    def as_config(self) -> dict[str, bool]:
        """The flags as the identity checksum carries them."""
        return dict(sorted(asdict(self).items()))
