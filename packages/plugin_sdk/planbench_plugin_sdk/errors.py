"""The SDK's refusals, each named for what the author did.

All inherit ``ValueError`` so a caller that only wants "this manifest is
bad" can catch one thing, while tests and error messages can name the
specific defect.
"""

from __future__ import annotations

from collections.abc import Sequence


class PluginSDKError(ValueError):
    """Base for every refusal this package raises."""


class ManifestError(PluginSDKError):
    """The manifest does not describe a plugin (schema-level defect)."""


class IncompatibleProtocolError(PluginSDKError):
    """The manifest was written against a plugin API this SDK cannot parse."""


class UnknownCapabilityError(PluginSDKError):
    """A capability reference that resolves to nothing.

    Carries close-match ``suggestions`` because the closed G6 vocabulary
    exists precisely so a typo dies at parse time with a pointer, rather
    than surfacing later as ``registered_but_missing_provider`` — which
    reads as missing infrastructure when the truth is a misspelling.
    """

    def __init__(self, message: str, *, suggestions: Sequence[str] = ()) -> None:
        self.suggestions = tuple(suggestions)
        if self.suggestions:
            message = f"{message} Did you mean: {', '.join(self.suggestions)}?"
        super().__init__(message)


class DuplicatePluginError(PluginSDKError):
    """Two different manifests claim one (id, version)."""
