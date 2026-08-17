"use client";

/** The sentence explaining a field, kept out of the way until asked for.
 *
 * **Why it moved off the page.** Every number on this form has a
 * consequence somebody has to know — a head start of zero makes three
 * hundred seeds replay one episode; a goal tolerance under π is refused
 * outright — so each grew a paragraph beside it. Together those
 * paragraphs took more room than the controls did, and a panel that is
 * four-fifths prose is one nobody reads: the explanations crowded out
 * the very fields they were explaining.
 *
 * So the text is still there, and still one sentence per number. It is
 * behind a mark you point at.
 *
 * **The full text stays in the markup**, as the mark's own accessible
 * name. A tooltip that exists only while a mouse is over it is a
 * tooltip that a screen reader, a keyboard user and a text search
 * cannot reach — and this text is the difference between a deployment
 * somebody understands and one they guessed at.
 */

import { useState } from "react";

/** Distance from the pointer to the corner of the bubble. Far enough
 *  that the cursor does not sit on top of the first word. */
const OFFSET_PX = 16;
const WIDTH_PX = 340;

interface Anchor {
  x: number;
  y: number;
}

export interface HintProps {
  text: string;
  /** Screen-reader name for the mark itself, before the text it
   *  carries — "what is this" needs a subject. */
  label?: string;
}

export function Hint({ text, label }: HintProps) {
  const [at, setAt] = useState<Anchor | null>(null);

  /** Keep the bubble on screen. Near the right edge it opens to the
   *  left of the pointer instead, and near the bottom it opens
   *  upwards — a hint that runs off the window is a hint that was not
   *  shown. */
  const place = (anchor: Anchor) => {
    if (typeof window === "undefined") return { left: anchor.x + OFFSET_PX, top: anchor.y + OFFSET_PX };
    const flipX = anchor.x + OFFSET_PX + WIDTH_PX > window.innerWidth;
    const flipY = anchor.y + OFFSET_PX + 160 > window.innerHeight;
    return {
      left: flipX ? Math.max(8, anchor.x - OFFSET_PX - WIDTH_PX) : anchor.x + OFFSET_PX,
      top: flipY ? Math.max(8, anchor.y - OFFSET_PX - 160) : anchor.y + OFFSET_PX,
    };
  };

  return (
    <>
      <span
        className="hint-mark"
        role="button"
        tabIndex={0}
        aria-label={label ? `${label}: ${text}` : text}
        onMouseEnter={(event) => setAt({ x: event.clientX, y: event.clientY })}
        onMouseMove={(event) => setAt({ x: event.clientX, y: event.clientY })}
        onMouseLeave={() => setAt(null)}
        /* Keyboard users have no pointer to anchor to, so the bubble
           opens at the mark itself. Without this the text would be
           reachable only by mouse, which is where it was before this
           component and the reason it needed one. */
        onFocus={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          setAt({ x: box.right, y: box.bottom });
        }}
        onBlur={() => setAt(null)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setAt(null);
        }}
      >
        ?
      </span>
      {at ? (
        <span
          role="tooltip"
          className="hint-bubble"
          style={{ position: "fixed", width: WIDTH_PX, ...place(at) }}
        >
          {text}
        </span>
      ) : null}
    </>
  );
}
