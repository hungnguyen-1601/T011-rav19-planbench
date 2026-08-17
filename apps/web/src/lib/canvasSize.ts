/** How big the map canvas is, given the room it has.
 *
 * **A canvas cannot simply be told `width: 100%`.** `MapCanvas` maps a
 * press to world coordinates by assuming its drawing surface and its
 * CSS box are the same size — it sets `style.width` from the `width`
 * prop for exactly that reason. Stretching the element with CSS while
 * the prop stays at 760 leaves every click landing somewhere other than
 * where the pointer is, and it does so silently: the map still looks
 * right. So the width is measured and passed down as a number, and this
 * is the function that decides it.
 *
 * **No lower bound on the canvas.** An earlier draft floored it at
 * 480 px, which put the two-column layout's minimum on the canvas
 * itself and made a 390 px phone scroll sideways. 480 is a statement
 * about *the layout* — below it the panel and the map stop fitting side
 * by side — and it belongs in `SIDE_BY_SIDE_MIN_PX`, not here.
 */

/** The widest the map is ever drawn. Past this the extra pixels buy no
 *  detail: the grid is already legible and the panel beside it is the
 *  thing that wants the room. */
export const MAX_CANVAS_WIDTH_PX = 760;

/** Room the canvas needs before the panel may sit next to it rather
 *  than under it. Narrower than this and the map is too small to place
 *  anything on precisely. */
export const CANVAS_MIN_SIDE_BY_SIDE_PX = 480;
/** Room the tab panel needs to hold a row of number fields without
 *  wrapping every one of them onto its own line. */
export const PANEL_MIN_PX = 420;
/** The gap between the two columns. */
export const COLUMN_GAP_PX = 24;

/** Below this the form is one column: the map on top, the panel under.
 *
 * Derived rather than chosen, so the number moves when either minimum
 * does. Measured against the *form's own width* rather than the
 * viewport's, because a sidebar or a browser panel makes the viewport
 * a liar about how much room this component actually has. */
export const SIDE_BY_SIDE_MIN_PX =
  CANVAS_MIN_SIDE_BY_SIDE_PX + PANEL_MIN_PX + COLUMN_GAP_PX;

export interface CanvasSize {
  width: number;
  height: number;
}

/** Fit the canvas to its container, keeping the map's proportions.
 *
 * `aspect` is height ÷ width of the map in world units. Height follows
 * from it so a long thin corridor is not drawn in a square box with
 * most of the space empty.
 */
export function canvasSize(
  containerWidth: number,
  aspect: number,
  maxWidth: number = MAX_CANVAS_WIDTH_PX,
): CanvasSize {
  // A container that has not been measured yet reports 0. Drawing at
  // zero width would divide by it in the viewport maths, so the first
  // paint uses the full size and the observer corrects it a frame
  // later.
  const width =
    Number.isFinite(containerWidth) && containerWidth > 0
      ? Math.min(maxWidth, Math.round(containerWidth))
      : maxWidth;
  const ratio = Number.isFinite(aspect) && aspect > 0 ? aspect : 0.75;
  // Kept inside a band: a 30:1 corridor drawn to scale is a few pixels
  // tall and unusable, and a very tall map would push the controls off
  // the screen.
  const height = Math.round(width * Math.min(1.2, Math.max(0.45, ratio)));
  return { width, height };
}

/** Whether the form has room to put the panel beside the map. */
export function sideBySide(containerWidth: number): boolean {
  return Number.isFinite(containerWidth) && containerWidth >= SIDE_BY_SIDE_MIN_PX;
}
