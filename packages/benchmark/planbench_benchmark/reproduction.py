"""Why your numbers differ from the paper's.

A reader registers a candidate from a paper, runs it, gets a different
success rate, and has no way to tell whether the gap is the platform, the
deployment, or a parameter the paper never stated. That last one is the
usual answer and the hardest to see: the extraction reports what the
paper said, the registry fills the rest with defaults, and the resulting
configuration looks complete because every field has a value.

This module diffs the two. For each parameter it says which of four
things happened — the paper stated it and the candidate agrees, the paper
stated it and the candidate differs, the paper was silent and a default
was taken, or the paper stated something this platform cannot express —
and then checks the deployment against the conditions the paper claimed
its result under.

**Nothing is stored, and the shape follows from that.** The platform
deliberately keeps no copy of a paper (``POST /candidates/from-paper``
returns a draft and writes nothing), so this takes the extraction and the
candidate in one call. What is lost is history: two months later nobody
can re-run this diff without the PDF again. That is the price of not
becoming a document store, and it is worth saying out loud rather than
discovering.

**A default is not agreement.** The loudest rule here fires on silence:
a paper that never mentions ``safety_margin`` did not choose 0.05, and a
reproduction that treats the default as the paper's value is comparing
against a configuration nobody published.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from planbench_benchmark.candidates import candidate_from_stack
from planbench_decision.advice import Advice, keep_resolvable, order

__all__ = [
    "REPRODUCTION_CODES",
    "build_comparison",
    "reproduction_advice",
]

REPRODUCTION_CODES: tuple[str, ...] = (
    "RP_CONDITIONS_DIFFER",
    "RP_DEFAULT_TAKEN_FOR_SILENCE",
    "RP_NOT_REPRESENTABLE",
    "RP_PARAM_DIFFERS",
    "RP_STACK_DIFFERS",
    "RP_UNQUOTED_VALUES_DROPPED",
)


def _stated(extraction: Mapping[str, Any]) -> dict[str, Any]:
    """Only the parameters the paper actually stated, keyed by name.

    Taken from ``parameters`` rather than ``params`` because that is the
    list whose entries carry the source sentence. ``params`` is the same
    values flattened for the registry, and a value with no sentence
    behind it is exactly what this module exists to distinguish.
    """
    out: dict[str, Any] = {}
    for item in extraction.get("parameters") or ():
        name = str((item or {}).get("name") or "")
        if name:
            out[name] = (item or {}).get("value")
    return out


def _flat_params(params: Any) -> dict[str, Any]:
    """The controller's tunables, whichever shape they arrive in.

    A built :class:`Candidate` nests them under the controller name —
    ``{"dwa": {"horizon_seconds": 1.5, ...}}`` — while a paper extraction
    and the API's ``CandidateSpec`` both hand over a flat dict. Reading
    only the flat shape reported every stated parameter as ``None here``,
    which turned a diff of two configurations into a diff against
    nothing.

    Unwrapped only when the whole mapping is one key holding a dict, so a
    genuinely flat mapping with one tunable is not mistaken for a wrapper.
    """
    if not isinstance(params, Mapping):
        return {}
    plain = dict(params)
    if len(plain) == 1:
        (only,) = plain.values()
        if isinstance(only, Mapping):
            return dict(only)
    return plain


def build_comparison(
    extraction: Mapping[str, Any],
    candidate: Mapping[str, Any],
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One dict holding the paper, the candidate, and the field-by-field diff.

    The diff is computed here rather than in the rules so a caller can
    render the table without re-deriving it, and so every rule cites a
    path into a structure the caller is already showing.
    """
    stated = _stated(extraction)
    registered = _flat_params(candidate.get("params"))

    # The registry's own defaults for this stack, so "the paper was
    # silent and a default was taken" can name the default rather than
    # merely assert one exists.
    defaults: dict[str, Any] = {}
    stack = str(candidate.get("stack") or extraction.get("stack") or "")
    try:
        defaults = _flat_params(candidate_from_stack(stack, params={}).params)
    except Exception:  # an unknown stack is diagnosed by its own rule
        defaults = {}

    rows: list[dict[str, Any]] = []
    for name in sorted(set(registered) | set(stated) | set(defaults)):
        paper_value = stated.get(name)
        used = registered.get(name, defaults.get(name))
        if name in stated:
            verdict = "agrees" if _same(paper_value, used) else "differs"
        else:
            verdict = "default_taken"
        rows.append(
            {
                "name": name,
                "paper": paper_value,
                "candidate": used,
                "default": defaults.get(name),
                "verdict": verdict,
                "paper_stated": name in stated,
            }
        )

    return {
        "paper": {
            "stack": extraction.get("stack") or "",
            "not_representable": list(extraction.get("not_representable") or ()),
            "claimed_conditions": extraction.get("claimed_conditions") or "",
            "unquoted": extraction.get("unquoted") or 0,
            "assumptions": list(extraction.get("assumptions") or ()),
        },
        "candidate": {
            "candidate_id": candidate.get("candidate_id") or "",
            "stack": stack,
        },
        "deployment": {
            "id": (profile or {}).get("id") or "",
            "map": ((profile or {}).get("environment") or {}).get("map") or "",
        },
        "parameters": rows,
    }


def _same(left: Any, right: Any) -> bool:
    """Equality that tolerates 2 and 2.0, and nothing else.

    A looser comparison would hide the differences this module exists to
    surface; a stricter one would report ``velocity_samples`` as changed
    because JSON round-tripped an int through a float.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= 1e-9
    return left == right


def reproduction_advice(comparison: Mapping[str, Any]) -> tuple[Advice, ...]:
    """What stands between this candidate and the paper's result."""
    try:
        found = tuple(_rules(comparison))
    except Exception:  # noqa: BLE001 — advice must never take a caller down
        return ()
    return order(keep_resolvable(found, dict(comparison)))


def _rules(comparison: Mapping[str, Any]) -> Any:
    paper = dict(comparison.get("paper") or {})
    candidate = dict(comparison.get("candidate") or {})
    deployment = dict(comparison.get("deployment") or {})
    rows: Sequence[Mapping[str, Any]] = list(comparison.get("parameters") or ())
    subject = str(candidate.get("candidate_id") or candidate.get("stack") or "")

    paper_stack = str(paper.get("stack") or "")
    built_stack = str(candidate.get("stack") or "")
    if paper_stack and built_stack and paper_stack != built_stack:
        yield Advice(
            code="RP_STACK_DIFFERS",
            kind="reproduction",
            severity="blocking",
            subject=subject,
            claim=f"the paper describes {paper_stack}, and this candidate is {built_stack}",
            ground="a different stack answers a different question, whatever the parameters say",
            field_path="candidate.stack",
            do="register a candidate on the stack the paper used, or compare like for like",
            do_not="present this as a reproduction of the paper's method",
        )

    for index, row in enumerate(rows):
        if row.get("verdict") == "differs":
            yield Advice(
                code="RP_PARAM_DIFFERS",
                kind="reproduction",
                severity="material",
                subject=str(row.get("name") or ""),
                claim=(
                    f"{row.get('name')} is {row.get('candidate')} here and "
                    f"{row.get('paper')} in the paper"
                ),
                ground="the paper stated this value, so the difference is a choice somebody made",
                field_path=f"parameters[{index}].candidate",
                do="match the paper's value, or say in the report that you changed it and why",
                do_not="report a difference in results while a stated parameter differs",
            )

    silent = [i for i, row in enumerate(rows) if row.get("verdict") == "default_taken"]
    if silent:
        first = rows[silent[0]]
        yield Advice(
            code="RP_DEFAULT_TAKEN_FOR_SILENCE",
            kind="reproduction",
            severity="material",
            subject=subject,
            claim=(
                f"{len(silent)} parameters the paper never stated took this platform's defaults"
            ),
            ground=(
                f"for example {first.get('name')} = {first.get('candidate')}, which the paper "
                "does not mention; a default is not agreement, and the usual reason a "
                "reproduction misses is a value nobody published"
            ),
            field_path=f"parameters[{silent[0]}].default",
            do="say which defaults you took, so a reader can see what the paper left open",
            do_not="describe the configuration as the paper's when most of it is this platform's",
        )

    missing = list(paper.get("not_representable") or ())
    if missing:
        yield Advice(
            code="RP_NOT_REPRESENTABLE",
            kind="reproduction",
            severity="blocking",
            subject=subject,
            claim="the paper specifies something this platform cannot express",
            ground="; ".join(str(item) for item in missing)[:400],
            field_path="paper.not_representable",
            do="state this as a limit of the reproduction, in the report, beside the numbers",
            do_not="call the run a reproduction when part of the method could not be built",
        )

    dropped = paper.get("unquoted")
    if isinstance(dropped, int) and dropped > 0:
        yield Advice(
            code="RP_UNQUOTED_VALUES_DROPPED",
            kind="reproduction",
            severity="material",
            subject=subject,
            claim=f"{dropped} value(s) the model produced were not in the paper and were dropped",
            ground=(
                "each parameter has to carry the sentence it came from; those that cited a "
                "sentence absent from the text were discarded rather than used"
            ),
            field_path="paper.unquoted",
            do="re-read the paper for those parameters and set them by hand if they are stated",
            do_not="assume the extraction was complete because it produced a valid candidate",
        )

    conditions = str(paper.get("claimed_conditions") or "")
    if conditions and deployment.get("id"):
        yield Advice(
            code="RP_CONDITIONS_DIFFER",
            kind="reproduction",
            severity="disclosure",
            subject=str(deployment.get("id")),
            claim=(
                f'the paper claims its result under "{conditions[:120]}", and this runs on '
                f"{deployment.get('id')}"
            ),
            ground=(
                "a navigation result is a statement about a world; two different worlds "
                "produce two numbers that were never comparable"
            ),
            field_path="paper.claimed_conditions",
            do="check the map, the robot and the traffic match before quoting the paper's number",
            do_not="present a difference in results as a difference between the algorithms",
        )
