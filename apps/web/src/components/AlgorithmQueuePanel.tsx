"use client";

/** Imported algorithms nobody has vouched for yet.
 *
 * The other half of a reviewer's workload, and it has no request behind
 * it. A run reaches a reviewer because an engineer sent it; an imported
 * algorithm reaches one by existing — somebody uploaded a bundle and it
 * sits there, offered to nobody, until a reviewer publishes it. There is
 * nothing to claim, so this pile is a list and a link rather than a
 * queue with buttons.
 *
 * It shows what a reviewer can act on and stays quiet about the rest: a
 * bundle that failed its conformance run needs its author, not a
 * reviewer, and one somebody already withdrew is a decision rather than
 * an outstanding task.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { useTranslation } from "@/lib/i18n";
import {
  bundleStates,
  listPlugins,
  publishedBundleIds,
  stackIdFor,
  type BundleState,
  type PluginBundleSummary,
} from "@/lib/plugins";

/** The states that are somebody's outstanding work, and whose.
 *
 * `awaiting` is a reviewer's: it ran, it behaved, and it is waiting for
 * a decision. `checking` is the platform's — nobody has run the suite —
 * and `held` is a reviewer's own note to themselves. `superseded`,
 * `broken` and `disabled` are all settled, and a queue that listed them
 * would be a catalogue.
 */
const OUTSTANDING: BundleState[] = ["awaiting", "checking", "held"];

export function AlgorithmQueuePanel() {
  const { t } = useTranslation();
  const [bundles, setBundles] = useState<PluginBundleSummary[]>([]);
  const [states, setStates] = useState<Map<string, BundleState>>(new Map());
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const [imported, published] = await Promise.all([
        listPlugins(),
        publishedBundleIds().catch(() => [] as string[]),
      ]);
      setBundles(imported);
      setStates(bundleStates(imported, published));
      setFailed(null);
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading) return <p className="muted">{t("common.loading")}</p>;

  const outstanding = bundles.filter((bundle) =>
    OUTSTANDING.includes(states.get(bundle.id) ?? "checking"),
  );

  return (
    <>
      {failed ? <div className="error-box">{failed}</div> : null}
      {outstanding.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon="inbox"
            title={t("queue.algorithms.empty.title")}
            body={t("queue.algorithms.empty.body")}
            actionHref="/algorithms"
            actionLabel={t("algorithms.title")}
          />
        </div>
      ) : (
        <div className="panel">
          <div className="panel-head">
            <h3>
              {t("queue.algorithms")}{" "}
              <span className="badge muted-badge">{outstanding.length}</span>
            </h3>
          </div>
          <p className="muted small">{t("queue.algorithms.note")}</p>
          <table>
            <thead>
              <tr>
                <th>{t("algorithms.col.name")}</th>
                <th>{t("algorithms.col.revision")}</th>
                <th>{t("algorithms.col.state")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {outstanding.map((bundle) => {
                const state = states.get(bundle.id) ?? "checking";
                return (
                  <tr key={bundle.id}>
                    <td>
                      <div>{bundle.name}</div>
                      <code className="small muted">{stackIdFor(bundle)}</code>
                    </td>
                    <td>{bundle.revision}</td>
                    <td>
                      <span className="badge warn">{t(`algorithms.state.${state}`)}</span>
                      <div className="muted small">{t(`algorithms.why.${state}`)}</div>
                    </td>
                    <td>
                      {/* The decision itself is made on the algorithm's
                          own page. Publishing from a queue row would mean
                          vouching for code from a table that never showed
                          it. */}
                      <Link href="/algorithms" className="button">
                        {t("algorithms.review")}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
