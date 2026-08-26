"use client";

/** Importing an algorithm: the form, and what the host says about it.
 *
 * **The isolation warning is above the button, not in a tooltip.**
 * Uploading here runs the uploader's code on the server. That is stated
 * in three places on purpose — the threat model, the subprocess lane's
 * docstring, and here — because it is the claim most likely to soften as
 * it gets retold, and this is the only one of the three a person
 * uploading will ever read.
 *
 * **The compatibility report is rendered, not summarised.** Every list
 * in it was filled in by the host's own preflight, and `why` is its
 * one-line explanation naming every blocker at once. Rewriting them into
 * something friendlier would mean this component inventing a diagnosis
 * the platform did not make — and the friendlier sentence is exactly the
 * one that would go stale when the host learned a new refusal.
 */

import { useEffect, useState } from "react";

import { Hint } from "@/components/Hint";
import { Icon } from "@/components/Icon";
import { useTranslation } from "@/lib/i18n";
import type { RobotProfile } from "@/lib/models";
import {
  type HostCompatibility,
  type PluginBundleSummary,
  getPlugin,
  importPlugin,
} from "@/lib/plugins";

export function PluginImportPanel({
  profiles,
  onImported,
}: {
  profiles: RobotProfile[];
  onImported: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1");
  const [description, setDescription] = useState("");
  const [robotProfileId, setRobotProfileId] = useState("");
  const [bundleFile, setBundleFile] = useState<File | null>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  /** The last import's verdict, kept on screen after the form clears:
   *  the answer to "did it work?" is the report, and a form that reset
   *  itself and said nothing would have thrown it away. */
  const [verdict, setVerdict] = useState<{
    bundle: PluginBundleSummary;
    compatibility: HostCompatibility;
  } | null>(null);

  // Opens on the first profile rather than blank: every bundle needs
  // one, and a select that starts empty is a field somebody misses and a
  // 422 they then have to read.
  useEffect(() => {
    if (!robotProfileId && profiles.length > 0) setRobotProfileId(profiles[0].id);
  }, [profiles, robotProfileId]);

  const choose = (file: File | null) => {
    setRefusal(null);
    if (!file) {
      setBundleFile(null);
      return;
    }
    // Refused here as well as on the server. The server's message is the
    // one that matters, but learning that a folder is not a `.zip` after
    // sending it is a refusal that cost the whole transfer to deliver.
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setBundleFile(null);
      setRefusal(t("plugins.wrongExtension"));
      return;
    }
    setBundleFile(file);
  };

  const ready = name.trim() !== "" && robotProfileId !== "" && bundleFile !== null;

  const submit = async () => {
    if (!bundleFile || !ready) return;
    setPercent(0);
    setRefusal(null);
    setVerdict(null);
    try {
      const bundle = await importPlugin(
        { name, version, description, robotProfileId, bundleFile },
        setPercent,
      );
      // Fetch the detail rather than trusting the create response: the
      // compatibility report is recomputed on read, and the answer that
      // matters is the one about the host as it is now.
      const detail = await getPlugin(bundle.id);
      setVerdict(detail);
      setName("");
      setDescription("");
      setBundleFile(null);
      onImported();
    } catch (caught) {
      setRefusal(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setPercent(null);
    }
  };

  return (
    <div className="panel models-upload">
      <div className="panel-head">
        <h3>
          <span className="panel-title-icon" aria-hidden="true">
            <Icon name="plus" size={17} />
          </span>
          {t("plugins.import")}
        </h3>
      </div>

      <div className="warn-box plugins-isolation">{t("plugins.isolation")}</div>

      <div className="models-upload-grid">
        <label className="field">
          <span>{t("models.name")}</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("models.version")}</span>
          <input value={version} onChange={(event) => setVersion(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("models.robotProfile")}</span>
          <select
            value={robotProfileId}
            onChange={(event) => setRobotProfileId(event.target.value)}
          >
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name} · {profile.lidar_beams} beams
              </option>
            ))}
          </select>
        </label>
        <label className="field models-upload-wide">
          <span>{t("models.description")}</span>
          <input value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label className="field models-upload-wide">
          <span>
            {t("plugins.bundle")} <Hint text={t("plugins.bundleHint")} />
          </span>
          <input
            type="file"
            accept=".zip"
            onChange={(event) => choose(event.target.files?.[0] ?? null)}
          />
        </label>
      </div>

      {refusal ? <div className="error-box">{refusal}</div> : null}
      {percent !== null ? (
        <p className="muted small">{t("plugins.uploading", { percent: String(percent) })}</p>
      ) : null}

      <button type="button" className="primary" disabled={!ready || percent !== null} onClick={() => void submit()}>
        {t("plugins.importAction")}
      </button>

      {verdict ? <HostReport detail={verdict} /> : null}
    </div>
  );
}

/** The host's verdict on one bundle, field by field.
 *
 * Only non-empty lists are shown. A report rendering every field would
 * print eight empty rows for a plugin with nothing wrong with it, and
 * the one row that mattered would be the hardest to find.
 */
export function HostReport({
  detail,
}: {
  detail: { bundle: PluginBundleSummary; compatibility: HostCompatibility };
}) {
  const { t } = useTranslation();
  const report = detail.compatibility;
  const blockers: [string, string[]][] = [
    ["plugins.report.missingCapabilities", report.missing_capabilities],
    ["plugins.report.missingProviders", report.missing_providers],
    ["plugins.report.missingRuntime", report.missing_runtime],
    ["plugins.report.incompatibleActions", report.incompatible_action_types],
    ["plugins.report.incompatibleDynamics", report.incompatible_dynamics],
    ["plugins.report.incompatibleExecution", report.incompatible_execution_models],
    ["plugins.report.fairnessRefusals", report.fairness_refusals],
    ["plugins.report.undeclaredProviders", report.undeclared_providers],
    ["plugins.report.graphProblems", report.graph_problems],
  ].filter(([, values]) => values.length > 0) as [string, string[]][];

  return (
    <div className="plugins-report">
      <dl className="plugins-report-facts">
        <dt>{t("plugins.report.state")}</dt>
        <dd>
          <span className={`badge ${report.runnable ? "ok" : "err"}`}>{report.state}</span>
        </dd>
        <dt>{t("plugins.report.evidence")}</dt>
        <dd>{report.evidence_class}</dd>
        <dt>{t("plugins.report.lane")}</dt>
        <dd>{report.runtime_lane || "—"}</dd>
        <dt>{t("plugins.report.conformance")}</dt>
        <dd>
          <span className={`badge ${detail.bundle.validation_status === "loaded" ? "ok" : "warn"}`}>
            {detail.bundle.validation_status}
          </span>
          {detail.bundle.validation_message ? (
            <div className="muted small">{detail.bundle.validation_message}</div>
          ) : null}
        </dd>
        {report.provider_order.length > 0 ? (
          <>
            <dt>{t("plugins.report.providers")}</dt>
            <dd>
              <code className="small">{report.provider_order.join(", ")}</code>
            </dd>
          </>
        ) : null}
      </dl>

      {blockers.length > 0 ? (
        <ul className="plugins-report-blockers">
          {blockers.map(([key, values]) => (
            <li key={key}>
              {t(key)}: <code>{values.join(", ")}</code>
            </li>
          ))}
        </ul>
      ) : null}

      {/* The host's own one-line explanation, last and verbatim. It
          names every blocker at once, which is the whole reason it
          exists — fixing them one preflight at a time is the cost that
          report was written to avoid. */}
      {report.why ? <p className="muted small plugins-report-why">{report.why}</p> : null}
    </div>
  );
}
