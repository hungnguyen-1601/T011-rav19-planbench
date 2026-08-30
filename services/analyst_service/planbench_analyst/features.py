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

``filter_tool_menu`` and ``auto_route_checker`` landed at W3 and are
still off by default. The second one is the only flag here that changes
what a *metric means* rather than what the model is shown:
``checker_selection`` stops being "did the model pick the right check"
and becomes "did the code". The report separates the two, which is why
the flag has to be inside the checksum — a run cannot be graded under
one reading and replayed under the other.
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
    #: W4's discriminated union. Off is the shape the answer had before
    #: W4: one object carrying both a final statement and a statement
    #: written before its check. E6 measures whether asking the model to
    #: commit to a branch first is worth what it costs to read.
    discriminated_union: bool = True
    #: A3's deterministic critic — the ranking and the "this looks thin"
    #: flags. Off is the arm E7 compares against, because a critic that
    #: nobody has shown is worth its place is a habit rather than a
    #: component.
    critic: bool = True
    #: W3: hide tools whose evidence this run cannot serve.
    filter_tool_menu: bool = False
    #: W3: route to a checker deterministically after the model declares.
    auto_route_checker: bool = False
    #: Tell the model it may state a magnitude as a ref in braces.
    #:
    #: The other half of the same problem `floor_when_silent` covers
    #: from behind: that one stops a blank screen, this one stops the
    #: sentence being lost in the first place.
    magnitude_placeholders: bool = False
    #: Show the platform's own answer when nothing the model said survived.
    #:
    #: Sixty per cent of hold-out rounds ended blank, every one because a
    #: number in a sentence took the sentence with it, while the floor —
    #: what fired, and a difference only where one was found — was
    #: computable from the packet for nothing the whole time. Off by
    #: default like the rest: it changes what a reader is shown, and no
    #: arm already measured was measured with it.
    floor_when_silent: bool = False
    #: Ask once more when every proposal was removed over how it was
    #: written rather than over what it claimed.
    #:
    #: Off by default for the same reason as the gate beside it. See
    #: :data:`planbench_analyst.episode_runner.REWORDABLE_RULES` for
    #: which removals count and which deliberately do not.
    reword_once: bool = False
    #: Append the rule saying a contrast cites two kinds of ref.
    #:
    #: A prompt arm rather than an input arm: it changes nothing the
    #: model is shown about this episode, only what it is told the
    #: platform will accept. Off by default, because every arm already
    #: measured ran without it.
    contrast_citation_rule: bool = False
    #: The round is about one episode rather than the whole run.
    #:
    #: Not an input toggle like the four above: it selects **which
    #: question was asked**. A round graded on one scope and replayed on
    #: the other is not the same system, so the runner refuses a packet
    #: of the wrong shape rather than reading it — the two are similar
    #: enough that a mismatch would otherwise run to completion and
    #: answer confidently about the wrong thing.
    episode_scope: bool = False
    #: Show the run's aggregates beside an episode, as background.
    #:
    #: Nothing in that block carries a ref, so it cannot be cited
    #: whatever this flag says; the arm measures whether *seeing* it
    #: changes the answer. Meaningless without ``episode_scope``, and
    #: refused there rather than ignored — an arm reporting that it ran
    #: a setting it silently dropped is the one failure nothing
    #: downstream can detect.
    run_context: bool = False

    def __post_init__(self) -> None:
        if self.run_context and not self.episode_scope:
            raise FeatureRefusal(
                "run_context shows the run beside one episode, and there is no "
                "episode in a run-scope round; an arm that reported having run "
                "this setting while it was quietly dropped would be measuring "
                "nothing and saying so to nobody"
            )

    @property
    def as_config(self) -> dict[str, bool]:
        """The flags as the identity checksum carries them."""
        return dict(sorted(asdict(self).items()))
