/** How far the global planner keeps off an obstacle, for drawing only.
 *
 * **Why this is worth a module.** The canvas draws a cart at its own
 * radius — 0.40 m on `sudden_stop` — while the planner refuses to route
 * within `robot.radius + √2 × resolution` of it, which on the same map
 * is another 0.61 m. The ring is two and a half times the circle, and it
 * was invisible: a robot parked half a metre clear of the cart looked
 * like it was standing in open space, and the reason it could not
 * replan was not on screen anywhere.
 *
 * That cost a full session to diagnose from first principles. Drawing it
 * is what makes the next instance of the same class of problem readable
 * instead of mysterious.
 *
 * **The two halves are not the same kind of number**, and the difference
 * is the whole reason the ring surprises people:
 *
 * - `robot.radius` is geometry. A path whose centre line runs closer
 *   than that puts the body through the obstacle.
 * - `√2 × resolution` is not geometry at all. It is the half-diagonal of
 *   a grid cell, there so a diagonal step between two free cells cannot
 *   clip the corner of an occupied one. It is a property of the **map's
 *   resolution** — halve the cell size and the ring shrinks, with
 *   nothing about the world having changed.
 *
 * **This is a copy of a Python definition and there is no way around
 * that**, so the copy is named, kept in one place, and pinned by a test
 * that reads `nav_stack._inflation_radius` and checks the two agree.
 * Two hand-typed copies drifting apart is exactly how the controller's
 * keep-out and the planner's came to differ by 0.30 m in the first
 * place.
 */

/** The planner's keep-out margin, in metres, around any obstacle. */
export function inflationRadius(resolution: number, robotRadius: number): number {
  return robotRadius + Math.SQRT2 * resolution;
}

/** Radius of the ring to draw around an obstacle of this radius.
 *
 * Returns `null` when either input is missing. A ring drawn from a
 * guessed robot radius would be a picture of a keep-out nobody has —
 * worse than no ring, because it looks authoritative.
 */
export function keepOutRadius(
  obstacleRadius: number,
  resolution: number | undefined,
  robotRadius: number | undefined,
): number | null {
  if (!resolution || !robotRadius) return null;
  return obstacleRadius + inflationRadius(resolution, robotRadius);
}

/** Fill for the ring: faint enough that the obstacle stays the subject.
 *
 * The ring is context, not an object. At full strength it swamps a
 * 0.4 m cart inside a 1.0 m disc and the reader's eye lands on the
 * wrong thing — so it is drawn *under* the obstacle and at an alpha
 * that survives a screenshot without competing with it.
 */
export const KEEP_OUT_FILL = "rgba(240, 180, 41, 0.07)";

/** Outline for the ring: dashed, thin, and the same hue as the obstacle.
 *
 * Dashed rather than solid because a solid ring reads as a wall. Same
 * hue because it belongs to that obstacle rather than being a second
 * thing in the scene.
 */
export const KEEP_OUT_STROKE = "rgba(240, 180, 41, 0.35)";
