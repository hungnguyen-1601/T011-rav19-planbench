"use client";

/** Who is signed in, and whether anything is waiting for them.
 *
 * This component lives in the root layout, so it mounts once per tab and
 * client-side navigation never remounts it. It therefore has to
 * *subscribe* to the session — reading it once on mount would show
 * whatever was true before the user ever signed in.
 *
 * There is no role badge any more: everyone is a member, and what they
 * can do depends on the benchmark in front of them, not on a label here.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession, useSession } from "@/lib/auth";
import { fetchInbox } from "@/lib/reviews";

export function SessionBar() {
  const router = useRouter();
  const session = useSession();
  const [pending, setPending] = useState(0);

  const userId = session?.user.id ?? "";
  useEffect(() => {
    if (!userId) {
      setPending(0);
      return;
    }
    let cancelled = false;
    const load = () =>
      fetchInbox()
        .then((inbox) => {
          if (!cancelled) setPending(inbox.pending);
        })
        // A failed badge poll is not worth an error message: the inbox
        // page reports properly if something is actually wrong.
        .catch(() => {});
    load();
    const timer = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [userId]);

  if (!session) {
    return (
      <div className="muted" style={{ fontSize: 12, marginTop: 16 }}>
        Not signed in — <Link href="/login">sign in</Link>
      </div>
    );
  }

  const { user } = session;
  const label = user.nickname || user.display_name || "your account";

  return (
    <div style={{ fontSize: 12, marginTop: 16 }}>
      <Link href="/reviews" className="inbox-link">
        Review Inbox
        {pending > 0 ? <span className="badge warn">{pending}</span> : null}
      </Link>

      <div className="session-card">
        {user.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- avatars
          // come from arbitrary provider hosts; next/image would need
          // every one allow-listed in next.config.
          <img className="avatar" src={user.avatar_url} alt="" width={28} height={28} />
        ) : (
          <span className="avatar avatar-placeholder">{label.slice(0, 1).toUpperCase()}</span>
        )}
        <div style={{ minWidth: 0 }}>
          <div className="session-name">{label}</div>
          {user.email ? <div className="muted session-email">{user.email}</div> : null}
        </div>
      </div>

      {user.needs_nickname ? (
        <div style={{ marginTop: 6 }}>
          <Link href="/welcome">Choose a nickname</Link>
        </div>
      ) : null}

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
