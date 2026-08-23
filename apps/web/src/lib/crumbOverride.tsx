"use client";

/** Letting a page name its own last breadcrumb.
 *
 * **Why a context and not a prop.** `breadcrumbs()` is a pure function
 * of the path, and a path cannot know that `/decisions/20750b0d9dbe` is
 * the `sudden_stop_v5` comparison — that lives in a fetch the detail
 * page makes. The breadcrumb is rendered by `TopBar`, which the root
 * layout mounts *above* the page, so there is no prop to pass upward.
 *
 * **`breadcrumbs()` itself is untouched**, and that matters. Its comment
 * is right that an id must be shown verbatim rather than run through a
 * dictionary; this does not translate the id, it replaces it with a name
 * the page fetched. The two claims are different, and the pure function
 * stays the one place that decides what a *path* means.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface CrumbOverride {
  /** What the last crumb should say, or `null` to leave the path's own
   *  answer — an id — in place. */
  label: string | null;
  setLabel: (label: string | null) => void;
}

/** The default is deliberately inert. A page rendered outside the
 *  provider still works; its breadcrumb simply shows the id, which is
 *  what every page did before this existed. */
const CrumbOverrideContext = createContext<CrumbOverride>({
  label: null,
  setLabel: () => {},
});

export function CrumbOverrideProvider({ children }: { children: ReactNode }) {
  const [label, setLabel] = useState<string | null>(null);
  // `setLabel` is referentially stable from `useState`, so the value only
  // changes when the label does — a page's cleanup effect will not be
  // torn down and re-run on every parent render.
  const value = useMemo(() => ({ label, setLabel }), [label]);
  return (
    <CrumbOverrideContext.Provider value={value}>{children}</CrumbOverrideContext.Provider>
  );
}

/** Read by the breadcrumb. */
export function useCrumbOverride(): string | null {
  return useContext(CrumbOverrideContext).label;
}

/**
 * Name this page's last crumb for as long as the page is mounted.
 *
 * **The cleanup is the whole hook.** Without it the name outlives the
 * page: navigate from a decision to `/maps/warehouse_a` and the crumb
 * still reads `sudden_stop_v5`, which is not a stale label but a wrong
 * one — it names a different record than the page under it. Nothing
 * throws, and the wrongness only appears after a navigation, which is
 * exactly when nobody is looking at the breadcrumb.
 *
 * `null` is a valid argument and means "I have nothing yet" — the crumb
 * falls back to the id while the fetch is in flight.
 */
export function useNameThisCrumb(label: string | null | undefined): void {
  const { setLabel } = useContext(CrumbOverrideContext);
  const set = useCallback(setLabel, [setLabel]);
  useEffect(() => {
    set(label ?? null);
    return () => set(null);
  }, [set, label]);
}
