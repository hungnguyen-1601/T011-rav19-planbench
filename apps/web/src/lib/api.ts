"use client";

/** REST client for the PlanBench backend.
 *
 * **Every request carries the session token.** It did not always: this
 * client predates accounts, and when reading was opened to anybody the
 * absence of a header was invisible. Closing the routes made it visible
 * all at once, as `missing bearer token` on six pages. There is no such
 * thing here as a call that does not need an identity — `/health` is
 * reached directly, not through this module — so the header is attached
 * in one place rather than passed in by fourteen callers who would each
 * have to remember.
 *
 * `authFetch` in `auth.ts` does the same for the newer modules. The two
 * exist because they answer errors differently: this one throws
 * `ApiError`, which its callers switch on by `code`. Merging them is a
 * separate change from making them agree about credentials.
 */

import { clearSession, loadSession } from "./auth";
import { API_BASE } from "./origin";

import type {
  MapData,
  MapResource,
  MapSummary,
  Scenario,
  ScenarioResource,
  SimulationResource,
  SimulationResultResponse,
} from "./types";
import type { ReplanningConfig } from "./benchmarkTypes";

/** Re-exported so the twenty-odd `from "@/lib/api"` imports keep working.
 *
 * The value moved to `origin.ts` because `auth.ts` needs it and this
 * module now needs `auth.ts`; see that file for why the two must not
 * import each other. */
export { API_BASE } from "./origin";

interface Ticket {
  ticket: string;
  expires_in: number;
}

/** Socket URL, with a freshly minted ticket in it.
 *
 * **Asynchronous because a browser cannot put a header on a
 * `WebSocket`.** The server therefore takes a one-minute, single-use
 * ticket in the query string instead, traded for the bearer token on an
 * ordinary authenticated request — so a log line that captured the URL
 * is describing something already spent, rather than a credential good
 * for the next hour.
 *
 * Minted per connection rather than cached: a ticket is consumed on
 * connect, so a reconnect needs a new one, and one held from a previous
 * page load is a minute old at best.
 *
 * `pace=false` asks the server for every frame without throttling — the
 * client owns playback timing. Derived from `API_BASE`, so `https://`
 * origins give `wss://` and the desktop build's own origin gives `ws://`
 * on the port it picked.
 */
export async function wsUrl(simulationId: string, pace = false): Promise<string> {
  const { ticket } = await request<Ticket>("/ws/tickets", { method: "POST" });
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/simulations/${simulationId}?pace=${pace}&ticket=${encodeURIComponent(ticket)}`;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = loadSession();
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // Read per request, not captured at module scope: a page that was
      // open across a sign-out would otherwise keep sending a token the
      // server has stopped honouring.
      ...(session ? { Authorization: `Bearer ${session.token}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    // A 401 means the stored session is no longer good — expired, or
    // signed out in another tab. Dropping it here is what moves the UI
    // to the signed-out state; leaving it would show a signed-in header
    // above a page that can load nothing. Same rule as `authFetch`.
    if (response.status === 401) clearSession();
    let code = "unknown";
    let message = response.statusText;
    try {
      const body = await response.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      // non-JSON error body: keep the status text
    }
    throw new ApiError(response.status, code, message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; app: string; version: string }>("/health"),
  listMaps: () => request<MapSummary[]>("/maps"),
  getMap: (id: string) => request<MapResource>(`/maps/${id}`),
  createMap: (map: MapData) =>
    request<MapResource>("/maps", { method: "POST", body: JSON.stringify(map) }),
  updateMap: (id: string, map: MapData) =>
    request<MapResource>(`/maps/${id}`, { method: "PUT", body: JSON.stringify(map) }),
  deleteMap: (id: string) => request<void>(`/maps/${id}`, { method: "DELETE" }),
  listScenarios: () => request<ScenarioResource[]>("/scenarios"),
  createScenario: (mapId: string, scenario: Scenario) =>
    request<ScenarioResource>("/scenarios", {
      method: "POST",
      body: JSON.stringify({ map_id: mapId, scenario }),
    }),
  createSimulation: (mapId: string, scenarioId: string, replanning?: ReplanningConfig) =>
    request<SimulationResource>("/simulations", {
      method: "POST",
      // Omitted rather than sent as disabled when the caller does not
      // care: the server's default is off, and a payload that never
      // mentions replanning cannot turn it on by accident.
      body: JSON.stringify({
        map_id: mapId,
        scenario_id: scenarioId,
        ...(replanning?.enabled ? { replanning } : {}),
      }),
    }),
  listSimulations: () => request<SimulationResource[]>("/simulations"),
  getSimulation: (id: string) => request<SimulationResource>(`/simulations/${id}`),
  runSimulation: (id: string) =>
    request<SimulationResultResponse>(`/simulations/${id}/run`, { method: "POST" }),
  getSimulationResult: (id: string) =>
    request<SimulationResultResponse>(`/simulations/${id}/result`),
};
