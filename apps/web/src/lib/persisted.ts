"use client";

/** A tiny store that survives a reload, shared by theme, locale and sidebar.
 *
 * All three want the same four things: read a remembered value, write it,
 * tell every subscriber, and stay reference-stable so
 * `useSyncExternalStore` does not loop. Writing that machinery three
 * times is how the three drift apart, so it is written once here.
 *
 * Two storage backends, chosen per preference rather than by taste:
 *
 * - **localStorage** for anything the browser can apply before React
 *   runs. The blocking script in `<head>` reads it and stamps the result
 *   on `<html>`, so the page paints in the right theme the first time.
 * - **cookie** for anything the *server* must know at render time. The
 *   locale is the only one: text comes from React, so the server has to
 *   render the right language or the user sees a frame of the wrong one.
 *
 * Server snapshots are always the supplied default. The server cannot
 * read either store, and returning anything else is a hydration
 * mismatch.
 */

import { useSyncExternalStore } from "react";

export type Backend = "local" | "cookie";

export interface PersistedStore<T extends string> {
  get(): T;
  set(value: T): void;
  subscribe(listener: () => void): () => void;
  /** For `useSyncExternalStore`'s server snapshot. */
  readonly fallback: T;
  readonly key: string;
}

/** A year: these are preferences, not sessions. */
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function readCookie(key: string, source?: string): string | null {
  const jar = source ?? (typeof document === "undefined" ? "" : document.cookie);
  for (const part of jar.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === key) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function writeCookie(key: string, value: string): void {
  // SameSite=Lax so it survives ordinary navigation; not httpOnly,
  // because the client is the one that sets it. Nothing secret goes in
  // a preference cookie.
  document.cookie = `${key}=${encodeURIComponent(value)};path=/;max-age=${COOKIE_MAX_AGE};samesite=lax`;
}

export function createPersistedStore<T extends string>(options: {
  key: string;
  fallback: T;
  allowed: readonly T[];
  backend?: Backend;
  /** Runs after every change, e.g. to stamp `<html>` for the CSS. */
  onChange?: (value: T) => void;
}): PersistedStore<T> {
  const { key, fallback, allowed, backend = "local", onChange } = options;
  const listeners = new Set<() => void>();

  // Cached so repeated reads are cheap *and* identity-stable.
  let current: T | null = null;

  const parse = (raw: string | null): T =>
    raw !== null && (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback;

  const read = (): T => {
    if (typeof window === "undefined") return fallback;
    try {
      return parse(
        backend === "cookie" ? readCookie(key) : window.localStorage.getItem(key),
      );
    } catch {
      // Safari in private mode throws on localStorage. A preference is
      // not worth breaking the page over.
      return fallback;
    }
  };

  const notify = (): void => {
    for (const listener of listeners) listener();
  };

  const store: PersistedStore<T> = {
    key,
    fallback,
    get() {
      if (current === null) current = read();
      return current;
    },
    set(value: T) {
      const next = parse(value);
      if (current === next) return;
      current = next;
      try {
        if (backend === "cookie") writeCookie(key, next);
        else window.localStorage.setItem(key, next);
      } catch {
        // Keep the in-memory value: the choice still applies for this
        // session even when it cannot be remembered for the next one.
      }
      onChange?.(next);
      notify();
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      if (listeners.size === 1 && typeof window !== "undefined" && backend === "local") {
        window.addEventListener("storage", onStorage);
      }
      return () => {
        listeners.delete(listener);
        if (listeners.size === 0 && typeof window !== "undefined" && backend === "local") {
          window.removeEventListener("storage", onStorage);
        }
      };
    },
  };

  // Another tab changing the preference should change this one too.
  function onStorage(event: StorageEvent): void {
    if (event.key !== null && event.key !== key) return;
    const next = read();
    if (next === current) return;
    current = next;
    onChange?.(next);
    notify();
  }

  return store;
}

/** Subscribe a component to a persisted preference. */
export function usePersisted<T extends string>(store: PersistedStore<T>): T {
  return useSyncExternalStore(
    (listener) => store.subscribe(listener),
    () => store.get(),
    () => store.fallback,
  );
}
