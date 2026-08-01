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

function Callback() {
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
      setError("This sign-in link is incomplete. Please start again.");
      return;
    }
    exchangeOAuthCode(code)
      .then((session) => {
        router.replace(session.user.needs_nickname ? "/welcome" : "/benchmarks");
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [params, router]);

  if (error) {
    return (
      <>
        <h2>Sign-in failed</h2>
        <div className="error-box">{error}</div>
        <p>
          <Link href="/login">Back to sign in</Link>
        </p>
      </>
    );
  }
  return (
    <>
      <h2>Signing you in…</h2>
      <p className="muted">Finishing the handshake with your provider.</p>
    </>
  );
}

export default function CallbackPage() {
  // useSearchParams needs a Suspense boundary during prerender.
  return (
    <Suspense fallback={<p className="muted">Signing you in…</p>}>
      <Callback />
    </Suspense>
  );
}
