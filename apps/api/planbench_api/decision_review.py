"""Submit, claim, acknowledge, decide — the review of a decision run.

The benchmark lane's rule was "only the person you named may answer".
That works while a deployment has one reviewer and fails the moment it
has two or none: a request addressed to somebody on holiday is a request
nobody can answer, and there is no way to say "I am looking at this" so
that a second reviewer does not start on it as well.

So a request is *claimed* before it is decided, and the four steps mean
four different things:

* **submit** — the owner asks. Naming a reviewer is optional; without
  one the request goes to the pool.
* **claim** — a reviewer takes it. Atomic, so two people cannot both
  hold it, and the loser is told somebody got there first rather than
  silently sharing.
* **acknowledge** — they say they have read the evidence. Recorded
  against *this* claim, which is the part that matters below.
* **decide** — approve or reject, with a comment.

**Acknowledgement is per claim, not per run.** Person A can read the
evidence, put the request down, and person B pick it up; if the check
were "has anybody acknowledged this run?", B would then be able to sign
without opening anything. So the condition is an acknowledgement whose
actor is the current claimant and whose time is after the current claim
began. The gap between those two timestamps is also the only evidence
anywhere that a reviewer spent time on it — not proof they understood,
but visible, which one transaction writing both events would not be.
"""

from __future__ import annotations

import logging

from planbench_api.accounts import Capability, User, now_iso
from planbench_api.review import (
    LIVE_STATUSES,
    ReviewConflict,
    ReviewError,
    ReviewNotAllowed,
    ReviewRequest,
    ReviewStage,
    ReviewStatus,
    ReviewSubject,
)

logger = logging.getLogger("planbench.api.decision_reviews")

#: What counts as "I have read the evidence" in the audit trail.
#: ``review`` is the spelling the store has always used; ``acknowledge``
#: is what this lane calls it. Both are the same act.
_ACKNOWLEDGEMENTS = frozenset({"review", "acknowledge"})

#: What ``submission`` reads as, derived from the current request rather
#: than stored. Two places recording who a run is waiting on is how they
#: come to disagree.
SUBMISSION_NONE = "none"
SUBMISSION_OPEN = "submitted"
SUBMISSION_CLAIMED = "in_review"
SUBMISSION_CLOSED = "closed"


def submission_of(request: ReviewRequest | None) -> str:
    if request is None:
        return SUBMISSION_NONE
    if request.status is ReviewStatus.OPEN:
        return SUBMISSION_OPEN
    if request.status is ReviewStatus.CLAIMED:
        return SUBMISSION_CLAIMED
    return SUBMISSION_CLOSED


class DecisionReviewService:
    """The claim workflow, for decision runs only.

    Benchmarks keep their own rules in :class:`ReviewService`; this class
    refuses to touch them. Sharing a table is not sharing a rulebook.
    """

    def __init__(self, reviews, users, runs) -> None:
        self._reviews = reviews
        self._users = users
        self._runs = runs

    # -- reading -------------------------------------------------------

    def current(self, run_id: str) -> ReviewRequest | None:
        """The live request for this run, if there is one."""
        for request in self._reviews.list_for_subject(ReviewSubject.DECISION_RUN.value, run_id):
            if request.status in LIVE_STATUSES:
                return self._release_if_the_holder_lost_the_right(request)
        return None

    def _release_if_the_holder_lost_the_right(self, request: ReviewRequest) -> ReviewRequest:
        """A claim held by somebody who can no longer review is not a claim.

        Checked on read rather than only when a role is revoked, and that
        is deliberate: revoking happens in one place, but *forgetting* to
        release happens everywhere else — a disabled account, a role
        removed directly in the database, a grant that expired. The
        engineers waiting on a run they cannot see the reason for is the
        failure mode, and the reason is always the same one.
        """
        if request.status is not ReviewStatus.CLAIMED or not request.claimed_by_user_id:
            return request
        try:
            holder = self._users.get(request.claimed_by_user_id)
        except Exception:  # noqa: BLE001 - a missing account is a lost right
            holder = None
        if holder is not None and not holder.disabled and holder.can(Capability.RUN_REVIEW):
            return request
        logger.info(
            "released a claim whose holder can no longer review",
            extra={"context": {"request_id": request.id, "holder": request.claimed_by_user_id}},
        )
        return self._reviews.save(
            request.model_copy(
                update={
                    "status": ReviewStatus.OPEN,
                    "claimed_by_user_id": None,
                    "claimed_at": None,
                    "available_to_pool": True,
                }
            )
        )

    def latest(self, run_id: str) -> ReviewRequest | None:
        """The live request, or the last one there was.

        ``current`` answers "who is this waiting on?" and goes quiet once
        nobody is. That is the wrong answer for the interface, which has
        to tell *never sent* from *finished* — the first offers a submit
        button and the second offers the verdict. Two states that look
        identical from one query are two states somebody will conflate.
        """
        live = self.current(run_id)
        if live is not None:
            return live
        history = self.history(run_id)
        return history[-1] if history else None

    def history(self, run_id: str) -> list[ReviewRequest]:
        return self._reviews.list_for_subject(ReviewSubject.DECISION_RUN.value, run_id)

    def queue(self) -> list[ReviewRequest]:
        return self._reviews.list_by_kind(ReviewSubject.DECISION_RUN.value)

    # -- the four steps ------------------------------------------------

    def submit(
        self, run_id: str, owner: User, reviewer_nickname: str = "", comment: str = ""
    ) -> ReviewRequest:
        """Ask for a review. A named reviewer is optional.

        Optional because the alternative is worse in both directions: on
        a deployment with one reviewer, naming them is ceremony; on one
        with several, the requester usually does not know who is free.
        An unnamed request goes to the pool, which is where "whoever
        picks it up" belongs.
        """
        if self.current(run_id) is not None:
            raise ReviewError(
                "this run is already waiting on a review. Cancel that request before "
                "sending another, so that 'who is this waiting on?' has one answer"
            )
        reviewer_id = None
        if reviewer_nickname:
            reviewer = self._users.find_by_nickname(reviewer_nickname)
            if reviewer is None:
                raise ReviewError(f"no member with the nickname {reviewer_nickname!r}")
            if reviewer.id == owner.id:
                raise ReviewError("you cannot send a run to yourself for review")
            reviewer_id = reviewer.id
        return self._reviews.create(
            ReviewRequest(
                id="",
                subject_kind=ReviewSubject.DECISION_RUN,
                subject_id=run_id,
                stage=ReviewStage.RESULT,
                requested_by_user_id=owner.id,
                requested_reviewer_user_id=reviewer_id,
                available_to_pool=reviewer_id is None,
                status=ReviewStatus.OPEN,
                request_comment=comment,
                created_at=now_iso(),
            )
        )

    def cancel(self, run_id: str, owner: User) -> ReviewRequest:
        """Withdraw the request. Only the person who sent it."""
        request = self._require_live(run_id)
        if request.requested_by_user_id != owner.id:
            raise ReviewNotAllowed("only the member who asked for this review can cancel it")
        return self._reviews.save(
            request.model_copy(update={"status": ReviewStatus.CANCELLED, "cancelled_at": now_iso()})
        )

    def claim(self, run_id: str, reviewer: User) -> ReviewRequest:
        """Take it. Refused if somebody already has it."""
        request = self._require_live(run_id)
        if request.claimed_by_user_id == reviewer.id:
            return request
        if request.claimed_by_user_id is not None:
            raise ReviewConflict(
                "somebody else is already reviewing this run. Taking it over is a separate "
                "act and needs a reason, so that they can see what happened"
            )
        if not request.claimable_by(reviewer.id):
            raise ReviewNotAllowed(
                "this review was addressed to somebody else and has not been released to "
                "the pool. Taking it over is a separate act and needs a reason"
            )
        return self._hold(request, reviewer)

    def takeover(self, run_id: str, reviewer: User, reason: str) -> ReviewRequest:
        """Take it from whoever has it — or from nobody, when a directed
        request is waiting on somebody who has not come back.

        One endpoint rather than two, because the two cases differ in
        exactly one field and share every rule: a reason is required, the
        person who was asked stays recorded, and the change is atomic.
        """
        if not reason.strip():
            raise ReviewError(
                "taking over a review needs a reason: somebody else was either holding it "
                "or was asked for it, and they see this"
            )
        request = self._require_live(run_id)
        if request.claimed_by_user_id == reviewer.id:
            return request
        previous = request.claimed_by_user_id or request.requested_reviewer_user_id
        taken = self._hold(request, reviewer)
        logger.info(
            "review taken over",
            extra={
                "context": {
                    "request_id": request.id,
                    "run_id": run_id,
                    "from": previous,
                    "to": reviewer.id,
                    "reason": reason,
                }
            },
        )
        return taken

    def release(self, run_id: str, reviewer: User) -> ReviewRequest:
        """Put it back. It becomes available to anybody.

        The requester's choice of reviewer is *not* cleared — it is part
        of what they said — but it stops being a gate, because a request
        that only one person may answer and that person has put down is a
        request nobody can answer.
        """
        request = self._require_live(run_id)
        if request.claimed_by_user_id != reviewer.id:
            raise ReviewNotAllowed("you are not holding this review")
        return self._reviews.save(
            request.model_copy(
                update={
                    "status": ReviewStatus.OPEN,
                    "claimed_by_user_id": None,
                    "claimed_at": None,
                    "available_to_pool": True,
                }
            )
        )

    def release_lost_claims(self, user_id: str) -> list[ReviewRequest]:
        """Free everything somebody was holding when they lost the right.

        Called when a role is revoked or an account is disabled. Without
        it, revoking a reviewer's role silently parks every run they were
        holding, and the engineers waiting on them have no way to see
        why nothing is happening.
        """
        released = []
        for request in self.queue():
            if request.status is not ReviewStatus.CLAIMED:
                continue
            if request.claimed_by_user_id != user_id:
                continue
            released.append(
                self._reviews.save(
                    request.model_copy(
                        update={
                            "status": ReviewStatus.OPEN,
                            "claimed_by_user_id": None,
                            "claimed_at": None,
                            "available_to_pool": True,
                        }
                    )
                )
            )
        return released

    def close(self, run_id: str, status: ReviewStatus, comment: str = "") -> ReviewRequest:
        """Mark the request finished, once the run itself has moved."""
        request = self._require_live(run_id)
        return self._reviews.save(
            request.model_copy(
                update={
                    "status": status,
                    "review_comment": comment or request.review_comment,
                    "reviewed_at": now_iso(),
                }
            )
        )

    # -- the rule that makes a signature mean something -----------------

    def require_claimant(self, run_id: str, reviewer: User) -> ReviewRequest:
        """The request this person is holding, or a refusal saying why."""
        request = self.current(run_id)
        if request is None:
            raise ReviewNotAllowed(
                "this run has not been sent for review. A reviewer acts on what somebody "
                "asked them to look at"
            )
        if request.status is not ReviewStatus.CLAIMED:
            raise ReviewNotAllowed("claim this review before answering it")
        if request.claimed_by_user_id != reviewer.id:
            raise ReviewNotAllowed("somebody else is holding this review")
        return request

    @staticmethod
    def acknowledged_under(request: ReviewRequest, events) -> bool:
        """Whether the current claimant has read the evidence *this time*.

        Both halves matter. The actor, because a claim taken over from
        somebody who had read it does not inherit their reading. The
        time, because the same person may have acknowledged it under an
        earlier claim and then put it down for a week — during which the
        run's evidence did not change, but their memory of it did.
        """
        claimed_at = request.claimed_at or ""
        for event in events:
            # Two spellings, one act. The store has written ``review``
            # since before this lane existed and rows carrying it are
            # real acknowledgements; refusing to recognise the older word
            # would make every run reviewed before today unsignable.
            if event.action not in _ACKNOWLEDGEMENTS:
                continue
            if event.actor_user_id != request.claimed_by_user_id:
                continue
            if (event.created_at or "") >= claimed_at:
                return True
        return False

    # -- internals -----------------------------------------------------

    def _hold(self, request: ReviewRequest, reviewer: User) -> ReviewRequest:
        return self._reviews.save(
            request.model_copy(
                update={
                    "status": ReviewStatus.CLAIMED,
                    "claimed_by_user_id": reviewer.id,
                    "claimed_at": now_iso(),
                    "available_to_pool": False,
                }
            )
        )

    def _require_live(self, run_id: str) -> ReviewRequest:
        request = self.current(run_id)
        if request is None:
            raise ReviewError("this run is not waiting on a review")
        return request


__all__ = [
    "SUBMISSION_CLAIMED",
    "SUBMISSION_CLOSED",
    "SUBMISSION_NONE",
    "SUBMISSION_OPEN",
    "DecisionReviewService",
    "submission_of",
]
