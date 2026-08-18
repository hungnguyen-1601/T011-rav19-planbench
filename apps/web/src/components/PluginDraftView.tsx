"use client";

/* A plugin bundle draft, with the validator's verdict front and centre.
 *
 * The verdict is the deterministic validator's word, never the model's:
 * the Algorithm Host takes exactly one shape, and a draft out of shape
 * shows its named errors instead of a green tick. The bundle itself is
 * still shown either way — the errors point into it, and hiding the
 * draft would hide what they refer to.
 */

import type { PluginDraft } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";

export function PluginDraftView({ draft }: { draft: PluginDraft }) {
  const { t } = useTranslation();

  if (draft.refused) {
    return (
      <div className="notice">
        {t("plugin.refused")}: {draft.refused}
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <p style={{ margin: 0 }}>
        {draft.accepted ? (
          <span className="badge ok">{t("plugin.accepted")}</span>
        ) : (
          <span className="badge err">{t("plugin.rejected")}</span>
        )}{" "}
        {draft.summary}
      </p>

      {draft.errors.length > 0 ? (
        <div className="error-box">
          <strong>{t("plugin.errors")}</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {draft.errors.map((error, index) => (
              <li key={index} style={{ fontSize: 13 }}>
                {error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {draft.notes.length > 0 ? (
        <div>
          <p className="muted" style={{ margin: "0 0 4px", fontSize: 12 }}>
            {t("plugin.notes")}
          </p>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {draft.notes.map((note, index) => (
              <li key={index} className="muted" style={{ fontSize: 13 }}>
                {note}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {Object.entries(draft.files).map(([name, content]) => (
        <details key={name}>
          <summary style={{ cursor: "pointer", fontSize: 13 }}>
            <code>{name}</code>
          </summary>
          <pre
            style={{ overflowX: "auto", fontSize: 12, padding: 10 }}
          >
            {content}
          </pre>
        </details>
      ))}

      <p className="muted" style={{ margin: 0, fontSize: 12 }}>
        {t("plugin.hint")}
      </p>
    </div>
  );
}
