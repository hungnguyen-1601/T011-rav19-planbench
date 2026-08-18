"""``human_state_estimates`` from ground truth — the oracle source.

**The only built-in that reads world truth, and it pays for it.** Its
provenance is ``oracle``, which under §5.10 demotes the whole
execution's evidence class and marks the channel ``sim_only``; under a
production fairness policy it is refused at admission rather than
discovered afterwards.

This is not a loophole, it is the lane P4 and P5 needed and did not
have. Measuring what perfect perception would buy is a real question —
P4 answered it (11 of 11 paired disagreements, p = 0.0005) and P5
answered the follow-up (the LiDAR tracker recovered none of it) — and
both had to run outside the platform, in scripts beside it. Through this
provider that measurement runs on the same runtime, the same loop and
the same trace, while the evidence machinery keeps it out of every
production conclusion.

Access is gated on the *class object* (see
``runtime_view.TRUSTED_ORACLE_PROVIDERS``), so a provider cannot reach
truth by adopting a convenient name.
"""

from __future__ import annotations

from typing import Any

from planbench_schemas.scenario import CircleObstacle
from planbench_simulator.host.providers.base import Provider
from planbench_simulator.host.runtime_view import (
    ProviderRuntimeView,
    register_trusted_oracle,
)

HUMAN_STATE_ESTIMATES = "human_state_estimates"


class GroundTruthTrackProvider(Provider):
    """Exact obstacle positions and velocities, as the simulator knows them.

    Velocity is a **backward difference** over the two most recent truth
    samples, never a peek at the next one: an oracle that knew the future
    would measure something no estimator could approach even in
    principle, which makes the upper bound it produces uninformative.
    Same rule P4's oracle followed.
    """

    capability = HUMAN_STATE_ESTIMATES
    cadence = "per_tick"
    provenance = "oracle"
    stream_id = 5

    def __init__(self) -> None:
        self._tracks: tuple[dict[str, float], ...] = ()
        self._previous: tuple[CircleObstacle, ...] = ()
        self._previous_time: float | None = None

    def reset(self) -> None:
        self._tracks = ()
        self._previous = ()
        self._previous_time = None

    def advance(
        self, tick: int, now: float, view: ProviderRuntimeView, inputs: dict[str, Any]
    ) -> None:
        del tick, inputs
        current = view.private_truth(self)
        elapsed = None if self._previous_time is None else now - self._previous_time
        tracks = []
        for index, obstacle in enumerate(current):
            vx = vy = 0.0
            if elapsed and elapsed > 0.0 and index < len(self._previous):
                earlier = self._previous[index].center
                vx = (obstacle.center.x - earlier.x) / elapsed
                vy = (obstacle.center.y - earlier.y) / elapsed
            tracks.append(
                {
                    "x": obstacle.center.x,
                    "y": obstacle.center.y,
                    "radius": obstacle.radius,
                    "vx": vx,
                    "vy": vy,
                }
            )
        self._tracks = tuple(tracks)
        self._previous = tuple(current)
        self._previous_time = now

    def read(self) -> tuple[dict[str, float], ...]:
        return self._tracks


register_trusted_oracle(GroundTruthTrackProvider)
