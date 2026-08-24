/** REST client for the PlanBench backend. */

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

/**
 * Where the backend is.
 *
 * `NEXT_PUBLIC_API_URL` still wins and is still baked in at build time —
 * Docker passes it as a build arg, `scripts/dev_stack.sh` exports it,
 * and `.env.development` sets it for `next dev`, so none of those change
 * behaviour.
 *
 * The fallback is the page's own origin rather than a fixed port,
 * because the desktop build has no fixed port: the API picks a free one
 * at startup and serves the exported UI from the same process, so the
 * origin the page was loaded from *is* the API. Falling back to a
 * literal `localhost:8000` there would send every request to whatever
 * happened to be on 8000, or to nothing.
 *
 * `window` is guarded because this module is also evaluated while the
 * export is being prerendered, in Node, where there is no location — and
 * nothing fetches during a prerender, so the value used there only has
 * to be a legal URL.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");

/** Socket URL. `pace=false` asks the server for every frame without
 *  server-side throttling — the client owns playback timing.
 *
 *  Derived from `API_BASE`, so `https://` origins give `wss://` and the
 *  desktop build's own origin gives `ws://` on the port it picked. */
export function wsUrl(simulationId: string, pace = false): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/simulations/${simulationId}?pace=${pace}`;
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
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
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
