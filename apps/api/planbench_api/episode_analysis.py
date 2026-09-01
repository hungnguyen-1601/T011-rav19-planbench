"""Serving one episode's answer, and the gate on the part a model wrote.

Two routes, and the difference between them is the whole design.

The **verdict** route is deterministic: it reads rows the scoring pass
already stored, runs the detectors over two served traces, applies the
contrast rules and hands back what the platform can say by itself. No
model is involved, nothing is gated, and it is the thing a reader
actually opened the panel for.

The **analysis** route asks a model, and is therefore behind a mode with
four settings rather than a boolean. "We measured it" and "it is good
enough to show people" are different claims, and a flag with two
positions cannot tell them apart:

``off``
    404. The route does not exist for this deployment.
``shadow``
    The round runs and the answer is written to an artifact the platform
    keeps. The response carries none of it — this is how a model's
    output is collected before anybody has decided it is fit to read.
``internal_preview``
    Admins see it, labelled. Opened on an exploratory report, which is
    what "we measured it" earns.
``production``
    Everybody sees it. Needs an ``EpisodeGateDecision``: a
    machine-checkable record pinning bundle, prompt, eval spec, model
    identity, cluster set, thresholds and an expiry. **Nothing issues one
    yet**, and settings refuses this mode unconditionally — the type
    exists so the day it is issued is a day of granting a decision
    rather than of designing what one is.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal

EpisodeAnalystMode = Literal["off", "shadow", "internal_preview", "production"]

MODES: tuple[EpisodeAnalystMode, ...] = ("off", "shadow", "internal_preview", "production")


class EpisodeAnalysisRefusal(Exception):
    """The analysis cannot be served, and why."""


@dataclass(frozen=True)
class EpisodeGateDecision:
    """What it would take to show a model's answer to everybody.

    Every field pins something a later run could differ in. A record
    missing any of them cannot say which system was graded, and a record
    without an expiry says a grading holds forever — which no measurement
    of a model does.

    Deliberately **not** an extension of
    :class:`~planbench_explanation.bundle.GateDecision`: widening the
    record the run scope already grades against would change a contract
    in use to describe one that is not.
    """

    scope: Literal["episode"]
    bundle_identity: str
    runtime_config_checksum: str
    prompt_checksum: str
    eval_spec_checksum: str
    model_identity: str
    cluster_set_version: str
    primary_endpoint: str
    primary_threshold: float
    hard_constraints: tuple[str, ...]
    cost_ceiling_usd: float
    expires_at: str
    revoked: bool = False


def verify_episode_gate_decision(decision: EpisodeGateDecision | None, *, now: str) -> str:
    """Why this decision may not open production, or ``""`` if it may.

    Returns a reason rather than raising: the caller is a settings check
    that has to report what is missing, and a raise there would make the
    absence of a decision — the normal state today — look like a fault.
    """
    if decision is None:
        return "no episode gate decision has been issued"
    if decision.revoked:
        return "the episode gate decision has been revoked"
    if decision.expires_at <= now:
        return f"the episode gate decision expired at {decision.expires_at}"
    missing = [
        name
        for name in (
            "bundle_identity",
            "runtime_config_checksum",
            "prompt_checksum",
            "eval_spec_checksum",
            "model_identity",
            "cluster_set_version",
            "primary_endpoint",
        )
        if not getattr(decision, name)
    ]
    if missing:
        return f"the episode gate decision does not pin {sorted(missing)}"
    if not decision.hard_constraints:
        return "the episode gate decision names no hard constraint it was held to"
    return ""


@dataclass(frozen=True)
class EpisodeAnalystPolicy:
    """What this deployment allows, and what it will spend doing it."""

    mode: EpisodeAnalystMode = "off"
    #: Where the exploratory report lives. Required to leave ``shadow``:
    #: a mode that let a model's answer reach a person on nothing but a
    #: flag would be a decision nobody recorded.
    evaluation_report_ref: str = ""
    #: Per user per day. Both, because a call that returns a long answer
    #: and a call that returns a short one cost differently, and a cap on
    #: only one of them is a cap on neither.
    max_calls_per_day: int = 20
    max_tokens_per_day: int = 400_000
    #: One round's wall clock. The budget the round carries governs the
    #: model call; this governs the request.
    timeout_s: float = 120.0
    gate: EpisodeGateDecision | None = None

    def refusal(self, *, now: str) -> str:
        """Why this policy is not allowed to run, or ``""`` if it is."""
        if self.mode == "off":
            return ""
        if self.mode in ("shadow",):
            return ""
        if self.mode == "internal_preview":
            if not self.evaluation_report_ref:
                return (
                    "internal_preview shows a model's answer to a person, and this "
                    "deployment names no evaluation report it was opened on; a mode "
                    "that turned on with nothing behind it would be a decision "
                    "nobody recorded"
                )
            return ""
        reason = verify_episode_gate_decision(self.gate, now=now)
        return (
            reason
            or "production is not available in this build: no episode gate decision "
            "can be issued yet, and the mode exists so that granting one later is a "
            "grant rather than a redesign"
        )


def visible_to(policy: EpisodeAnalystPolicy, *, is_admin: bool) -> bool:
    """Whether this caller may read what the model wrote."""
    if policy.mode == "internal_preview":
        return is_admin
    return policy.mode == "production"


@dataclass
class InFlight:
    """One analysis in progress, and everybody waiting on its answer.

    Requests that name the same packet under the same configuration are
    the same question. Serving them from one round is not only cheaper:
    two rounds of a non-deterministic model would give two answers to a
    question asked once, and a reader refreshing a page would watch the
    explanation change.
    """

    done: threading.Event = field(default_factory=threading.Event)
    answer: Mapping[str, Any] | None = None
    error: BaseException | None = None


class InFlightRegistry:
    """Coalesces identical analyses that are running at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: dict[str, InFlight] = {}

    def start(self, key: str) -> tuple[InFlight, bool]:
        """The slot for this key, and whether this caller owns it."""
        with self._lock:
            existing = self._running.get(key)
            if existing is not None:
                return existing, False
            fresh = InFlight()
            self._running[key] = fresh
            return fresh, True

    def finish(
        self, key: str, *, answer: Mapping[str, Any] | None, error: BaseException | None
    ) -> None:
        with self._lock:
            slot = self._running.pop(key, None)
        if slot is None:  # pragma: no cover - finish without start
            return
        slot.answer = answer
        slot.error = error
        slot.done.set()

    @property
    def active(self) -> int:
        with self._lock:
            return len(self._running)


def dedup_key(
    *, packet_checksum: str, runtime_config_checksum: str, question: str = ""
) -> str:
    """What makes two analyses the same question.

    The packet **after** budgeting, because what a round was given is
    what was left; the configuration, because the same facts under a
    different arm vector are a different system being asked; and the
    question, because once a reader can type one, two readers asking
    different things about one episode are not asking the same thing.

    **The question had to join them the day it became typeable.** Keyed
    on packet and configuration alone, the second question asked about an
    episode would have been served the first one's answer — silently, and
    looking exactly like a reply to what was asked. Empty means the fixed
    question, so every key recorded before this still hashes the same and
    the artifacts already written stay addressable.
    """
    material = json.dumps(
        {
            "packet": packet_checksum,
            "config": runtime_config_checksum,
            **({"question": question.strip()} if question.strip() else {}),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class DailySpend:
    """One caller's spend today, kept in memory and reset by the date.

    In memory because a cost cap that survives a restart needs a store,
    and a store needs a migration; the cap that matters is the one that
    stops a loop this afternoon. Written down here so nobody reads the
    absence as an oversight.
    """

    day: str = ""
    calls: int = 0
    tokens: int = 0


class SpendLedger:
    """Per-caller daily spend, and the two caps it is checked against."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spend: dict[str, DailySpend] = {}

    def check(self, caller: str, *, policy: EpisodeAnalystPolicy, today: str) -> str:
        """Why this caller may not spend more today, or ``""``."""
        with self._lock:
            record = self._spend.get(caller)
            if record is None or record.day != today:
                return ""
            if record.calls >= policy.max_calls_per_day:
                return (
                    f"this account has asked for {record.calls} episode analyses today, "
                    f"and the daily cap is {policy.max_calls_per_day}"
                )
            if record.tokens >= policy.max_tokens_per_day:
                return (
                    f"this account has spent {record.tokens} tokens on episode analyses "
                    f"today, and the daily cap is {policy.max_tokens_per_day}"
                )
        return ""

    def record(self, caller: str, *, today: str, tokens: int) -> None:
        with self._lock:
            current = self._spend.get(caller)
            if current is None or current.day != today:
                current = DailySpend(day=today)
                self._spend[caller] = current
            current.calls += 1
            current.tokens += tokens

    def spent(self, caller: str) -> DailySpend:
        with self._lock:
            return self._spend.get(caller, DailySpend())


def artifact_path(root: Path, *, run_id: str, episode_context_id: str, key: str) -> Path:
    """Where a shadow round's answer is written.

    Addressed by the dedup key, so the same question asked twice
    overwrites one file rather than accumulating two answers that are
    supposed to be the same.
    """
    return root / run_id / episode_context_id / f"{key}.json"


def _encodable(value: object) -> object:
    """A dataclass as its fields, for the encoder that cannot take one.

    **The round's own annotations are dataclasses**, and every payload
    written here carries them: which register the guard kept a proposal
    in, which of the contract's four terms it met, what it cited. The
    caller passed them through untouched and `json.dumps` refused —
    which is what happened the first time any deployment turned the
    analyst on. The round died writing the record of a model call it had
    already made and paid for, and the reader got a 500.

    Encoding belongs here rather than at each call site because there is
    one writer and several callers, and a rule every caller has to
    remember is a rule one of them will not.

    Anything else still raises. A silent `str()` would put the repr of
    an object into an audit record and make it look like data.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"cannot record an object of type {type(value).__name__} in an artifact")


def write_artifact(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_encodable),
        encoding="utf-8",
    )


def today(now: float | None = None) -> str:
    """The day a spend belongs to, in UTC."""
    return time.strftime("%Y-%m-%d", time.gmtime(now if now is not None else time.time()))
