"""The claim ledger as an artifact: what was proposed, what survived — E4.

E0 defined the objects and the matrix; this is the thing that actually
holds a run's investigation and can be written to disk, read back, and
handed to somebody a month later.

**Refusals are stored, not dropped.** A ledger that kept only its claims
would be a ledger that cannot tell "nobody looked at this" from "three
checks refuted it", and those look identical on a panel: blank. So every
adjudication lands here, promoted or not, with the matrix's own reasons
attached. The panel renders claims; the *audit* reads the whole thing.

**The packet's known unknowns are enforced here, not remembered.** The
ledger takes the packet, reads ``blocked_claim_types`` off it and passes
them into every promotion. A caller cannot forget to, because there is
no path through this module that promotes without them.

**One header, one set of versions.** Everything in a ledger was produced
by one code version against one knowledge base and one tool catalog, and
the header says which. Two claims in one file promoted under different
matrix versions would be a file nobody can reason about.

**Every cross-link is re-checked when the file is read.** An entry holds
four things that must be about each other — the proposal, the record
adjudicating it, the claim promoted from it and the sentence rendered
from that — and the first version checked only the first pair. A
hand-edited artifact could therefore staple another record's claim onto
an entry, or replace the sentence with a stronger one, and satisfy every
validator on the way in.

**And parsing is still not verification.** Those checks make an entry
*internally consistent*, which is a weaker property than it sounds: edit
``level`` from ``mechanism_verified`` to ``intervention_supported``,
re-render the sentence to match, leave the matrix version alone, and
every one of them passes. The schema cannot do better on its own —
whether a record earned a level depends on the tool catalog and the
packet's blocked claim types, neither of which is in the file.

So there are two operations here and they are not interchangeable:

``ClaimLedger.model_validate``
    shape and internal consistency. What you get from reading JSON.
:func:`verify_ledger`
    re-runs the promotion matrix over every stored proposal and record
    with a **trusted** packet and catalog, and compares the whole
    rebuilt artifact against what the file says. This is the one that
    answers "was this produced by the matrix".

A checksum the artifact carries about itself cannot close this: whoever
edited the claim can recompute it. Verification has to re-derive the
conclusion from inputs supplied by the caller, or the trust boundary is
the file itself.

**Re-derivation only counts if the inputs are inputs.** The first
verifier took the statement to re-promote off ``claim.statement``, which
made it circular: swap the claim for a conclusion about a different
passage, re-render the sentence, and the matrix was asked to adjudicate
the forgery, agreed with it, and the verifier passed. The statement is
now :attr:`LedgerEntry.promotion_statement`, written by the builder from
what it actually handed the matrix and required to equal the claim's own
statement — so the swap is caught at parse time and the re-derivation
starts from a field the claim cannot move.

**And the comparison is over the whole rebuilt artifact.** Checking a
list of fields somebody chose is a check on the fields somebody thought
of; ``run_id`` was not one of them, so a ledger relabelled to another run
verified clean. Both dumps are compared in full, and the differing paths
come back on the exception.

**The remaining hole, named.** Re-adjudication proves the conclusions
follow from the inputs *stored in the file*. Rewrite proposal, record and
statement together and the result is self-consistent, so this verifies
it. Catching that needs a digest held where the artifact cannot reach —
signed, or kept by the run store — and this module does not have one.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planbench_explanation.case_packet import CasePacket
from planbench_explanation.ledger import Claim, HypothesisProposal, InvestigationRecord
from planbench_explanation.promotion import PromotionOutcome, promote
from planbench_explanation.render import render_claim, render_no_claim
from planbench_explanation.subjects import H4_ACCOUNTING_COMPLETE
from planbench_explanation.tools import ToolCatalog
from planbench_explanation.versioning import ExplanationArtifactHeader, artifact_checksum


class LedgerRefusal(ValueError):
    """An entry that cannot be admitted to the ledger."""


class LedgerEntry(BaseModel):
    """One hypothesis, its adjudication, and what came of it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    proposal: HypothesisProposal
    record: InvestigationRecord
    #: ``None`` when nothing was promoted. That is the common case and
    #: it is not a failure of the entry — see :attr:`reasons`.
    claim: Claim | None
    #: The promotion matrix's own words, always. This is the field that
    #: distinguishes "no applicable check" from "a checker refuted it",
    #: and a ledger without it cannot be audited.
    reasons: tuple[str, ...]
    #: **The exact statement the matrix was asked to adjudicate.**
    #:
    #: Stored separately from the claim because verification has to
    #: re-run the matrix, and re-running it with a statement read off
    #: the claim would feed the verifier the very thing under suspicion:
    #: change the claim's statement to a different conclusion, re-render
    #: the sentence to match, and a verifier that re-promoted *that*
    #: statement would agree with the forgery. Kept for refused entries
    #: too — what a matrix declined to promote is part of the record,
    #: and the proposal's own wording is not necessarily what was tried.
    promotion_statement: str = Field(min_length=1)
    #: What a panel prints for this entry, template-rendered.
    sentence: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> LedgerEntry:
        if self.record.proposal_ref != self.proposal.hypothesis_id:
            raise LedgerRefusal(
                f"record {self.record.record_id} adjudicates "
                f"{self.record.proposal_ref!r}, not {self.proposal.hypothesis_id!r}"
            )
        if not self.reasons:
            raise LedgerRefusal(
                "an entry with no reasons cannot be audited: a reader cannot tell a "
                "hypothesis nobody could check from one a check refuted"
            )

        claim = self.claim
        if claim is None:
            if self.sentence != render_no_claim("; ".join(self.reasons)):
                raise LedgerRefusal(
                    "an entry with no claim carries a sentence that is not the "
                    "no-claim wording for its reasons; a panel would print a "
                    "conclusion this entry does not hold"
                )
            return self

        if claim.statement != self.promotion_statement:
            raise LedgerRefusal(
                "the claim's statement is not the one the matrix adjudicated; the "
                "sentence a reader sees has to be the sentence the level was granted for"
            )
        if claim.record_ref != self.record.record_id:
            raise LedgerRefusal(
                f"claim {claim.claim_id} was promoted from record {claim.record_ref!r}, "
                f"but sits beside record {self.record.record_id!r}. A claim stapled to "
                "another investigation is a conclusion about evidence nobody linked"
            )
        if claim.proposition_type != self.proposal.proposition_type:
            raise LedgerRefusal(
                f"claim asserts {claim.proposition_type!r} while the proposal asked "
                f"about {self.proposal.proposition_type!r}"
            )
        if claim.subject != self.proposal.proposed_subject:
            raise LedgerRefusal(
                f"claim blames {claim.subject!r} while the proposal proposed "
                f"{self.proposal.proposed_subject!r}"
            )
        if tuple(claim.supports) != tuple(self.proposal.supports):
            raise LedgerRefusal(
                "the claim cites different evidence than the proposal offered; the "
                "citations under a rendered sentence are the part a reader checks"
            )
        if self.sentence != render_claim(claim):
            raise LedgerRefusal(
                "the stored sentence is not what this claim renders to. Wording is "
                "gated by the claim's level, and a sentence free to differ from its "
                "claim is a sentence free to say more than the evidence earned"
            )
        return self

    @property
    def promoted(self) -> bool:
        return self.claim is not None


class ClaimLedger(BaseModel):
    """One run's investigation, whole.

    Parsing one of these says it is *well formed*. It does not say the
    claims in it were promoted rather than written — see
    :func:`verify_ledger`, and do not treat ``model_validate`` as the
    last word before rendering.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    header: ExplanationArtifactHeader
    run_id: str = Field(min_length=1)
    #: Which packet this was investigated from, by checksum. The packet
    #: is the analyst's whole input, so a ledger that cannot name the
    #: one it answered is a set of conclusions about unknown evidence.
    case_packet_checksum: str = Field(min_length=64, max_length=64)
    entries: tuple[LedgerEntry, ...] = ()

    @property
    def claims(self) -> tuple[Claim, ...]:
        """What a panel may render. Often empty, legitimately."""
        return tuple(entry.claim for entry in self.entries if entry.claim is not None)

    @property
    def refused(self) -> tuple[LedgerEntry, ...]:
        return tuple(entry for entry in self.entries if entry.claim is None)

    @model_validator(mode="after")
    def _check(self) -> ClaimLedger:
        ids = [entry.proposal.hypothesis_id for entry in self.entries]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise LedgerRefusal(
                f"hypothesis id(s) {duplicates} appear twice; two adjudications of one "
                "hypothesis in one ledger cannot both be the answer"
            )
        for entry in self.entries:
            if entry.claim is None:
                continue
            if entry.claim.promotion_matrix_version != self.header.promotion_matrix_version:
                raise LedgerRefusal(
                    f"claim {entry.claim.claim_id} was promoted under matrix "
                    f"{entry.claim.promotion_matrix_version} but this ledger says "
                    f"{self.header.promotion_matrix_version}; two rule versions in one "
                    "file is a file nobody can reason about"
                )
        return self


def build_ledger(
    packet: CasePacket,
    adjudications: Sequence[tuple[HypothesisProposal, InvestigationRecord, str]],
    *,
    catalog: ToolCatalog,
    scope: str,
) -> ClaimLedger:
    """Run every proposal through the matrix and keep all of it.

    ``adjudications`` is ``(proposal, record, statement)``: the analyst's
    hypothesis, the orchestrator's adjudication of it, and the sentence a
    template produced for it. The statement is supplied rather than
    generated here because the matrix checks the wording *against the
    level it is about to grant* — which cannot be known before it runs,
    and must not be chosen after.

    The packet's blocked claim types are read off the packet and applied
    to every promotion. There is no argument to override them: a caller
    able to drop the H4 gap would be a caller able to promote a latency
    attribution the platform cannot make.

    Neither is there an argument for whether H4's accounting has landed.
    That used to be a keyword on this function, which meant the party
    being judged could declare the infrastructure finished and lift the
    ceiling on ``perception_provider`` and ``runtime_transport``. It is
    a property of the platform's own code
    (:data:`planbench_explanation.subjects.H4_ACCOUNTING_COMPLETE`), and
    changing it is a promotion-matrix version bump.
    """
    blocked = packet.known_unknowns
    entries = []
    for index, (proposal, record, statement) in enumerate(adjudications):
        outcome: PromotionOutcome = promote(
            claim_id=f"{packet.run_id}-claim-{index:03d}",
            proposal=proposal,
            record=record,
            catalog=catalog,
            statement=statement,
            scope=scope,
            known_unknowns=blocked,
            h4_accounting_complete=H4_ACCOUNTING_COMPLETE,
        )
        sentence = (
            render_claim(outcome.claim)
            if outcome.claim is not None
            else render_no_claim("; ".join(outcome.reasons))
        )
        entries.append(
            LedgerEntry(
                proposal=proposal,
                record=record,
                claim=outcome.claim,
                reasons=outcome.reasons,
                promotion_statement=statement,
                sentence=sentence,
            )
        )

    return ClaimLedger(
        header=packet.header,
        run_id=packet.run_id,
        case_packet_checksum=artifact_checksum(packet.model_dump(mode="json")),
        entries=tuple(entries),
    )


class LedgerVerificationFailure(LedgerRefusal):
    """A stored ledger does not match what the matrix produces."""

    def __init__(self, message: str, mismatches: Sequence[str]) -> None:
        self.mismatches = tuple(mismatches)
        super().__init__(f"{message}: {'; '.join(mismatches)}")


def verify_ledger(
    ledger: ClaimLedger,
    packet: CasePacket,
    *,
    catalog: ToolCatalog,
    scope: str,
) -> ClaimLedger:
    """Re-derive the whole ledger and refuse the file if anything differs.

    The trust boundary is the arguments, not the artifact: ``packet`` and
    ``catalog`` come from the caller, and every entry is recomputed from
    the proposal, the record and the **statement that was adjudicated**,
    all three stored beside each other. A file whose claims were edited
    — level raised, sentence re-rendered to match, matrix version left
    alone, which passes every schema check — fails here, because the
    matrix run over the same record does not produce them.

    The comparison is over the **entire canonical dump**, not a chosen
    list of fields. The first version compared level, qualifiers,
    reasons and sentence, and so let an edited ``run_id`` through while
    its docstring said it refused anything that differed; every field
    somebody thinks to check is a field, and the set of fields nobody
    thought of is the interesting one.

    Returns the freshly built ledger rather than the input. Same content
    by construction once it passes, and it makes the verified object the
    one that continues downstream, so a caller cannot verify and then
    keep rendering the unverified copy.

    **What this cannot do.** Re-adjudication proves the conclusions
    follow from the inputs *in the file*. An attacker who can rewrite
    the whole artifact — statement, proposal and record together —
    produces something self-consistent that this will happily verify.
    Detecting that needs a digest kept somewhere the artifact cannot
    reach: signed, or held by the run store. Stated here rather than
    left for somebody to assume otherwise.
    """
    if ledger.case_packet_checksum != artifact_checksum(packet.model_dump(mode="json")):
        raise LedgerVerificationFailure(
            "this ledger answers a different packet",
            ["case_packet_checksum"],
        )

    rebuilt = build_ledger(
        packet,
        [(entry.proposal, entry.record, entry.promotion_statement) for entry in ledger.entries],
        catalog=catalog,
        scope=scope,
    )

    mismatches = _differences(
        ledger.model_dump(mode="json"), rebuilt.model_dump(mode="json"), path=""
    )
    if mismatches:
        raise LedgerVerificationFailure("stored ledger is not what the matrix produces", mismatches)
    return rebuilt


def _differences(stored: object, fresh: object, *, path: str) -> list[str]:
    """Every place two canonical dumps disagree, by path.

    Paths rather than a boolean because the point of failing is that
    somebody then goes and looks: ``entries.0.claim.level: file
    'intervention_supported' vs matrix 'mechanism_verified'`` is an
    audit line, and "verification failed" is not.
    """
    if isinstance(stored, dict) and isinstance(fresh, dict):
        found: list[str] = []
        for key in sorted(set(stored) | set(fresh)):
            where = f"{path}.{key}" if path else str(key)
            if key not in stored:
                found.append(f"{where}: missing from file")
            elif key not in fresh:
                found.append(f"{where}: not produced by the matrix")
            else:
                found.extend(_differences(stored[key], fresh[key], path=where))
        return found
    if isinstance(stored, list) and isinstance(fresh, list):
        if len(stored) != len(fresh):
            return [f"{path}: file has {len(stored)} entries, the matrix produced {len(fresh)}"]
        return [
            difference
            for index, (left, right) in enumerate(zip(stored, fresh, strict=True))
            for difference in _differences(left, right, path=f"{path}.{index}")
        ]
    if stored != fresh:
        return [f"{path}: file {stored!r} vs matrix {fresh!r}"]
    return []
