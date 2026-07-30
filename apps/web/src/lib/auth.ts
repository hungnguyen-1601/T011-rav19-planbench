"use client";

/** Token storage and the authenticated fetch wrapper.
 *
 * The token lives in sessionStorage: it disappears when the tab closes
 * and is never written to a cookie, so there is no CSRF surface.
 */

import { API_BASE } from "./api";

const TOKEN_KEY = "planbench.token";
const USER_KEY = "planbench.user";

export interface Session {
  token: string;
  username: string;
  role: "operator" | "reviewer" | "admin";
}

export function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  const raw = window.sessionStorage.getItem(USER_KEY);
  if (!token || !raw) return null;
  try {
    const user = JSON.parse(raw) as { username: string; role: Session["role"] };
    return { token, ...user };
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  window.sessionStorage.setItem(TOKEN_KEY, session.token);
  window.sessionStorage.setItem(
    USER_KEY,
    JSON.stringify({ username: session.username, role: session.role }),
  );
}

export function clearSession(): void {
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(USER_KEY);
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
