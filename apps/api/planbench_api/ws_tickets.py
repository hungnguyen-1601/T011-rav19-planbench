"""One-time tickets for opening a WebSocket.

A browser cannot set a header on a ``WebSocket`` connection, so the
token has to travel some other way. The obvious way — ``?token=<jwt>`` —
puts a credential that is good for the next hour into every access log,
proxy log and browser history entry along the path. Logs are copied,
shipped to aggregators and kept far longer than the token is valid for.

So the caller trades a bearer token, on an ordinary authenticated HTTP
request, for a ticket that is:

* **single use** — redeemed on connect and gone, so a log line that
  captured it is describing something already spent;
* **short lived** — a minute, which is a page load, not a session;
* **bound to the account**, so redeeming it yields the same identity the
  request that minted it had.

Held in memory rather than in the database on purpose. A ticket is worth
less than the request that created it and is dead within a minute; the
cost of persisting it is a table whose rows are all garbage, and the
benefit — surviving a restart — is a restart that dropped the socket
anyway.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

#: Long enough to cover a page load and a reconnect, short enough that a
#: leaked log line is describing something already expired.
TICKET_TTL = timedelta(seconds=60)


@dataclass(frozen=True)
class Ticket:
    value: str
    user_id: str
    expires_at: datetime


class TicketStore:
    def __init__(self, ttl: timedelta = TICKET_TTL) -> None:
        self._ttl = ttl
        self._tickets: dict[str, Ticket] = {}
        self._lock = threading.Lock()

    def issue(self, user_id: str) -> Ticket:
        ticket = Ticket(
            value=secrets.token_urlsafe(24),
            user_id=user_id,
            expires_at=datetime.now(UTC) + self._ttl,
        )
        with self._lock:
            self._purge()
            self._tickets[ticket.value] = ticket
        return ticket

    def redeem(self, value: str) -> str | None:
        """The user id this ticket stands for, or ``None``.

        Removed whether or not it had expired: a ticket presented twice
        is either a replay or a bug, and neither deserves a second
        chance at connecting.
        """
        if not value:
            return None
        with self._lock:
            self._purge()
            ticket = self._tickets.pop(value, None)
        if ticket is None or ticket.expires_at <= datetime.now(UTC):
            return None
        return ticket.user_id

    def _purge(self) -> None:
        """Caller holds the lock."""
        now = datetime.now(UTC)
        expired = [key for key, ticket in self._tickets.items() if ticket.expires_at <= now]
        for key in expired:
            del self._tickets[key]


__all__ = ["TICKET_TTL", "Ticket", "TicketStore"]
