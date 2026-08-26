"use client";

/** "Send for review": pick a member by nickname, pick a stage, say why.
 *
 * The nickname box autocompletes from `/users/search`, but the value the
 * form submits is whatever was typed — the backend resolves it and
 * refuses an unknown name with a message worth showing. Autocomplete is
 * a convenience, not a validation step, so a member who types a name
 * exactly right without waiting for the dropdown is not blocked.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "@/lib/i18n";
import { useDismiss } from "@/lib/useDismiss";
import { searchMembers, sendForReview, type ReviewStage, type UserSummary } from "@/lib/reviews";

export function SendForReview({
  benchmarkId,
  defaultStage,
  onSent,
  onClose,
}: {
  benchmarkId: string;
  defaultStage: ReviewStage;
  onSent: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [nickname, setNickname] = useState("");
  const [stage, setStage] = useState<ReviewStage>(defaultStage);
  const [comment, setComment] = useState("");
  const [matches, setMatches] = useState<UserSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);

  // Escape and a click on the backdrop both close it, like every other
  // overlay in the app.
  useDismiss(true, onClose, dialog);

  useEffect(() => {
    const term = nickname.trim();
    if (term.length < 1) {
      setMatches([]);
      return;
    }
    const timer = setTimeout(() => {
      searchMembers(term)
        .then(setMatches)
        // Search failing is not worth an error banner over a form the
        // user can still submit by typing the whole name.
        .catch(() => setMatches([]));
    }, 200);
    return () => clearTimeout(timer);
  }, [nickname]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await sendForReview(benchmarkId, nickname.trim(), stage, comment.trim());
      onSent();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={t("sendReview.title")}
    >
      <div className="modal" ref={dialog}>
        <h3 style={{ marginTop: 0 }}>{t("sendReview.title")}</h3>
        <p className="muted" style={{ fontSize: 12 }}>
          {defaultStage === "spec" ? t("sendReview.hintSpec") : t("sendReview.hintResult")}
        </p>
        {error ? <div className="error-box">{error}</div> : null}

        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <label className="field">
            {t("sendReview.reviewer")}
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              list="member-suggestions"
              placeholder={t("sendReview.reviewerPlaceholder")}
              autoFocus
              required
            />
            <datalist id="member-suggestions">
              {matches.map((member) => (
                <option key={member.id} value={member.nickname}>
                  {member.display_name || member.nickname}
                </option>
              ))}
            </datalist>
          </label>

          <label className="field">
            {t("sendReview.stage")}
            <select value={stage} onChange={(event) => setStage(event.target.value as ReviewStage)}>
              <option value="spec">{t("sendReview.stageSpec")}</option>
              <option value="result">{t("sendReview.stageResult")}</option>
            </select>
          </label>

          <label className="field">
            {t("sendReview.message")} ({t("common.optional")})
            <input
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder={t("sendReview.messagePlaceholder")}
            />
          </label>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="primary" type="submit" disabled={busy || !nickname.trim()}>
              {busy ? t("sendReview.sending") : t("sendReview.submit")}
            </button>
            <button type="button" onClick={onClose} disabled={busy}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
