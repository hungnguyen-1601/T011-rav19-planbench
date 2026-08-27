"""What the platform keeps, and what the submitter is told.

The container running a graded analyst has no network. It does have
stderr, and stderr is a place a whole hidden packet fits. So the
platform holds three things the submitter never receives — stderr, the
raw frame transcript, and the prompts and responses of the graded run —
and hands back a metric table plus a closed error code.

**A case is named by a token, not by its id.** "Your analyst crashed on
``narrow-gap-007``" tells a submitter which hidden case exists and what
it is about. The token is stable within one gate run, so a submitter can
say "the third failure" and mean something, and means nothing outside it.

**Truncation is announced.** A byte cap that silently drops the end of a
log is a log that lies about what happened; the marker says how much
went, so a reader knows to ask the platform for the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planbench_explanation.versioning import artifact_checksum

__all__ = ["RestrictedArtifact", "case_token", "public_error"]

#: Cap for one restricted stream. Generous enough to hold a real
#: traceback, small enough that a container narrating a packet one line
#: at a time fills it and gets cut.
MAX_RESTRICTED_BYTES = 256 * 1024

#: Every code a submitter may be told. Closed: an error message written
#: for a human is an error message that eventually quotes the input.
PUBLIC_ERROR_CODES: frozenset[str] = frozenset(
    {
        "analyst_raised",
        "protocol_violation",
        "budget_exceeded",
        "timeout",
        "container_exited",
        "platform_error",
    }
)


def case_token(case_id: str, *, run_salt: str) -> str:
    """A name for one case that is stable in this run and useless outside.

    Salted with the run so the same case in two gate runs gets two
    tokens: a submitter who kept the tokens from a previous attempt must
    not be able to line them up with this one and learn which cases are
    the same.
    """
    return artifact_checksum({"case": case_id, "salt": run_salt})[:12]


@dataclass
class RestrictedArtifact:
    """Bytes the platform keeps. Appending past the cap is announced."""

    name: str
    _chunks: list[str] = field(default_factory=list)
    _size: int = 0
    truncated_bytes: int = 0

    def append(self, text: str) -> None:
        room = MAX_RESTRICTED_BYTES - self._size
        encoded = text.encode("utf-8")
        if room <= 0:
            self.truncated_bytes += len(encoded)
            return
        if len(encoded) > room:
            self._chunks.append(encoded[:room].decode("utf-8", errors="ignore"))
            self._size = MAX_RESTRICTED_BYTES
            self.truncated_bytes += len(encoded) - room
            return
        self._chunks.append(text)
        self._size += len(encoded)

    @property
    def text(self) -> str:
        """Platform-side only. Never travels with a gate report."""
        body = "".join(self._chunks)
        if self.truncated_bytes:
            return body + f"\n[{self.truncated_bytes} bytes truncated at the restricted cap]"
        return body

    @property
    def size(self) -> int:
        return self._size


def public_error(code: str, *, case_id: str, run_salt: str) -> dict[str, str]:
    """What the submitter gets: a closed code and an anonymous token."""
    if code not in PUBLIC_ERROR_CODES:
        # A code nobody enumerated is prose, and prose is how the case id
        # ends up in the submitter's copy.
        code = "platform_error"
    return {"error": code, "case": case_token(case_id, run_salt=run_salt)}
