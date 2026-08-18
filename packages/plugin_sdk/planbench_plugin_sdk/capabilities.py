"""Capability references: open URIs, with the v1 tokens as aliases.

The extension surface is a namespaced URI with a major version —
``planbench://channel/lidar-2d@1``, ``org.vendor://channel/radar-cube@1``
— because a closed enum cannot admit a capability the core has never
heard of. The G6 vocabulary (``lidar_2d``, ``human_state_estimates``)
stays exactly what it is: the **canonical spelling** of the two
capabilities that existed before URIs did.

**Canonicalisation is the identity rule** (plan §5.2 rule 1). Every
requirement is reduced by :func:`canonical_requirement` before anything
hashes it: a v1 token stays itself, a URI that aliases a v1 token
becomes the token, any other well-formed URI stays a URI. So a manifest
declaring ``planbench://channel/lidar-2d@1`` and one declaring
``lidar_2d`` produce the same ``candidate_id`` — and every candidate
that predates this package keeps the id it was measured under.

A reference that is neither a known token nor a well-formed URI raises
:class:`~planbench_plugin_sdk.errors.UnknownCapabilityError` with close
matches, at parse time. Whether a well-formed URI actually *resolves* is
the manifest's business (it may declare the schema itself) — see
:mod:`planbench_plugin_sdk.manifest`.
"""

from __future__ import annotations

import re
from difflib import get_close_matches

from pydantic import BaseModel, ConfigDict

from planbench_plugin_sdk.errors import UnknownCapabilityError

#: ``namespace://channel/name@major``. Lowercase throughout so two
#: spellings of one capability cannot hash apart; the major is part of
#: the reference because payload schema changes are breaking by definition.
URI_PATTERN = re.compile(
    r"^(?P<namespace>[a-z0-9][a-z0-9.+-]*)://channel/"
    r"(?P<name>[a-z0-9][a-z0-9-]*)@(?P<major>[1-9][0-9]*)$"
)

PLANBENCH_NAMESPACE = "planbench"

#: The v1 observation tokens and the URIs they alias. **This mapping is
#: append-only**: the token side is frozen into every stored candidate_id,
#: and tests pin it against ``planbench_schemas.observations`` so the two
#: vocabularies cannot drift apart silently.
V1_TOKEN_TO_URI: dict[str, str] = {
    "lidar_2d": "planbench://channel/lidar-2d@1",
    "human_state_estimates": "planbench://channel/human-state-estimates@1",
}

URI_TO_V1_TOKEN: dict[str, str] = {uri: token for token, uri in V1_TOKEN_TO_URI.items()}

#: Channels the core itself defines (plan §5.2). The two alias targets
#: plus the ones every stack already consumes implicitly; providers for
#: them arrive in H3, but the *references* must resolve from day one so
#: a manifest can require them.
BUILTIN_CHANNEL_URIS: frozenset[str] = frozenset(
    {
        "planbench://channel/robot-state@1",
        "planbench://channel/global-path@1",
        *V1_TOKEN_TO_URI.values(),
    }
)


class CapabilityRef(BaseModel):
    """One parsed capability URI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str
    name: str
    major: int

    @classmethod
    def parse(cls, uri: str) -> CapabilityRef:
        match = URI_PATTERN.match(uri)
        if match is None:
            raise UnknownCapabilityError(
                f"{uri!r} is not a capability URI "
                "(expected namespace://channel/name@major, all lowercase).",
                suggestions=_close_matches(uri),
            )
        return cls(
            namespace=match.group("namespace"),
            name=match.group("name"),
            major=int(match.group("major")),
        )

    @property
    def uri(self) -> str:
        return f"{self.namespace}://channel/{self.name}@{self.major}"


def _known_spellings() -> tuple[str, ...]:
    return tuple(V1_TOKEN_TO_URI) + tuple(sorted(BUILTIN_CHANNEL_URIS))


def _close_matches(value: str) -> tuple[str, ...]:
    return tuple(get_close_matches(value, _known_spellings(), n=3, cutoff=0.6))


def canonical_requirement(reference: str) -> str:
    """The one spelling a requirement hashes under.

    v1 token → itself; URI aliasing a v1 token → the token; any other
    well-formed URI → itself. Anything else is refused here, with
    suggestions, because letting it through would hand the typo to G6 to
    report as a hardware incompatibility that does not exist.
    """
    if reference in V1_TOKEN_TO_URI:
        return reference
    ref = CapabilityRef.parse(reference)  # raises with suggestions on syntax
    return URI_TO_V1_TOKEN.get(ref.uri, ref.uri)


def canonical_requirements(references: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Canonicalise, deduplicate and sort — two spellings of one set must
    compare and hash equal, same argument as ``canonical_observations``."""
    return tuple(sorted({canonical_requirement(reference) for reference in references}))


def is_builtin(canonical: str) -> bool:
    """True when the core itself defines this capability."""
    return canonical in V1_TOKEN_TO_URI or canonical in BUILTIN_CHANNEL_URIS
