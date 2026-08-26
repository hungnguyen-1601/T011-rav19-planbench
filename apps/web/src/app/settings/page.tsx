"use client";

/** Settings — which model answers, and the key that lets it.
 *
 * The page fetches and the form renders; nothing here decides what the
 * screen looks like. That split is what lets the form be asserted on
 * without a browser, and it keeps the one thing this file is really
 * about — the refusal handling — in one place.
 *
 * A save returns the **new** settings, so the answer replaces the state
 * rather than triggering a re-fetch. Re-reading would ask the same
 * question twice and leave a window where the screen disagrees with the
 * response that just arrived.
 */

import { useCallback, useEffect, useState } from "react";

import { AgentSettingsForm } from "@/components/AgentSettingsForm";
import { fieldErrorsOf, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { getAgentSettings, saveAgentKey, type AgentSettings } from "@/lib/settings";

export default function SettingsPage() {
  const { t } = useTranslation();
  const session = useSession();
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ path: string; message: string }[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAgentSettings()
      .then((result) => {
        if (cancelled) return;
        setSettings(result);
        setLoadError(null);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setLoadError(caught instanceof Error ? caught.message : String(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Re-read after a sign-in: the endpoint needs a session, and the
    // first attempt on a cold tab happens before one exists.
  }, [session?.token]);

  const save = useCallback(async (apiKey: string) => {
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    setFieldErrors([]);
    try {
      const updated = await saveAgentKey(apiKey);
      setSettings(updated);
      setSaved(true);
    } catch (caught) {
      // An addressed refusal (a key that is too short) belongs beside
      // the input. Everything else — a 403 above all — is about the
      // request rather than the value, and goes above the form.
      const addressed = fieldErrorsOf(caught);
      setFieldErrors(addressed);
      if (addressed.length === 0) {
        setSaveError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      setSaving(false);
    }
  }, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("settings.title")}</h2>
          <p>{t("settings.subtitle")}</p>
        </div>
      </div>

      {loadError ? <div className="error-box">{loadError}</div> : null}

      {loading ? (
        <p className="muted">{t("common.loading")}</p>
      ) : settings ? (
        <AgentSettingsForm
          settings={settings}
          canEdit={session?.user.is_admin ?? false}
          saving={saving}
          saved={saved}
          error={saveError}
          fieldErrors={fieldErrors}
          onSave={save}
        />
      ) : null}
    </>
  );
}
