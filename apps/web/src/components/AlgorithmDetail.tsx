"use client";

/** One imported algorithm, and the acts a reviewer can perform on it.
 *
 * Two readers, one component. An engineer sees what the algorithm needs
 * and whether this host can run it — enough to decide whether to pick
 * it. A reviewer additionally sees the code's identity, its publication
 * history and who did what to it, which is what vouching for it rests
 * on. The split is the server's: the fields describing code arrive as
 * `null` for a reader without `algorithm.inspect`, and every section
 * below draws nothing rather than an empty box when its data is absent.
 *
 * **Every act asks for a reason, and the destructive ones require one.**
 * The reason is the only part of the record that survives into a
 * sentence a person later reads — "held" tells a colleague nothing, and
 * "held: the conformance run was against the wrong robot profile" tells
 * them exactly what to fix. Publishing is the exception that can go
 * without: it is the act that says nothing is wrong.
 */

import { useCallback, useEffect, useState } from "react";

import { HostReport } from "@/components/PluginImportPanel";
import { CAPABILITIES, can, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  disablePlugin,
  getPlugin,
  holdPlugin,
  pluginEvents,
  publishPlugin,
  releasePluginHold,
  revalidatePlugin,
  unpublishPlugin,
  type PluginBundleDetail,
  type PluginEvent,
} from "@/lib/plugins";

type Act = "publish" | "unpublish" | "hold" | "release-hold" | "disable" | "validate";

export function AlgorithmDetail({
  bundleId,
  onChanged,
}: {
  bundleId: string;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const session = useSession();
  const [detail, setDetail] = useState<PluginBundleDetail | null>(null);
  const [events, setEvents] = useState<PluginEvent[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const inspects = can(session?.user, CAPABILITIES.algorithmInspect);
  const publishes = can(session?.user, CAPABILITIES.algorithmPublish);

  const load = useCallback(() => {
    getPlugin(bundleId)
      .then(setDetail)
      .catch((caught) => setFailed(caught instanceof Error ? caught.message : String(caught)));
    if (!inspects) {
      setEvents([]);
      return;
    }
    pluginEvents(bundleId)
      .then(setEvents)
      // The timeline is context, not the page. A deployment with
      // governance off answers 404 here, and that is not worth a red box
      // on a panel whose other half loaded.
      .catch(() => setEvents([]));
  }, [bundleId, inspects]);

  useEffect(load, [load]);

  const act = async (which: Act) => {
    setBusy(true);
    setFailed(null);
    try {
      if (which === "publish") await publishPlugin(bundleId, reason);
      else if (which === "unpublish") await unpublishPlugin(bundleId, reason);
      else if (which === "hold") await holdPlugin(bundleId, reason);
      else if (which === "release-hold") await releasePluginHold(bundleId, reason);
      else if (which === "disable") await disablePlugin(bundleId, reason);
      else await revalidatePlugin(bundleId);
      setReason("");
      load();
      onChanged();
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  if (!detail) {
    return (
      <div className="panel">
        <p className="muted">{failed ?? t("common.loading")}</p>
      </div>
    );
  }

  const bundle = detail.bundle;
  const isCurrent = detail.published_revision === bundle.revision;
  const needsReason = !reason.trim();

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>
          {bundle.name} <span className="muted">v{bundle.plugin_version}</span>
        </h3>
        <span className="muted small">
          {t("algorithms.revisionOf", {
            revision: String(bundle.revision),
            plugin: bundle.plugin_id,
          })}
        </span>
      </div>

      {failed ? <div className="error-box">{failed}</div> : null}

      <p className="muted">{bundle.description}</p>

      <HostReport detail={detail} />

      {/* The half that describes code. Absent for a picker, because
          reading code is what the reviewer package is for. */}
      {inspects ? (
        <dl className="plugins-report-facts">
          <dt>{t("algorithms.entryPoint")}</dt>
          <dd>
            <code>{detail.entry_point ?? "—"}</code>
          </dd>
          <dt>{t("algorithms.checksum")}</dt>
          <dd>
            <code className="small">{bundle.checksum || "—"}</code>
          </dd>
          <dt>{t("algorithms.archive")}</dt>
          <dd className="muted">
            {bundle.original_filename} · {Math.round(bundle.file_size / 1024)} KB
          </dd>
        </dl>
      ) : null}

      {publishes ? (
        <div className="row" style={{ marginTop: 12, alignItems: "flex-end", gap: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span>{t("algorithms.reason")}</span>
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={t("algorithms.reasonHint")}
              disabled={busy}
            />
          </label>
        </div>
      ) : null}

      <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
        {publishes ? (
          <>
            {/* Publishing needs no reason: it is the act that says
                nothing is wrong. Every other one takes something away
                from somebody, and they get told why. */}
            {isCurrent ? (
              <button type="button" disabled={busy || needsReason} onClick={() => act("unpublish")}>
                {t("algorithms.act.unpublish")}
              </button>
            ) : (
              <button
                type="button"
                className="primary"
                disabled={busy || bundle.validation_status !== "loaded"}
                onClick={() => act("publish")}
              >
                {t("algorithms.act.publish")}
              </button>
            )}
            {bundle.status === "held" ? (
              <button type="button" disabled={busy} onClick={() => act("release-hold")}>
                {t("algorithms.act.releaseHold")}
              </button>
            ) : (
              <button
                type="button"
                disabled={busy || needsReason || bundle.status === "disabled"}
                onClick={() => act("hold")}
              >
                {t("algorithms.act.hold")}
              </button>
            )}
            <button
              type="button"
              className="danger"
              disabled={busy || needsReason || bundle.status === "disabled"}
              onClick={() => act("disable")}
            >
              {t("algorithms.act.disable")}
            </button>
          </>
        ) : null}
        {bundle.owned || inspects ? (
          <button type="button" disabled={busy} onClick={() => act("validate")}>
            {t("plugins.recheck")}
          </button>
        ) : null}
      </div>

      {publishes ? <p className="muted small">{t("algorithms.disableIsFinal")}</p> : null}

      {detail.publications && detail.publications.length > 0 ? (
        <>
          <h4>{t("algorithms.history")}</h4>
          <table>
            <thead>
              <tr>
                <th>{t("algorithms.col.revision")}</th>
                <th>{t("algorithms.col.published")}</th>
                <th>{t("algorithms.col.ended")}</th>
                <th>{t("algorithms.col.reason")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.publications.map((row) => (
                <tr key={`${row.bundle_id}-${row.published_at}`}>
                  <td>{row.revision}</td>
                  <td className="muted small">{row.published_at}</td>
                  <td className="muted small">
                    {/* Two closing dates, never merged into one: a
                        revision that a newer one replaced and a revision
                        somebody withdrew look identical in a column that
                        only says when it stopped. */}
                    {row.unpublished_at
                      ? t("algorithms.withdrawnAt", { at: row.unpublished_at })
                      : row.superseded_at
                        ? t("algorithms.supersededAt", { at: row.superseded_at })
                        : t("algorithms.stillCurrent")}
                  </td>
                  <td className="muted small">{row.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      {events.length > 0 ? (
        <>
          <h4>{t("algorithms.timeline")}</h4>
          <ul className="small">
            {events.map((event) => (
              <li key={event.sequence}>
                <strong>{event.action}</strong> · rev {event.revision} ·{" "}
                <span className="muted">
                  {event.actor_user_id ?? "system"} ({event.authorized_capability})
                </span>{" "}
                <span className="muted">{event.created_at}</span>
                {event.reason ? <div className="muted">{event.reason}</div> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
