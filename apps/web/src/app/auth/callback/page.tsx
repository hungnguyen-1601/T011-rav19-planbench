"use client";

/** Where the backend sends the browser after a provider round trip.
 *
 * The URL carries a one-time code, never a token. This page trades it
 * for a session over POST and then replaces the history entry, so the
 * code does not sit in the back button — it is already spent by then,
 * but a spent code in history is still noise a user can trip over.
 */

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { exchangeOAuthCode } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

function Callback() {
  const { t } = useTranslation();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  // React runs effects twice in development; the code is one-time, so
  // the second run would always fail and overwrite a good session.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const failure = params.get("error");
    if (failure) {
      setError(failure);
      return;
    }
    const code = params.get("code");
    if (!code) {
      setError(t("callback.incomplete"));
      return;
    }
    exchangeOAuthCode(code)
      .then((session) => {
        router.replace(session.user.needs_nickname ? "/welcome" : "/decisions");
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [params, router, t]);

  if (error) {
    return (
      <>
        <h2>{t("callback.failed")}</h2>
        <div className="error-box">{error}</div>
        <p>
          <Link href="/login">{t("callback.backToLogin")}</Link>
        </p>
      </>
    );
  }
  return (
    <>
      <h2>{t("callback.signingIn")}</h2>
      <p className="muted">{t("callback.handshake")}</p>
    </>
  );
}

export default function CallbackPage() {
  // useSearchParams needs a Suspense boundary during prerender.
  return (
    <Suspense fallback={<p className="muted">…</p>}>
      <Callback />
    </Suspense>
  );
}
