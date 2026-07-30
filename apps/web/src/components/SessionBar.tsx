"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession, useSession } from "@/lib/auth";

/** Shows who is signed in; benchmark pages require a session.
 *
 * This component lives in the root layout, so it mounts once per tab and
 * client-side navigation never remounts it. It therefore has to
 * *subscribe* to the session — reading it once on mount would show
 * whatever was true before the user ever signed in.
 */
export function SessionBar() {
  const router = useRouter();
  const session = useSession();

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
          router.push("/login");
        }}
      >
        Sign out
      </button>
    </div>
  );
}
