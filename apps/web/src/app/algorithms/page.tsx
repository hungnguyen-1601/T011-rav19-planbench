"use client";

/** Every algorithm this deployment can offer, and why one cannot.
 *
 * **The gap this fills.** Imported algorithms were reachable only from a
 * tab inside the Models page, which is where trained policies live —
 * two different kinds of thing behind one heading. Worse, an engineer
 * who could not find an algorithm in the candidate picker had nowhere to
 * look: the reason was either "nobody has published it", "a newer
 * revision took over", "it cannot run on this host" or "a reviewer
 * turned it off", and none of those were visible anywhere.
 *
 * So this page lists every imported algorithm and says which state each
 * is in.
 *
 * **The built-in catalogue is deliberately not here.** `/candidates`
 * shows it, with the observation classes that made it the reason an
 * older `/algorithms` page was deleted rather than regrouped. A second,
 * thinner copy on this page undid that decision without noticing it had
 * been made, and nothing this page answers needed it. A bundle nobody has published still appears,
 * greyed, saying so. That is deliberate: an algorithm simply missing
 * from a list reads as a broken system, and the person picking cannot
 * tell "not here" from "not yet vouched for".
 *
 * The controls a reviewer needs are on the detail panel rather than in
 * the row, because publishing is a decision about one revision and a
 * table cell is not enough to make it on.
 */

import { useCallback, useEffect, useState } from "react";

import { AlgorithmDetail } from "@/components/AlgorithmDetail";
import { EmptyState } from "@/components/EmptyState";
import { CAPABILITIES, can, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  bundleStates,
  listPlugins,
  publishedBundleIds,
  stackIdFor,
  type BundleState,
  type PluginBundleSummary,
} from "@/lib/plugins";

/** Which chip a state gets. `published` is the only good outcome; the
 * rest are either somebody's decision or something to fix, and a reader
 * scanning the column should be able to see that without reading. */
const TONE: Record<BundleState, string> = {
  published: "ok",
  superseded: "muted",
  awaiting: "warn",
  checking: "warn",
  held: "warn",
  broken: "danger",
  disabled: "danger",
};

export default function AlgorithmsPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [bundles, setBundles] = useState<PluginBundleSummary[]>([]);
  const [states, setStates] = useState<Map<string, BundleState>>(new Map());
  const [selected, setSelected] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [imported, published] = await Promise.all([
        listPlugins(),
        // A deployment with governance off answers 404 here. That is not
        // a failure: with nothing published, every bundle's state is
        // decided by whether it is runnable, which is what an empty set
        // makes `bundleStates` say.
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
    void refresh();
  }, [refresh]);

  const inspects = can(session?.user, CAPABILITIES.algorithmInspect);

  return (
    <section>
      <header className="page-head">
        <h1>{t("algorithms.title")}</h1>
        <p className="muted">{t("algorithms.subtitle")}</p>
      </header>

      {failed ? <div className="error-box">{failed}</div> : null}

      <div className="panel">
        <div className="panel-head">
          <h3>{t("plugins.listTitle")}</h3>
        </div>
        {loading ? (
          <p className="muted">{t("common.loading")}</p>
        ) : bundles.length === 0 ? (
          <EmptyState title={t("algorithms.empty.title")} body={t("algorithms.empty.body")} />
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("algorithms.col.name")}</th>
                <th>{t("algorithms.col.revision")}</th>
                <th>{t("algorithms.col.state")}</th>
                <th>{t("plugins.requires")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {bundles.map((bundle) => {
                const state = states.get(bundle.id) ?? "checking";
                return (
                  <tr key={bundle.id}>
                    <td>
                      <div>{bundle.name}</div>
                      <code className="small muted">{stackIdFor(bundle)}</code>
                    </td>
                    <td>{bundle.revision}</td>
                    <td>
                      <span className={`badge ${TONE[state]}`}>
                        {t(`algorithms.state.${state}`)}
                      </span>
                      <div className="muted small">{t(`algorithms.why.${state}`)}</div>
                    </td>
                    <td className="muted small">{bundle.requirements.join(", ") || "—"}</td>
                    <td>
                      <button
                        type="button"
                        onClick={() => setSelected(selected === bundle.id ? null : bundle.id)}
                      >
                        {t(inspects ? "algorithms.review" : "algorithms.details")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {selected ? <AlgorithmDetail bundleId={selected} onChanged={() => void refresh()} /> : null}
    </section>
  );
}
