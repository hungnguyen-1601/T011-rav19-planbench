"""What a plugin needs, in three strengths (plan §5.1).

``all_of`` — the episode cannot run without every one of these.
``any_of`` — at least one of these must be available; a controller that
can work from either a costmap or a raw scan says so here instead of
faking two plugins.
``optional`` — used when present, never blocking. Declared anyway
because an undeclared channel is a channel the host will not grant:
plugins receive exactly what they asked for, nothing else.

Entries are canonicalised at parse (v1 token stays a token, an aliasing
URI becomes its token), so requirement sets hash and compare on one
spelling — the candidate-identity rule of §5.2 applied at the door.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from planbench_plugin_sdk.capabilities import canonical_requirements


class RequirementSet(BaseModel):
    """A plugin's declared data needs, canonicalised."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()

    @field_validator("all_of", "any_of", "optional", mode="before")
    @classmethod
    def _canonical(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return canonical_requirements(list(value))
        return value

    def mentioned(self) -> tuple[str, ...]:
        """Every reference this set names, for resolution checks."""
        return tuple(sorted({*self.all_of, *self.any_of, *self.optional}))

    def missing_from(self, available: frozenset[str] | set[str]) -> tuple[str, ...]:
        """What blocks this plugin, given the capabilities on offer.

        ``all_of`` entries are reported individually. An unsatisfied
        ``any_of`` is reported as one joined entry, because "give me any
        one of these" has no single missing name — reporting all of them
        as individually required would tell the operator to build three
        providers where one suffices.
        """
        missing = [entry for entry in self.all_of if entry not in available]
        if self.any_of and not any(entry in available for entry in self.any_of):
            missing.append("any of: " + " | ".join(self.any_of))
        return tuple(missing)

    def satisfied_by(self, available: frozenset[str] | set[str]) -> bool:
        return not self.missing_from(frozenset(available))
