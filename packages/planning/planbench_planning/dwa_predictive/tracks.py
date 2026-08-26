"""What a predictive controller is told about a moving obstacle.

One structure, three producers, and that is the point. In P3 tracks are
handed in by a test; in P4 a ground-truth provider builds them so the
value of prediction can be measured with **zero** estimation error; in P5
a LiDAR tracker estimates them for real. If those three returned
different shapes, the number P5 exists to produce — *what it costs to
have to estimate this* — would mix estimation error with a difference in
geometry, and neither half would be readable.

So the oracle does not hand over obstacle centres while the tracker hands
over cluster centroids. Both hand over an :class:`ObstacleTrack`, and the
distance between them is estimation error alone.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planbench_schemas.geometry import Point2D

__all__ = ["ObstacleTrack"]


class ObstacleTrack(BaseModel):
    """A moving obstacle as the controller believes it to be **now**.

    Deliberately a belief about the present and not a plan for the
    future: the controller extrapolates with its own constant-velocity
    model, so a producer that supplied future positions would be handing
    over a different model rather than a better observation. That is the
    line P4's oracle has to respect to stay an oracle about *perception*
    rather than an oracle about *time*.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    center: Point2D = Field(description="Where the obstacle is now, world frame.")
    radius: float = Field(gt=0, description="Obstacle radius, metres.")
    velocity: Point2D = Field(
        description=(
            "Metres per second, world frame, as a vector rather than a speed and a "
            "heading: the controller only ever adds it to a position, and two fields "
            "that must be read together are two fields that can disagree."
        )
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "How much the producer believes its own velocity. The oracle sets 1.0. A "
            "tracker lowers it while a track is young or has just been extrapolated "
            "through a gap in the scan. Carried from P3 so the field exists before "
            "anything needs to lower it — a structure that grows a confidence field "
            "later grows it in three producers at once."
        ),
    )

    def position_at(self, seconds_ahead: float) -> Point2D:
        """Constant-velocity extrapolation, and nothing cleverer.

        The model is wrong the moment an obstacle turns or stops, and the
        plan says so out loud: ``sudden_stop`` is kept as the adversarial
        case precisely because a constant-velocity prediction drives
        straight through the moment the cart parks. Writing the model here
        in one line is what makes that limitation a property of the
        candidate rather than a detail buried in a rollout.
        """
        return Point2D(
            x=self.center.x + self.velocity.x * seconds_ahead,
            y=self.center.y + self.velocity.y * seconds_ahead,
        )
