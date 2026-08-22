/** How far the global planner keeps off an obstacle, for drawing only.
 *
 * **Why this is worth a module.** The canvas drew a cart at its own
 * radius — 0.40 m on `sudden_stop` — while the planner refused to route
 * within another 0.61 m of it. The ring was two and a half times the
 * circle, and it was invisible: a robot parked half a metre clear of the
 * cart looked like it was standing in open space, and the reason it
 * could not replan was not on screen anywhere.
 *
 * That cost a full session to diagnose from first principles. Drawing it
 * is what makes the next instance of the same class of problem readable
 * instead of mysterious.
 *
 * **There are two rings now, and they say different things.**
 *
 * - The **forbidden** ring is `robot.radius + safety envelope`. Both are
 *   hard and both are geometry: the first is the body, the second is how
 *   wrong the robot's idea of its own position may be, derived from the
 *   localisation noise the deployment declares. A path inside it is one
 *   the local controller would refuse to drive.
 * - The **priced** band reaches a cell diagonal further, plus a taper.
 *   It is *passable*. `√2 × resolution` is not geometry at all — it is
 *   the band a coarsely drawn grid cannot be sure about, a property of
 *   the **map's resolution**, and halving the cell size halves it with
 *   nothing about the world having changed.
 *
 * Drawing them as one disc is what the single ring used to do, and it
 * made a region the robot may legally cross look like a wall. That
 * reading is precisely what made a stuck robot inexplicable: it stood in
 * space the picture called forbidden and its own collision test called
 * fine.
 *
 * A deployment that declares no localisation error has no envelope, so
 * its forbidden ring is the robot's own circle. One that declares drift
 * and a chance of a jump grows by 0.39 m — and *that* is the number a
 * reader needs on screen, because it is invisible everywhere else.
 *
 * **These are copies of Python definitions and there is no way around
 * that**, so the copies are named, kept in one place, and pinned by a
 * test that reads `nav_stack._hard_radius`, `nav_stack._caution_ramp`
 * and `feasibility.py` and checks they agree. Two hand-typed copies
 * drifting apart is exactly how the controller's keep-out and the
 * planner's came to differ by 0.30 m in the first place.
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

/** How far the planner **forbids**, in metres: `hard_clearance`.
 *
 * Mirrors `nav_stack._hard_radius`. Nothing about the map file is in
 * it — that is the whole point of the graded phase. A path inside this
 * ring is one the local controller would refuse to drive, so no planner
 * may return one.
 */
export function inflationRadius(robotRadius: number, positionUncertainty = 0): number {
  return robotRadius + positionUncertainty;
}

/** How far the graded penalty reaches past the hard boundary.
 *
 * Mirrors `nav_stack._caution_ramp`: **half** a cell diagonal — the
 * robot-side share of the quantisation slop, the share that stayed out
 * of the prohibition — plus one hard clearance of taper, so the cost
 * reaches zero smoothly instead of stepping off a cliff where paths are
 * decided.
 *
 * The *other* half sits inside the planner's own prohibition, because
 * an occupied cell says the obstacle touches it and not where. That
 * half is not drawn separately: it lands inside this band, which reads
 * as "priced" rather than "forbidden" for a sliver where the grid is
 * stricter than the physics. Drawing a third ring for it would cost
 * more clarity than the sliver is worth.
 */
export function cautionRamp(
  resolution: number,
  robotRadius: number,
  positionUncertainty = 0,
): number {
  return (Math.SQRT2 * resolution) / 2 + inflationRadius(robotRadius, positionUncertainty);
}

/** Radius of the **forbidden** ring around an obstacle of this radius.
 *
 * Returns `null` when the robot radius is missing. A ring drawn from a
 * guessed radius would be a picture of a keep-out nobody has — worse
 * than no ring, because it looks authoritative.
 *
 * `positionUncertainty` defaults to zero, which is the truthful reading
 * for a view with no deployment behind it: a scenario on its own
 * declares no localisation error, so it has no envelope. It is not a
 * guess standing in for a missing value.
 */
export function keepOutRadius(
  obstacleRadius: number,
  robotRadius: number | undefined,
  positionUncertainty = 0,
): number | null {
  if (!robotRadius) return null;
  return obstacleRadius + inflationRadius(robotRadius, positionUncertainty);
}

/** Radius of the **priced** band: passable, and charged for.
 *
 * Drawn fainter still than the hard ring, and drawn *separately*,
 * because the two say different things. Merging them into one disc —
 * which is what the single ring did before the gradient existed — makes
 * a region the robot may legally cross look like a wall, and that
 * reading is exactly what made a stuck robot inexplicable: it was
 * standing in space the picture called forbidden and its own collision
 * test called fine.
 */
export function cautionRadius(
  obstacleRadius: number,
  resolution: number | undefined,
  robotRadius: number | undefined,
  positionUncertainty = 0,
): number | null {
  if (!resolution || !robotRadius) return null;
  return obstacleRadius + cautionRamp(resolution, robotRadius, positionUncertainty);
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

/** Fill for the priced band, fainter than the forbidden ring.
 *
 * Fainter on purpose and not by accident of taste: the reader has to be
 * able to tell at a glance which of the two the robot may enter. Same
 * hue, because both belong to that obstacle.
 */
export const CAUTION_FILL = "rgba(240, 180, 41, 0.03)";

/** Outline for the priced band: dotted, to read as "soft" beside the
 *  dashed hard ring rather than as a second wall. */
export const CAUTION_STROKE = "rgba(240, 180, 41, 0.16)";
