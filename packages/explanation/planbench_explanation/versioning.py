"""What an explanation artifact must say about the world that produced it.

An explanation is a *derived* artifact: every number in it was computed
somewhere else, under conditions recorded somewhere else. So the header
below carries two kinds of thing and nothing in between.

**A one-way reference to the source of record.** The Decision Card's
manifest (HĐ-13) stays the single description of the run; an explanation
points at it by path and checksum and copies **no field out of it**.
Copying would create a second place where ``anchor_config_version`` is
written down, and the two would eventually disagree — at which point the
explanation would be describing a run that never happened while looking
perfectly well-formed. :mod:`tests.test_explanation_contracts` asserts
the header's field names do not intersect the manifest schema's, so this
rule is enforced rather than remembered.

**Five versions the explanation layer owns.** These are the inputs the
manifest cannot know about, and each one changes what the layer would
output from byte-identical run data:

``explanation_schema_version``
    the shape of the ledger objects themselves.
``promotion_matrix_version``
    the rules that turned records into claims. Two artifacts with the
    same evidence and different matrix versions may legitimately carry
    different claim levels; without this field that difference looks
    like a bug in one of them.
``detector_version``
    the detectors that produced the observations (E3).
``knowledge_base_version``
    the curated KB entries a claim may cite (E3).
``tool_catalog_version``
    which tool cards, at which versions, were on the menu.

Nothing here is optional and nothing has a default. A header that can
omit a version is a header that will omit it exactly once, in the
artifact somebody later needs to reproduce.
"""

from __future__ import annotations

import hashlib
import re

from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.identity import canonical_json

#: Shape of the ledger objects in :mod:`planbench_explanation.ledger`.
#: Bump MINOR to add an optional field, MAJOR to change or remove one.
EXPLANATION_SCHEMA_VERSION = "0.1.0"

#: Version of the deterministic rules in
#: :mod:`planbench_explanation.promotion`. Bump on **any** change that
#: could move a claim between levels, including a change that only makes
#: the layer stricter.
PROMOTION_MATRIX_VERSION = "0.1.0"

#: Version of the checksum recipe below. Part of the payload, so an
#: artifact hashed under an older recipe cannot silently compare equal to
#: one hashed under a newer one.
ARTIFACT_CHECKSUM_VERSION = "1"

#: Every checksum this layer stores is a SHA-256 hex digest, because
#: every one of them is produced by the two functions above. Stating the
#: shape lets a schema refuse ``"x"`` — a value that satisfies "not
#: empty" and identifies nothing.
CHECKSUM_PATTERN = r"^[0-9a-f]{64}$"

#: How a piece of running code is named: a full git commit, or a
#: container digest. Both are what the manifest already records
#: (``git_sha``, ``docker_image_digest``), so the explanation layer
#: names code the same way rather than inventing a third convention.
#:
#: Short SHAs are refused on purpose. Seven hex characters identify a
#: commit *in a repository at a moment*; the point of recording which
#: build produced a checker result is that somebody can still resolve it
#: after the repository has grown.
CODE_REF_PATTERN = r"^(git:[0-9a-f]{40}|sha256:[0-9a-f]{64})$"


def validate_code_ref(value: str, *, field: str) -> str:
    """Check a git-commit or container-digest reference, or explain why not."""
    if not re.fullmatch(CODE_REF_PATTERN, value):
        raise ValueError(
            f"{field}={value!r} is not a code reference; write git:<40 hex> for a "
            "commit or sha256:<64 hex> for a container digest. A short SHA or a "
            "free-form label cannot be resolved back to the build that ran."
        )
    return value


class ExplanationArtifactHeader(BaseModel):
    """Provenance every explanation artifact carries, before any content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Path of the manifest of the decision this explains, relative to the
    #: artifact root. A reference, never a copy.
    source_manifest_ref: str = Field(min_length=1)
    #: SHA-256 of that manifest's bytes. The reference is worth nothing
    #: without it: a manifest is a mutable file on disk, and an
    #: explanation that outlived an edit of its source would keep
    #: describing the run it was built from with no way to notice.
    source_manifest_checksum: str = Field(pattern=CHECKSUM_PATTERN)

    explanation_schema_version: str = Field(min_length=1)
    promotion_matrix_version: str = Field(min_length=1)
    detector_version: str = Field(min_length=1)
    knowledge_base_version: str = Field(min_length=1)
    tool_catalog_version: str = Field(min_length=1)

    @classmethod
    def for_current_code(
        cls,
        *,
        source_manifest_ref: str,
        source_manifest_checksum: str,
        detector_version: str,
        knowledge_base_version: str,
        tool_catalog_version: str,
    ) -> ExplanationArtifactHeader:
        """Header stamped with the versions this code implements.

        The two versions the *code* owns are filled in here rather than
        by each caller, for the reason ``CONTRACTS_VERSION`` lives in one
        module: a caller that passes its own idea of the schema version
        will pass a stale one.
        """
        return cls(
            source_manifest_ref=source_manifest_ref,
            source_manifest_checksum=source_manifest_checksum,
            explanation_schema_version=EXPLANATION_SCHEMA_VERSION,
            promotion_matrix_version=PROMOTION_MATRIX_VERSION,
            detector_version=detector_version,
            knowledge_base_version=knowledge_base_version,
            tool_catalog_version=tool_catalog_version,
        )


def artifact_checksum(payload: object) -> str:
    """SHA-256 of a JSON-safe payload, hashed the one canonical way.

    Reuses :func:`planbench_schemas.identity.canonical_json` so an
    explanation artifact and a candidate id agree on what "the same
    object" means. The recipe version is inside the hash, not beside it.
    """
    body = canonical_json({"v": ARTIFACT_CHECKSUM_VERSION, "payload": payload})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def file_checksum(data: bytes) -> str:
    """SHA-256 of raw file bytes — what ``source_manifest_checksum`` holds."""
    return hashlib.sha256(data).hexdigest()
