"use client";

/** The agent settings form, with no idea where its data came from.
 *
 * Everything arrives as props and the only state it owns is the key
 * being typed. That is what makes the two claims below assertable in a
 * test without a browser: a non-admin gets no save control, and a
 * present key is shown as a hint rather than as itself.
 *
 * The key is deliberately **not** lifted to the page. It exists for the
 * length of one submission and nothing above needs it; keeping it here
 * means there is exactly one place it can be read from.
 */

import { useState } from "react";

import { useTranslation } from "@/lib/i18n";
import type { AgentSettings } from "@/lib/settings";

export function AgentSettingsForm({
  settings,
  canEdit,
  saving,
  saved,
  error,
  fieldErrors,
  onSave,
}: {
  settings: AgentSettings;
  /** Admins only. The server enforces this too — hiding the control
   *  keeps a button from promising something that answers with a 403. */
  canEdit: boolean;
  saving: boolean;
  saved: boolean;
  /** A refusal with no field address, shown above the form. */
  error: string | null;
  /** Server refusals addressed by field path (`api_key`). */
  fieldErrors: { path: string; message: string }[];
  onSave: (apiKey: string) => void;
}) {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState("");

  const keyError = fieldErrors.find((entry) => entry.path.endsWith("api_key"));

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!apiKey.trim() || saving) return;
    onSave(apiKey.trim());
    setApiKey("");
  };

  return (
    <>
      {/* **The state line comes first, because it is the answer to the
          question that brings anyone here.** A configured provider and
          an answering provider are different facts, and reading only
          the first is how somebody concludes they are finished while
          the offline responder is still doing the talking. */}
      {settings.active_deterministic ? (
        <div className="panel settings-status">
          <span className="badge warn">{t("settings.status.offline")}</span>
          <p className="muted">{t("settings.status.offlineHint")}</p>
        </div>
      ) : settings.ready ? (
        <div className="panel settings-status">
          <span className="badge ok">
            {t("settings.status.live", {
              provider: settings.active_provider,
              model: settings.active_model || settings.model,
            })}
          </span>
        </div>
      ) : (
        <div className="panel settings-status">
          <span className="badge warn">{t("settings.status.notReady")}</span>
          {settings.missing ? <p className="muted">{settings.missing}</p> : null}
        </div>
      )}

      <div className="panel">
        <h3>{t("settings.model.title")}</h3>
        <label className="field">
          <span>{t("settings.model.label")}</span>
          {/* Disabled rather than absent: one option is still the answer
              to "which model is this", and a control that disappears
              when there is nothing to choose leaves the reader unsure
              whether the choice exists at all. */}
          <select value={settings.model} disabled onChange={() => {}}>
            {settings.models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
        <p className="muted settings-note">{t("settings.model.hint")}</p>
        <p className="muted settings-note">
          {t("settings.provider", { provider: settings.provider })}
        </p>
      </div>

      <div className="panel">
        <h3>{t("settings.key.title")}</h3>
        <p className="muted settings-note">
          {settings.key_present
            ? t("settings.key.current", { hint: settings.key_hint })
            : t("settings.key.absent")}
        </p>
        <p className="muted settings-note">
          {t("settings.key.envHint", { env: settings.api_key_env })}
        </p>

        {canEdit ? (
          <form onSubmit={submit}>
            {error ? <div className="error-box">{error}</div> : null}
            <label className="field">
              <span>{t("settings.key.label")}</span>
              <input
                type="password"
                value={apiKey}
                autoComplete="off"
                placeholder={t("settings.key.placeholder")}
                onChange={(event) => setApiKey(event.target.value)}
              />
            </label>
            {keyError ? <p className="settings-field-error">{keyError.message}</p> : null}
            <div className="settings-actions">
              <button type="submit" className="primary" disabled={saving || !apiKey.trim()}>
                {saving ? t("settings.key.saving") : t("common.save")}
              </button>
              {saved ? <span className="badge ok">{t("settings.saved")}</span> : null}
            </div>
          </form>
        ) : (
          <p className="muted settings-note">{t("settings.readOnly")}</p>
        )}
      </div>
    </>
  );
}
