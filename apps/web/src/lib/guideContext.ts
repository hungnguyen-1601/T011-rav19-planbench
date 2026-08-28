"use client";

/** The three live facts the guide states, and nothing else.
 *
 * The guide is prose; these are the sentences prose cannot write for
 * itself — which version is running, whether the assistant is answering
 * from a model or from the offline responder, and whether *this* reader
 * may import an algorithm. Writing any of them into an article would
 * make it wrong for somebody.
 *
 * **No new endpoints.** All three already exist and are already read
 * elsewhere: `/health` for the version, `/settings/agent` for the
 * provider — its docstring says outright that whether a model is
 * answering "is a question about the answers on screen, not a
 * privileged one" — and the session for who is reading.
 *
 * **Fail-open, and that is the whole design.** An article must be
 * readable when the API is down, when the reader has not signed in, and
 * on the desktop build before the server has finished starting. Every
 * field therefore has an answer that means "not known", and the callers
 * hide their line rather than blocking the page. A guide that will not
 * render because a version string failed to load is a guide that is
 * missing exactly when somebody is trying to work out what went wrong.
 */

import { useEffect, useState } from "react";

import { api } from "./api";
import { useSession } from "./auth";
import { getAgentSettings } from "./settings";

export interface GuideContext {
  /** Empty when unknown — never a guess, never "unknown" as text. */
  version: string;
  /** A real model is answering. False also covers "we could not ask". */
  aiReady: boolean;
  aiModel: string;
  signedIn: boolean;
  /** Whether this reader may import an algorithm.
   *
   * Today that is `is_admin`, because that is what the server checks
   * (`plugin_service._require_admin`). When the capability packages of
   * `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md` land,
   * this becomes `has("plugin.import")` and **nothing else in the guide
   * changes** — which is the reason no article is allowed to say
   * "administrators only" in its own words.
   */
  canImportPlugin: boolean;
  /** Still asking. Callers show nothing rather than a wrong answer. */
  loading: boolean;
}

export function useGuideContext(): GuideContext {
  const session = useSession();
  const [version, setVersion] = useState("");
  const [aiReady, setAiReady] = useState(false);
  const [aiModel, setAiModel] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // Two independent asks. `Promise.allSettled`, not `all`: the version
    // and the provider are separate facts, and one failing must not
    // erase the other.
    Promise.allSettled([api.health(), getAgentSettings()])
      .then(([health, agent]) => {
        if (cancelled) return;
        if (health.status === "fulfilled") setVersion(health.value.version);
        if (agent.status === "fulfilled") {
          // `deterministic` is the honest flag: a key can be present and
          // the provider still fall back to the offline responder, and
          // saying "connected" then would be a green tick over a keyword
          // matcher.
          setAiReady(agent.value.ready && !agent.value.active_deterministic);
          setAiModel(agent.value.active_model);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Re-ask after a sign-in: `/settings/agent` needs a session, and a
    // cold tab asks before there is one.
  }, [session?.token]);

  return {
    version,
    aiReady,
    aiModel,
    signedIn: Boolean(session),
    canImportPlugin: Boolean(session?.user.is_admin),
    loading,
  };
}
