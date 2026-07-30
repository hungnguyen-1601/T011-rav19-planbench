"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      router.push("/benchmarks");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>Sign in</h2>
      {error ? <div className="error-box">{error}</div> : null}
      <div className="panel" style={{ maxWidth: 380 }}>
        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <label className="field">
            Username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 14, fontSize: 12 }}>
          Operators create and run benchmarks; Reviewers approve specs and accept results. The
          backend provisions users from <code>PLANBENCH_SEED_USERS</code>; without it, development
          credentials are generated and printed in the API log at startup.
        </p>
      </div>
    </>
  );
}
