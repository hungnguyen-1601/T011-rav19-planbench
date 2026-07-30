"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession, loadSession, type Session } from "@/lib/auth";

/** Shows who is signed in; benchmark pages require a session. */
export function SessionBar() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    setSession(loadSession());
  }, []);

  if (!session) {
    return (
      <div className="muted" style={{ fontSize: 12, marginTop: 16 }}>
        Not signed in — <Link href="/login">sign in</Link>
      </div>
    );
  }
  return (
    <div style={{ fontSize: 12, marginTop: 16 }}>
      <div className="muted">Signed in as</div>
      <div>
        {session.username} <span className="badge ok">{session.role}</span>
      </div>
      <button
        style={{ marginTop: 8, padding: "3px 8px", fontSize: 12 }}
        onClick={() => {
          clearSession();
          setSession(null);
          router.push("/login");
        }}
      >
        Sign out
      </button>
    </div>
  );
}
