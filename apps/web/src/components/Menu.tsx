"use client";

/** A small dropdown: a trigger button and a list of choices.
 *
 * Written once because the three menus in the top bar differ only in
 * what they list. Keyboard and dismissal behaviour therefore cannot
 * diverge between them, which is exactly how the account menu ends up
 * being the one you cannot close with Escape.
 *
 * `role="menu"` with `menuitemradio` children: these are all
 * pick-exactly-one lists, and that is the role that tells a screen
 * reader which one is currently picked.
 */

import { useCallback, useRef, useState } from "react";

import { Icon, type IconName } from "./Icon";
import { useDismiss } from "@/lib/useDismiss";

export interface MenuChoice<T extends string> {
  value: T;
  label: string;
  icon?: IconName;
}

export function Menu<T extends string>({
  label,
  tooltip,
  icon,
  buttonLabel,
  choices,
  value,
  onSelect,
  heading,
}: {
  /** Accessible name for the trigger. */
  label: string;
  tooltip?: string;
  icon: IconName;
  /** Short text beside the icon, e.g. the current language code. */
  buttonLabel?: string;
  choices: readonly MenuChoice<T>[];
  value: T;
  onSelect: (value: T) => void;
  heading?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    // Focus goes back where it came from; otherwise Escape drops the
    // keyboard user at the top of the document.
    trigger.current?.focus();
  }, []);
  useDismiss(open, close, wrap);

  return (
    <div className="menu-wrap" ref={wrap}>
      <button
        ref={trigger}
        type="button"
        className="icon-button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        data-tooltip={tooltip ?? label}
        onClick={() => setOpen((current) => !current)}
      >
        <Icon name={icon} />
        {buttonLabel ? <span className="icon-button-label">{buttonLabel}</span> : null}
      </button>

      {open ? (
        <div className="menu" role="menu" aria-label={label}>
          {heading ? <div className="menu-heading">{heading}</div> : null}
          {choices.map((choice) => (
            <button
              key={choice.value}
              type="button"
              role="menuitemradio"
              aria-checked={choice.value === value}
              className="menu-item"
              onClick={() => {
                onSelect(choice.value);
                close();
              }}
            >
              {choice.icon ? <Icon name={choice.icon} size={15} /> : null}
              {choice.label}
              <span className="menu-check">
                <Icon name="check" size={14} />
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
