"use client";

/** "Send for review": pick a member by nickname, pick a stage, say why.
 *
 * The nickname box autocompletes from `/users/search`, but the value the
 * form submits is whatever was typed — the backend resolves it and
 * refuses an unknown name with a message worth showing. Autocomplete is
 * a convenience, not a validation step, so a member who types a name
 * exactly right without waiting for the dropdown is not blocked.
 */

import { useEffect, useState } from "react";
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
  const [nickname, setNickname] = useState("");
  const [stage, setStage] = useState<ReviewStage>(defaultStage);
  const [comment, setComment] = useState("");
  const [matches, setMatches] = useState<UserSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Send for review">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>Send for review</h3>
        <p className="muted" style={{ fontSize: 12 }}>
          The member you name becomes the only person who can answer — and until they do, you
          cannot {defaultStage === "spec" ? "run this benchmark" : "accept these results"}{" "}
          yourself. You can cancel the request at any time.
        </p>
        {error ? <div className="error-box">{error}</div> : null}

        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <label className="field">
            Reviewer nickname
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              list="member-suggestions"
              placeholder="who should look at this?"
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
            What to review
            <select value={stage} onChange={(event) => setStage(event.target.value as ReviewStage)}>
              <option value="spec">Spec — before the run</option>
              <option value="result">Results — after the run</option>
            </select>
          </label>

          <label className="field">
            Message (optional)
            <input
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="anything they should look at in particular?"
            />
          </label>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="primary" type="submit" disabled={busy || !nickname.trim()}>
              {busy ? "Sending…" : "Send request"}
            </button>
            <button type="button" onClick={onClose} disabled={busy}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
