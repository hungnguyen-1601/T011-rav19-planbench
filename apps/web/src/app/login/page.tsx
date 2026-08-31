"use client";

/** Sign in.
 *
 * The buttons come from `/auth/providers`, not from a build-time flag:
 * a deployment with no Google credentials must not offer a button that
 * leads to an error page. With nothing configured at all, the page says
 * so plainly rather than looking broken.
 */

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { fetchAuthProviders, login, oauthStartUrl, type AuthProviders } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M45 24c0-1.6-.1-2.7-.4-4H24v7.5h12c-.2 2-1.6 5-4.5 7l6.9 5.4C42.5 36.2 45 30.7 45 24z"
      />
      <path
        fill="#34A853"
        d="M24 46c6 0 11-2 14.4-5.4l-6.9-5.4C29.7 36.5 27.1 37.4 24 37.4c-5.8 0-10.7-3.9-12.5-9.1l-7.1 5.5C7.9 41 15.4 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.5 28.3c-.5-1.4-.7-2.8-.7-4.3s.3-2.9.7-4.3l-7.1-5.5C2.9 17.1 2 20.4 2 24s.9 6.9 2.4 9.8l7.1-5.5z"
      />
      <path
        fill="#EA4335"
        d="M24 10.6c3.3 0 6.2 1.1 8.5 3.3l6.1-6.1C34.9 4.3 30 2 24 2 15.4 2 7.9 7 4.4 14.2l7.1 5.5c1.8-5.2 6.7-9.1 12.5-9.1z"
      />
    </svg>
  );
}

function GitHubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function SignIn() {
  const { t } = useTranslation();
  const router = useRouter();
  const params = useSearchParams();
  const [providers, setProviders] = useState<AuthProviders | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // A failed OAuth round trip lands back here with its reason.
  const [error, setError] = useState<string | null>(params.get("error"));

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchAuthProviders()
      .then(setProviders)
      .catch((err) => setLoadError(err instanceof Error ? err.message : String(err)));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await login(username, password);
    /* **Dashboard, not the comparison list.** Signing in used to land on
       `/decisions`, which is one job among several and reads as the
       app's whole purpose to somebody arriving for the first time. The
       dashboard is where the counts, the shortcuts and the guide are —
       what a reader needs before they know which page they want. */
      router.push(session.user.needs_nickname ? "/welcome" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const nothingConfigured =
    providers && !providers.google && !providers.github && !providers.dev_login;

  /* The way out.
   *
   * `router.back()` alone is not it: `/login` is reachable directly —
   * a bookmark, a link in a message, a redirect that replaced the entry
   * — and in a fresh tab there is nothing behind it, so `back()` either
   * does nothing or leaves the app entirely. `history.length` is the
   * one thing that separates the two, and it is read at click time
   * rather than at render so the first paint cannot disagree with the
   * server's. */
  const leave = () => {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/");
  };

  return (
    <>
      <button type="button" className="ghost login-back" onClick={leave}>
        <Icon name="chevronLeft" size={16} />
        {t("login.back")}
      </button>
      <h2>{t("login.title")}</h2>
      {error ? <div className="error-box">{error}</div> : null}
      {loadError ? (
        <div className="error-box">{t("login.unreachable", { message: loadError })}</div>
      ) : null}

      <div className="panel" style={{ maxWidth: 400 }}>
        {providers?.google || providers?.github ? (
          <div style={{ display: "grid", gap: 10 }}>
            {providers.google ? (
              <a className="oauth-button" href={oauthStartUrl("google")}>
                <GoogleMark />
                {t("login.google")}
              </a>
            ) : null}
            {providers.github ? (
              <a className="oauth-button" href={oauthStartUrl("github")}>
                <GitHubMark />
                {t("login.github")}
              </a>
            ) : null}
          </div>
        ) : null}

        {(providers?.google || providers?.github) && providers?.dev_login ? (
          <div className="divider">{t("login.or")}</div>
        ) : null}

        {providers?.dev_login ? (
          <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
            <label className="field">
              {t("login.nickname")}
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              {t("login.password")}
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? t("login.submitting") : t("login.submit")}
            </button>
            <p className="muted" style={{ fontSize: 12, margin: 0 }}>
              {t("login.devHint")}
            </p>
          </form>
        ) : null}

        {nothingConfigured ? (
          <div>
            <p>{t("login.nothingConfigured")}</p>
            <p className="muted" style={{ fontSize: 13 }}>
              {t("login.nothingConfiguredHelp")}
            </p>
          </div>
        ) : null}

        {!providers && !loadError ? <p className="muted">{t("login.loading")}</p> : null}
      </div>
    </>
  );
}

export default function LoginPage() {
  // useSearchParams reads the ?error= a failed OAuth round trip leaves
  // behind, and needs a Suspense boundary to prerender.
  return (
    <Suspense fallback={<p className="muted">…</p>}>
      <SignIn />
    </Suspense>
  );
}
