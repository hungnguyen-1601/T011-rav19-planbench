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
 * **The three parts are not the same kind of number**, and the
 * difference is the whole reason the ring surprises people:
 *
 * - `robot.radius` is geometry. A path whose centre line runs closer
 *   than that puts the body through the obstacle.
 * - the **safety envelope** is how wrong the robot's idea of its own
 *   position may be, derived from the localisation noise the deployment
 *   declares. Also hard, also geometry in effect — the body may be
 *   anywhere inside it.
 * - `√2 × resolution` is not geometry at all. It is the half-diagonal of
 *   a grid cell, there so a diagonal step between two free cells cannot
 *   clip the corner of an occupied one. It is a property of the **map's
 *   resolution** — halve the cell size and the ring shrinks, with
 *   nothing about the world having changed.
 *
 * A deployment that declares no localisation error has no envelope, so
 * its ring is what it always was. One that declares drift and a chance
 * of a jump grows by 0.39 m — and *that* is the number a reader needs
 * on screen, because it is invisible everywhere else.
 *
 * **This is a copy of a Python definition and there is no way around
 * that**, so the copy is named, kept in one place, and pinned by a test
 * that reads `nav_stack._inflation_radius` and `feasibility.py` and
 * checks they agree. Two hand-typed copies drifting apart is exactly how
 * the controller's keep-out and the planner's came to differ by 0.30 m
 * in the first place.
 */

/** Smallest jump a bad relocalisation produces, metres.
 *
 * Mirrors `planbench_schemas.sensor.MIN_JUMP_MAGNITUDE_M`.
 */
export const MIN_JUMP_MAGNITUDE_M = 0.25;

/** Localisation fields of a deployment's declared sensor noise.
 *
 * Values are read defensively rather than typed tightly: the API hands
 * `sensor_noise` back as loose JSON, and a deployment written before a
 * field existed simply has no key. Absent reads as zero, which is the
 * truth — no declared drift is no drift.
 */
export type NoiseForEnvelope = Record<string, unknown> | undefined | null;

function metres(noise: NoiseForEnvelope, field: string): number {
  const value = noise?.[field];
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
}

/** How far the robot may be from where it believes it is, in metres.
 *
 * Mirrors `SafetyEnvelope.for_noise`. Worst case rather than a
 * percentile: a hard bound exceeded five per cent of the time is not
 * hard, and a percentile would need somebody to choose which one.
 *
 * Drift is a weighted sum whose weights total one per axis, so both axes
 * together are bounded by `amplitude × √2`. A non-zero jump probability
 * is counted as a certainty — across an episode of many relocalisation
 * windows, "unlikely per window" is "it happens".
 */
export function safetyEnvelope(noise: NoiseForEnvelope): number {
  const drift = metres(noise, "localization_drift_m");
  let bound = drift * Math.SQRT2;
  if (metres(noise, "localization_jump_probability") > 0) {
    bound += Math.max(drift, MIN_JUMP_MAGNITUDE_M);
  }
  return bound;
}

/** The planner's keep-out margin, in metres, around any obstacle. */
export function inflationRadius(
  resolution: number,
  robotRadius: number,
  positionUncertainty = 0,
): number {
  return robotRadius + positionUncertainty + Math.SQRT2 * resolution;
}

/** Radius of the ring to draw around an obstacle of this radius.
 *
 * Returns `null` when the resolution or the robot radius is missing. A
 * ring drawn from a guessed robot radius would be a picture of a
 * keep-out nobody has — worse than no ring, because it looks
 * authoritative.
 *
 * `positionUncertainty` defaults to zero, which is the truthful reading
 * for a view with no deployment behind it: a scenario on its own
 * declares no localisation error, so it has no envelope. It is not a
 * guess standing in for a missing value.
 */
export function keepOutRadius(
  obstacleRadius: number,
  resolution: number | undefined,
  robotRadius: number | undefined,
  positionUncertainty = 0,
): number | null {
  if (!resolution || !robotRadius) return null;
  return obstacleRadius + inflationRadius(resolution, robotRadius, positionUncertainty);
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
