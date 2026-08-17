"use client";

/** Token storage, the session store, and the authenticated fetch wrapper.
 *
 * The token lives in sessionStorage: it disappears when the tab closes
 * and is never written to a cookie, so there is no CSRF surface. The
 * OAuth *state* cookie the backend sets is a different thing entirely —
 * httpOnly, short-lived, and never read here.
 *
 * Nothing about a provider is stored: no provider access token, no
 * client id, no secret. The browser trades a one-time code for a
 * PlanBench JWT and keeps only that.
 *
 * The session is exposed as a subscribable store rather than a plain
 * read. Reading it once per component was wrong in a way that only
 * showed up in the sidebar: `SessionBar` lives in the root layout, so it
 * mounts once for the life of the tab. A one-shot read in `useEffect`
 * captured "signed out" before the user ever logged in, and no
 * client-side navigation ever remounted it to correct that.
 */

import { useSyncExternalStore } from "react";
import { API_BASE } from "./api";

const TOKEN_KEY = "planbench.token";
const USER_KEY = "planbench.user";

/** The signed-in account, as the API describes it.
 *
 * `id` is the identity; `nickname` is how other people find them. The
 * frontend never sends either as proof of anything — the bearer token
 * is the only credential — so this is display state.
 */
export interface SessionUser {
  id: string;
  nickname: string;
  email: string;
  display_name: string;
  avatar_url: string;
  is_admin: boolean;
  needs_nickname: boolean;
  providers: string[];
}

export interface Session {
  token: string;
  user: SessionUser;
}

/** Which sign-in methods this deployment offers. */
export interface AuthProviders {
  google: boolean;
  github: boolean;
  dev_login: boolean;
}

const listeners = new Set<() => void>();

// `useSyncExternalStore` compares snapshots by identity, so this must be
// a stable reference: rebuilding the object on every read would loop
// forever. It is replaced only when the stored value actually changes.
let snapshot: Session | null = null;
let loaded = false;

function normaliseUser(raw: Partial<SessionUser> | null): SessionUser | null {
  if (!raw || typeof raw.id !== "string" || !raw.id) return null;
  return {
    id: raw.id,
    nickname: raw.nickname ?? "",
    email: raw.email ?? "",
    display_name: raw.display_name ?? "",
    avatar_url: raw.avatar_url ?? "",
    is_admin: raw.is_admin ?? false,
    needs_nickname: raw.needs_nickname ?? !raw.nickname,
    providers: raw.providers ?? [],
  };
}

function readStorage(): Session | null {
  if (typeof window === "undefined") return null;
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  const raw = window.sessionStorage.getItem(USER_KEY);
  if (!token || !raw) return null;
  try {
    const user = normaliseUser(JSON.parse(raw));
    return user ? { token, user } : null;
  } catch {
    // A corrupted entry is treated as no session rather than crashing
    // the whole layout.
    return null;
  }
}

function same(a: Session | null, b: Session | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return (
    a.token === b.token &&
    a.user.id === b.user.id &&
    a.user.nickname === b.user.nickname &&
    a.user.needs_nickname === b.user.needs_nickname &&
    a.user.avatar_url === b.user.avatar_url &&
    a.user.email === b.user.email &&
    a.user.is_admin === b.user.is_admin &&
    a.user.providers.join(",") === b.user.providers.join(",")
  );
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
  // The token is deliberately not duplicated into the user record: one
  // place owns it, so the two copies cannot disagree.
  window.sessionStorage.setItem(USER_KEY, JSON.stringify(session.user));
  refresh();
}

/** Replace the stored profile, keeping the current token.
 *
 * Used after choosing a nickname or linking a provider: the token is
 * still valid, and re-authenticating just to see a new display name
 * would send the user back through the provider for nothing.
 */
export function updateSessionUser(user: SessionUser): void {
  const current = loadSession();
  if (!current) return;
  saveSession({ token: current.token, user });
}

export function clearSession(): void {
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(USER_KEY);
  refresh();
}

interface TokenResponse {
  access_token: string;
  user: SessionUser;
}

function sessionFrom(data: TokenResponse): Session {
  const user = normaliseUser(data.user);
  if (!user) throw new Error("the server returned an unrecognisable account");
  const session: Session = { token: data.access_token, user };
  saveSession(session);
  return session;
}

/** A refusal that says which fields it is about.
 *
 * The sentence is still the message, so every existing catcher keeps
 * working unchanged. `details` is what a form needs on top of it: one
 * blob saying "2 validation errors for TaskProfile" leaves the reader to
 * find which two among thirty inputs.
 */
export class FieldError extends Error {
  constructor(
    message: string,
    public details: { path: string; message: string }[],
    /** Everything in `error.details` that was not field-shaped.
     *
     * The server's `details` is a list of *whatever the refusal needs a
     * caller to act on* — sentences and field addresses for a form, and
     * counts for a confirmation dialog ("delete 7 runs, 2 approved?").
     * Filtering to the field shape and dropping the rest silently is
     * what made the first version of the delete dialog have nothing to
     * count with. Kept separate so `fieldErrorsOf` stays exactly as
     * narrow as a form needs.
     */
    public raw: unknown[] = [],
  ) {
    super(message);
    this.name = "FieldError";
  }
}

/** The addressed complaints on a thrown error, or none. */
export function fieldErrorsOf(caught: unknown): { path: string; message: string }[] {
  return caught instanceof FieldError ? caught.details : [];
}

async function errorBody(
  response: Response,
  fallback: string,
): Promise<{
  message: string;
  details: { path: string; message: string }[];
  raw: unknown[];
}> {
  try {
    const body = await response.json();
    const raw: unknown[] = Array.isArray(body?.error?.details) ? body.error.details : [];
    const details = raw.filter(
      (entry): entry is { path: string; message: string } =>
        entry !== null &&
        typeof entry === "object" &&
        typeof (entry as { path?: unknown }).path === "string" &&
        typeof (entry as { message?: unknown }).message === "string",
    );
    return { message: body?.error?.message ?? fallback, details, raw };
  } catch {
    return { message: fallback, details: [], raw: [] };
  }
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  return (await errorBody(response, fallback)).message;
}

/** Which sign-in methods the backend actually offers. */
export async function fetchAuthProviders(): Promise<AuthProviders> {
  const response = await fetch(`${API_BASE}/api/v1/auth/providers`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not reach the API (${response.status})`);
  return (await response.json()) as AuthProviders;
}

/** Where to send the browser to sign in with a provider. */
export function oauthStartUrl(provider: "google" | "github"): string {
  return `${API_BASE}/api/v1/auth/oauth/${provider}/start`;
}

/** Trade the one-time callback code for a session. */
export async function exchangeOAuthCode(code: string): Promise<Session> {
  const response = await fetch(`${API_BASE}/api/v1/auth/oauth/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "This sign-in link is no longer valid."));
  }
  return sessionFrom((await response.json()) as TokenResponse);
}

/** Development password sign-in. Only offered when the API enables it. */
export async function login(username: string, password: string): Promise<Session> {
  const body = new URLSearchParams({ username, password });
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    const fallback =
      response.status === 401
        ? "Invalid username or password"
        : `Login failed (${response.status})`;
    throw new Error(await errorMessage(response, fallback));
  }
  return sessionFrom((await response.json()) as TokenResponse);
}

/** Authenticated request against /api/v1; throws on non-2xx. */
export async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = loadSession();
  // A `FormData` body must set its own Content-Type, because only the
  // browser knows the multipart boundary it generated. Naming JSON here
  // would produce a request the server cannot parse.
  const multipart = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      ...(multipart ? {} : { "Content-Type": "application/json" }),
      ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const { message, details, raw } = await errorBody(response, response.statusText);
    if (response.status === 401) clearSession();
    // Always a `FieldError`, even with no details: one type of refusal
    // is easier to reason about than two, and `details` being empty is
    // the honest answer for an error nobody addressed.
    throw new FieldError(message, details, raw);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
