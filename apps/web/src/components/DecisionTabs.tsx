"use client";

/** A tab strip over sections that must all stay alive.
 *
 * **Every panel is rendered and the inactive ones are hidden, rather
 * than only the active one being mounted.** That is the whole reason
 * this component exists instead of a ternary in the page:
 *
 * - The episode viewer fetches a trace per candidate, holds a
 *   `setInterval` while a replay is playing, and remembers which episode
 *   the reader picked, how the 2.5D camera is turned and where the
 *   scrubber is. Unmounting it throws all of that away, so leaving the
 *   tab and coming back would re-download two traces and restart the
 *   replay from zero — a reader flipping to the evidence to check a
 *   number and back would lose the moment they were looking at.
 * - The advisory panels below hold answers that cost a model call and
 *   several seconds to fetch, and there is no cache behind them. Losing
 *   one on a tab switch means paying for it again.
 * - Every panel mounts on first render, exactly as it did when the page
 *   was one long column, so nothing about *when* anything is fetched
 *   changes with this layout.
 *
 * The cost is that the whole page is still built on load. It was
 * already; this changes what is on screen, not what is constructed.
 *
 * Hidden with the `hidden` attribute rather than a class, because
 * `hidden` also takes the panel out of the accessibility tree and out of
 * find-in-page — a `visibility: hidden` panel is still four screens of
 * text a screen reader walks through.
 */

import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { tabAfterKey } from "@/lib/decisionTabs";
import { useTranslation } from "@/lib/i18n";

/** A label, in one of the only two ways a caller can honestly have one.
 *
 * `string | string` would compile and say nothing: handed `"G1"`, the
 * component cannot tell whether that is a key it must look up or text
 * already in the reader's language. Every caller here has a key; the
 * guide's tab titles come from a manifest holding both languages side by
 * side, so there is no key to pass. Separate *fields* are what let the
 * component know which it was given — and `?: never` is what stops a
 * caller from supplying both and leaving the answer to precedence.
 */
export type Labelled =
  { labelKey: string; label?: never } | { label: string; labelKey?: never };

export type DecisionTabSpec = {
  id: string;
  content: ReactNode;
} & Labelled;

/** The text of either half. */
function labelText(source: Labelled, t: (key: string) => string): string {
  return source.label !== undefined ? source.label : t(source.labelKey);
}

export function DecisionTabs(
  props: {
    tabs: DecisionTabSpec[];
    active: string;
    onSelect: (id: string) => void;
  } & Labelled,
) {
  const { tabs, active, onSelect } = props;
  const { t } = useTranslation();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const next = tabAfterKey(event.key, index, tabs.length);
    if (next === null) return;
    // Arrows scroll the page by default, and `Home`/`End` jump it to an
    // end — either would move the reader away from the strip they are
    // steering with.
    event.preventDefault();
    onSelect(tabs[next].id);
    // **Selection follows focus, and focus follows the arrow.** A roving
    // `tabIndex` means only the selected tab is a tab stop, so without
    // this the focus ring would stay on a button that is no longer the
    // one in tab order.
    buttons.current[next]?.focus();
  };

  return (
    <div className="decision-tabs">
      <div
        className="decision-tablist"
        role="tablist"
        aria-label={labelText(props, t)}
      >
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`decision-tab-${tab.id}`}
            ref={(node) => {
              buttons.current[index] = node;
            }}
            className={`decision-tab${tab.id === active ? " is-active" : ""}`}
            aria-selected={tab.id === active}
            aria-controls={`decision-tabpanel-${tab.id}`}
            tabIndex={tab.id === active ? 0 : -1}
            onKeyDown={(event) => onKeyDown(event, index)}
            onClick={() => onSelect(tab.id)}
          >
            {labelText(tab, t)}
          </button>
        ))}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`decision-tabpanel-${tab.id}`}
          aria-labelledby={`decision-tab-${tab.id}`}
          className="decision-tabpanel"
          hidden={tab.id !== active}
        >
          {tab.content}
        </div>
      ))}
    </div>
  );
}
