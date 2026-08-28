"use client";

/** Says out loud when this deployment is running under relaxed rules.
 *
 * Two states are worth a permanent line across the top, and neither is
 * an error:
 *
 * - **relaxed duties** — one account may both run a comparison and sign
 *   it off. Legitimate on a single-person install and meaningless
 *   anywhere else, so a person looking at an approval needs to know
 *   which kind of deployment produced it *before* they read the name on
 *   it.
 * - **demo** — one account holds every capability. Same reasoning,
 *   louder, and not dismissible: the whole risk of a demonstration
 *   machine is somebody mistaking it for the product as it ships.
 *
 * Read from the server rather than from the build. The same bundle runs
 * in all three profiles, so a compile-time answer would be a guess about
 * where it ended up.
 */

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

interface DeploymentState {
  profile: string;
  separation_of_duties: string;
}

export function DeploymentBanner() {
  const { t } = useTranslation();
  const [state, setState] = useState<DeploymentState | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/health`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (!cancelled && body?.deployment) setState(body.deployment);
      })
      // Silence is the right failure here. The banner is context, and a
      // deployment whose health endpoint is unreachable has a louder
      // problem than a missing strip of colour.
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!state) return null;
  const demo = state.profile === "demo";
  if (!demo && state.separation_of_duties !== "relaxed") return null;

  return (
    <div
      className={`deployment-banner ${demo ? "deployment-banner-demo" : ""}`}
      role="status"
      data-profile={state.profile}
    >
      <strong>{t(demo ? "deployment.demo.title" : "deployment.relaxed.title")}</strong>{" "}
      <span>{t(demo ? "deployment.demo.body" : "deployment.relaxed.body")}</span>
    </div>
  );
}
