"use client";

/** Escape and click-outside, for anything that opens over the page.
 *
 * The drawer, the theme menu, the language menu and the account menu all
 * need exactly this, and each one written separately is one that ends up
 * missing the Escape key.
 *
 * `pointerdown`, not `click`: a menu item that navigates would otherwise
 * race the close, and on touch a drag started outside should already
 * count as "somewhere else".
 */

import { useEffect, type RefObject } from "react";

export function useDismiss(
  open: boolean,
  onDismiss: () => void,
  ref?: RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onDismiss();
      }
    };
    const onPointerDown = (event: PointerEvent) => {
      const node = ref?.current;
      if (!node || !(event.target instanceof Node) || node.contains(event.target)) return;
      onDismiss();
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open, onDismiss, ref]);
}
