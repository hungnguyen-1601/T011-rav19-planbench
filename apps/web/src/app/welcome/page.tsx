"use client";

/** First sign-in: choose a nickname.
 *
 * This is not decoration. A nickname is how other members address a
 * review request to you, so an account without one cannot be reached —
 * which is why the backend refuses everything else until it is set, and
 * why this page checks availability as you type rather than after you
 * submit.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch, updateSessionUser, useSession, type SessionUser } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

interface NicknameCheck {
  nickname: string;
  available: boolean;
  valid: boolean;
  message: string;
}

export default function WelcomePage() {
  const { t } = useTranslation();
  const router = useRouter();
  const session = useSession();
  const [nickname, setNickname] = useState("");
  const [check, setCheck] = useState<NicknameCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const suggestion = session?.user.display_name ?? "";

  useEffect(() => {
    if (session === null) router.replace("/login");
  }, [session, router]);

  // Debounced: this fires per keystroke, and a request per character
  // would be noise in the log and rate-limit bait.
  useEffect(() => {
    const candidate = nickname.trim();
    if (!candidate) {
      setCheck(null);
      return;
    }
    const timer = setTimeout(() => {
      authFetch<NicknameCheck>(`/users/nickname-available?nickname=${encodeURIComponent(candidate)}`)
        .then((result) => {
          // Ignore a reply for a value the user has already changed.
          setCheck((current) => (candidate === nickname.trim() ? result : current));
        })
        .catch(() => setCheck(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [nickname]);

  const submit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        const user = await authFetch<SessionUser>("/users/me/nickname", {
          method: "PUT",
          body: JSON.stringify({ nickname: nickname.trim() }),
        });
        updateSessionUser(user);
        router.push("/decisions");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [nickname, router],
  );

  if (!session) return <p className="muted">{t("common.loading")}</p>;

  const ready = Boolean(check?.valid && check?.available) && !busy;

  return (
    <>
      <h2>{t("welcome.title")}</h2>
      <p className="muted">{t("welcome.subtitle")}</p>
      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel" style={{ maxWidth: 420 }}>
        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <label className="field">
            {t("welcome.nicknameLabel")}
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              placeholder={suggestion ? suggestion.toLowerCase().replace(/\s+/g, "-") : "your-name"}
              autoFocus
              required
            />
          </label>
          <div style={{ minHeight: 18, fontSize: 12 }}>
            {check === null ? (
              <span className="muted">{t("welcome.rules")}</span>
            ) : check.valid && check.available ? (
              <span className="badge ok">
                {t("welcome.available", { nickname: check.nickname })}
              </span>
            ) : (
              <span className="badge warn">{check.message}</span>
            )}
          </div>
          <button className="primary" type="submit" disabled={!ready}>
            {busy ? t("welcome.saving") : t("welcome.continue")}
          </button>
        </form>
        {session.user.email ? (
          <p className="muted" style={{ marginTop: 14, fontSize: 12 }}>
            {session.user.providers.length
              ? t("welcome.signedInVia", {
                  email: session.user.email,
                  providers: session.user.providers.join(", "),
                })
              : t("welcome.signedInAs", { email: session.user.email })}
          </p>
        ) : null}
      </div>
    </>
  );
}
