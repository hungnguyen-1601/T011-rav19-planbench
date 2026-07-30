"use client";

/** Token storage and the authenticated fetch wrapper.
 *
 * The token lives in sessionStorage: it disappears when the tab closes
 * and is never written to a cookie, so there is no CSRF surface.
 *
 * The session is exposed as a subscribable store rather than a plain
 * read. Reading it once per component was wrong in a way that only
 * showed up in the sidebar: `SessionBar` lives in the root layout, so it
 * mounts once for the life of the tab. A one-shot read in `useEffect`
 * captured "signed out" before the user ever logged in, and no
 * client-side navigation ever remounted it to correct that. The same
 * staleness applied in reverse to every page — signing out from the
 * sidebar left them still believing they had a session.
 */

import { useSyncExternalStore } from "react";
import { API_BASE } from "./api";

const TOKEN_KEY = "planbench.token";
const USER_KEY = "planbench.user";

export interface Session {
  token: string;
  username: string;
  role: "operator" | "reviewer" | "admin";
}

const listeners = new Set<() => void>();

// `useSyncExternalStore` compares snapshots by identity, so this must be
// a stable reference: rebuilding the object on every read would loop
// forever. It is replaced only when the stored value actually changes.
let snapshot: Session | null = null;
let loaded = false;

function readStorage(): Session | null {
  if (typeof window === "undefined") return null;
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  const raw = window.sessionStorage.getItem(USER_KEY);
  if (!token || !raw) return null;
  try {
    const user = JSON.parse(raw) as { username: string; role: Session["role"] };
    return { token, ...user };
  } catch {
    // A corrupted entry is treated as no session rather than crashing
    // the whole layout.
    return null;
  }
}

function same(a: Session | null, b: Session | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return a.token === b.token && a.username === b.username && a.role === b.role;
}

function refresh(): void {
  const next = readStorage();
  if (loaded && same(snapshot, next)) return;
  snapshot = next;
  loaded = true;
  for (const listener of listeners) listener();
}

/** Current session. Cached, so repeated calls are cheap and stable. */
export function loadSession(): Session | null {
  if (!loaded) {
    snapshot = readStorage();
    loaded = true;
  }
  return snapshot;
}

function onStorage(event: StorageEvent): void {
  // key === null means the whole store was cleared.
  if (event.key === null || event.key === TOKEN_KEY || event.key === USER_KEY) {
    refresh();
  }
}

/** Watch the session. Returns an unsubscribe function. */
export function subscribeToSession(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") {
    // Covers a tab duplicated from this one, which inherits the same
    // sessionStorage and can sign out independently.
    window.addEventListener("storage", onStorage);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

/**
 * Subscribe a component to the session.
 *
 * The server snapshot is always null: the server cannot see
 * sessionStorage, so it renders the signed-out view and the client
 * corrects it on hydration. Returning anything else here would be a
 * hydration mismatch.
 */
export function useSession(): Session | null {
  return useSyncExternalStore(subscribeToSession, loadSession, () => null);
}

export function saveSession(session: Session): void {
  window.sessionStorage.setItem(TOKEN_KEY, session.token);
  window.sessionStorage.setItem(
    USER_KEY,
    JSON.stringify({ username: session.username, role: session.role }),
  );
  refresh();
}

export function clearSession(): void {
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(USER_KEY);
  refresh();
}

export async function login(username: string, password: string): Promise<Session> {
  const body = new URLSearchParams({ username, password });
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    throw new Error(
      response.status === 401 ? "Invalid username or password" : `Login failed (${response.status})`,
    );
  }
  const data = await response.json();
  const session: Session = {
    token: data.access_token,
    username: data.username,
    role: data.role,
  };
  saveSession(session);
  return session;
}

/** Authenticated request against /api/v1; throws on non-2xx. */
export async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = loadSession();
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = body?.error?.message ?? message;
    } catch {
      // keep the status text
    }
    if (response.status === 401) clearSession();
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
