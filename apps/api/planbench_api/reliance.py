"""Whether a stored approval can still be relied on for new work.

Two questions that look like one and are not:

* *What did a person decide, and when?* — ``approval.status``. Nothing
  that happens to an algorithm afterwards may change it. It is a record
  of a human act.
* *May that decision still be acted on?* — this module. It is a property
  of the world now, not of the decision then, so it is **derived on
  read** rather than stored.

Collapsing them leaves only two moves, and both are wrong. Editing
``config_state`` when an algorithm is disabled writes, on somebody's
behalf, that they withdrew an approval they never withdrew. Leaving it
alone lets a dead recommendation go on reading as a live one — the file
still downloads, still names a winner, and says nothing.

**Why an algorithm being replaced is not the same as being withdrawn.**
Publishing revision 4 says nothing about revision 3; a reviewer pulling
revision 3 back says something about it specifically. So a superseded
publication leaves reliance ``active`` and an unpublished one does not.
That distinction is the whole reason ``plugin_publications`` records the
two with different columns rather than as one absence.

``unknown`` is a real answer, not a failure. Runs stored before candidate
identity was recorded cannot say which bundle they used, and claiming
either ``active`` or ``revoked`` for them would be a guess presented as a
fact.
"""

from __future__ import annotations

from enum import StrEnum


class Reliance(StrEnum):
    #: Usable as the basis for new work.
    ACTIVE = "active"
    #: Somebody took the algorithm out of circulation, reversibly — a
    #: hold, or an unpublish. Publishing it again restores this.
    SUSPENDED = "suspended"
    #: The algorithm was disabled, which is terminal. Only a new run and
    #: a new approval can replace this.
    REVOKED = "revoked"
    #: The run predates recorded candidate identity, so which code it
    #: used is not knowable from the database.
    UNKNOWN = "unknown"


#: Worst-first. A run is only as reliable as its least reliable
#: candidate, so the ordering is what ``max`` is taken over.
_SEVERITY = {
    Reliance.REVOKED: 3,
    Reliance.UNKNOWN: 2,
    Reliance.SUSPENDED: 1,
    Reliance.ACTIVE: 0,
}

#: Codes that travel with the artefact. Named rather than composed at the
#: call site so the interface and the exported file agree on the string.
CODE_DISABLED = "algorithm_disabled_after_approval"
CODE_HELD = "algorithm_held"
CODE_UNPUBLISHED = "algorithm_unpublished"
CODE_NOT_PINNED = "identity_not_pinned"


def of_candidate(candidate: dict, lookup) -> tuple[Reliance, str, dict]:
    """Reliance for one pinned candidate, with the reason and its facts.

    ``lookup`` is the plugin service: ``get(bundle_id)`` for the bundle,
    ``publication_for_bundle(bundle_id)`` for whether it is still
    published. Passed in rather than imported so this can be exercised
    without a database.
    """
    bundle_id = candidate.get("bundle_id")
    plugin_id = candidate.get("plugin_id")
    if not plugin_id:
        # Built-in. The code shipped with the deployment; there is
        # nothing that could have been withdrawn.
        return Reliance.ACTIVE, "", {}
    if not bundle_id:
        return (
            Reliance.UNKNOWN,
            CODE_NOT_PINNED,
            {"stack": candidate.get("stack", ""), "plugin_id": plugin_id},
        )

    try:
        record = lookup.get(bundle_id)
    except Exception:  # noqa: BLE001 - a bundle nobody can find is unknowable
        return Reliance.UNKNOWN, CODE_NOT_PINNED, {"bundle_id": bundle_id}

    facts = {
        "bundle_id": bundle_id,
        "plugin_id": plugin_id,
        "revision": candidate.get("revision"),
        "stack": candidate.get("stack", ""),
    }
    status = getattr(record.status, "value", str(record.status))
    if status == "disabled":
        return (
            Reliance.REVOKED,
            CODE_DISABLED,
            facts
            | {
                "disabled_at": record.disabled_at,
                "disabled_by": record.disabled_by_user_id,
                "reason": record.disabled_reason or "",
            },
        )
    if status == "held":
        return Reliance.SUSPENDED, CODE_HELD, facts

    published = [
        row for row in lookup.publications_for_bundle(bundle_id) if row.unpublished_at is None
    ]
    if published:
        # Superseded counts. "There is a newer revision" is not a
        # statement about this one.
        return Reliance.ACTIVE, "", {}
    return Reliance.SUSPENDED, CODE_UNPUBLISHED, facts


def of_run(candidates: list[dict], lookup, governance: bool) -> tuple[Reliance, dict | None]:
    """The worst answer across a run's candidates, and why.

    With governance off, an unpublished bundle is not a state anything
    can be in — nobody has been asked to publish anything — so only the
    two that exist regardless are reported: disabled, and held.
    """
    worst = Reliance.ACTIVE
    warning: dict | None = None
    for candidate in candidates or []:
        verdict, code, facts = of_candidate(candidate, lookup)
        if not governance and code == CODE_UNPUBLISHED:
            continue
        if _SEVERITY[verdict] > _SEVERITY[worst]:
            worst = verdict
            warning = {"code": code, **facts} if code else None
    return worst, warning


#: What each code says, in the sentence the file carries.
MESSAGES = {
    CODE_DISABLED: (
        "Thuật toán của cấu hình này đã bị vô hiệu hoá sau khi cấu hình được phê duyệt. "
        "File được giữ để kiểm toán và tái lập bằng chứng; không dùng cho một mô phỏng mới."
    ),
    CODE_HELD: (
        "Thuật toán của cấu hình này đang được người duyệt giữ lại để xem xét. File vẫn "
        "đọc được; chờ họ trả lời trước khi dùng cho việc mới."
    ),
    CODE_UNPUBLISHED: (
        "Bản thuật toán mà cấu hình này đo trên đó đã bị rút khỏi danh mục. File được giữ "
        "để kiểm toán; muốn dùng lại phải publish lại rồi chạy và duyệt lần nữa."
    ),
    CODE_NOT_PINNED: (
        "Lượt chạy này có trước khi hệ thống ghi lại định danh thuật toán, nên không nói "
        "được nó đã chạy bản nào. Chạy scripts/backfill_run_candidates.py để đối chiếu."
    ),
}


def describe(warning: dict | None) -> dict | None:
    """Attach the sentence to the facts, for the exported artefact."""
    if not warning:
        return None
    code = warning.get("code", "")
    return {
        "code": code,
        "message": MESSAGES.get(code, ""),
        **{key: value for key, value in warning.items() if key != "code"},
    }


__all__ = [
    "CODE_DISABLED",
    "CODE_HELD",
    "CODE_NOT_PINNED",
    "CODE_UNPUBLISHED",
    "MESSAGES",
    "Reliance",
    "describe",
    "of_candidate",
    "of_run",
]
