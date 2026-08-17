"use client";

/** A tab strip and the panels under it.
 *
 * **Panels are hidden, never unmounted.** React throws away the state
 * of anything it removes, and the deployment form keeps real state in
 * its controls: the last non-zero amplitude of every noise source, so
 * unticking and re-ticking gives back what was typed; which vehicle was
 * applied. Rebuilding those on every tab change would lose an edited
 * figure to a stray click on another tab — the kind of small loss that
 * costs a re-measurement to notice. The `hidden` attribute takes the
 * panel out of the accessibility tree and out of the layout while
 * leaving the component alive.
 *
 * Generic on purpose: no contract path appears in this file. The schema
 * drift guard reads `DeploymentForm.tsx` for every field the contract
 * defines, and a control whose dotted path moved into a shell component
 * would be invisible to it.
 */

import type { ReactNode } from "react";

export interface TabDefinition<Id extends string> {
  id: Id;
  label: string;
  /** Refusals waiting on this tab. Rendered as a count beside the
   *  label, because a tab is a place to hide things and a blocked
   *  filing with no visible reason is what this form exists not to
   *  do. */
  badge?: number;
  /** Announced with the count, since a bare number beside a word reads
   *  as anything at all to a screen reader. */
  badgeLabel?: string;
  content: ReactNode;
}

export interface TabsProps<Id extends string> {
  tabs: TabDefinition<Id>[];
  active: Id;
  onSelect: (id: Id) => void;
  /** Distinguishes this strip's ids from another's on the same page. */
  idPrefix: string;
  ariaLabel: string;
}

export function Tabs<Id extends string>({
  tabs,
  active,
  onSelect,
  idPrefix,
  ariaLabel,
}: TabsProps<Id>) {
  return (
    <>
      <div className="toolbar" role="tablist" aria-label={ariaLabel}>
        {tabs.map((tab) => {
          const selected = tab.id === active;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${idPrefix}-tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`${idPrefix}-panel-${tab.id}`}
              className={selected ? "active" : undefined}
              onClick={() => onSelect(tab.id)}
            >
              {tab.label}
              {tab.badge ? (
                /* Labelled rather than left as a bare digit: "Traffic 3"
                   read aloud is a heading and a number, and only the
                   label says the number counts refusals. */
                <span className="badge err" style={{ marginLeft: 6 }} aria-label={tab.badgeLabel}>
                  {tab.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`${idPrefix}-panel-${tab.id}`}
          aria-labelledby={`${idPrefix}-tab-${tab.id}`}
          hidden={tab.id !== active}
        >
          {tab.content}
        </div>
      ))}
    </>
  );
}
