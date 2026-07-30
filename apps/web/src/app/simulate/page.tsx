"use client";

/** Live simulation page: pick a map, set start/goal, run, watch, inspect. */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MapCanvas } from "@/components/MapCanvas";
import { MetricsPanel } from "@/components/MetricsPanel";
import { api } from "@/lib/api";
import { defaultScenario } from "@/lib/demoMap";
import { useEpisodeStream } from "@/lib/useEpisodeStream";
import type { MapData, MapSummary, PlanResult, Point2D, Scenario } from "@/lib/types";

type PlaceMode = "start" | "goal" | "none";

export default function SimulatePage() {
  const [maps, setMaps] = useState<MapSummary[]>([]);
  const [mapId, setMapId] = useState<string>("");
  const [map, setMap] = useState<MapData | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [placeMode, setPlaceMode] = useState<PlaceMode>("start");
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showPlan, setShowPlan] = useState(true);
  const [showTrajectory, setShowTrajectory] = useState(true);

  const stream = useEpisodeStream();

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listMaps();
        setMaps(list);
        if (list.length > 0) setMapId((current) => current || list[0].id);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  useEffect(() => {
    if (!mapId) return;
    let cancelled = false;
    (async () => {
      try {
        const resource = await api.getMap(mapId);
        if (cancelled) return;
        setMap(resource.map_data);
        setScenario(defaultScenario(resource.map_data));
        setPlan(null);
        stream.reset();
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
    // stream identity changes every render; only re-fetch when the map changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapId]);

  const placePose = useCallback(
    (x: number, y: number) => {
      if (placeMode === "none") return;
      setScenario((current) => {
        if (!current) return current;
        const pose = { x: Number(x.toFixed(3)), y: Number(y.toFixed(3)), theta: 0 };
        return placeMode === "start"
          ? { ...current, start_pose: pose }
          : { ...current, goal_pose: pose };
      });
    },
    [placeMode],
  );

  const run = async () => {
    if (!map || !scenario || !mapId) return;
    setBusy(true);
    setError(null);
    setPlan(null);
    try {
      const scenarioResource = await api.createScenario(mapId, {
        ...scenario,
        name: `${scenario.name}-${Date.now()}`,
      });
      const simulation = await api.createSimulation(mapId, scenarioResource.id);
      const result = await api.runSimulation(simulation.id);
      setPlan(result.plan);
      if (result.result && result.result.trajectory.length > 0) {
        stream.connect(simulation.id);
      } else {
        setError(
          result.plan && !result.plan.success
            ? `No global path: ${result.plan.failure_reason}`
            : "Episode produced no trajectory",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const visibleTrajectory = useMemo(() => {
    if (!showTrajectory) return [];
    const upto = stream.frames.filter((frame) => frame.time <= stream.playhead + 1e-9);
    return upto.length > 0 ? upto : stream.frames.slice(0, 1);
  }, [stream.frames, stream.playhead, showTrajectory]);

  const collisionPoint: Point2D | null =
    stream.status === "collision" && stream.frames.length > 0
      ? { x: stream.frames[stream.frames.length - 1].x, y: stream.frames[stream.frames.length - 1].y }
      : null;

  const robotPose = stream.currentFrame
    ? {
        x: stream.currentFrame.x,
        y: stream.currentFrame.y,
        theta: stream.currentFrame.theta,
      }
    : (scenario?.start_pose ?? null);

  return (
    <>
      <h2>Live Simulation</h2>
      {error ? <div className="error-box">{error}</div> : null}
      {stream.error ? <div className="error-box">Stream: {stream.error}</div> : null}

      {maps.length === 0 ? (
        <div className="panel">
          <p className="muted">
            No maps available. Create one on the <Link href="/maps">Maps</Link> page first.
          </p>
        </div>
      ) : null}

      <div className="toolbar">
        <label className="inline">
          Map:
          <select value={mapId} onChange={(event) => setMapId(event.target.value)}>
            {maps.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">|</span>
        <span className="muted">Click to place:</span>
        {(["start", "goal", "none"] as PlaceMode[]).map((mode) => (
          <button
            key={mode}
            className={placeMode === mode ? "primary" : ""}
            onClick={() => setPlaceMode(mode)}
          >
            {mode}
          </button>
        ))}
        <span className="muted">|</span>
        <button className="primary" disabled={busy || !map} onClick={() => void run()}>
          {busy ? "Running…" : "Run simulation"}
        </button>
      </div>

      <div className="toolbar">
        <button onClick={stream.play} disabled={stream.frames.length === 0 || stream.playing}>
          Play
        </button>
        <button onClick={stream.pause} disabled={!stream.playing}>
          Pause
        </button>
        <button onClick={stream.stop} disabled={stream.phase === "idle"}>
          Stop
        </button>
        <button onClick={stream.reset} disabled={stream.frames.length === 0}>
          Reset
        </button>
        <label className="inline">
          Speed:
          <select
            value={stream.speed}
            onChange={(event) => stream.setSpeed(Number(event.target.value))}
          >
            {[0.25, 0.5, 1, 2, 4, 8].map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
        </label>
        <input
          type="range"
          min={0}
          max={Math.max(stream.duration, 0.001)}
          step={0.01}
          value={stream.playhead}
          onChange={(event) => stream.seek(Number(event.target.value))}
          style={{ flex: 1, minWidth: 160 }}
          aria-label="Playback timeline"
        />
        <span className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
          {stream.playhead.toFixed(2)} / {stream.duration.toFixed(2)} s
        </span>
      </div>

      <div className="toolbar">
        <label className="inline">
          <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
          Grid
        </label>
        <label className="inline">
          <input type="checkbox" checked={showPlan} onChange={(e) => setShowPlan(e.target.checked)} />
          Global path
        </label>
        <label className="inline">
          <input
            type="checkbox"
            checked={showTrajectory}
            onChange={(e) => setShowTrajectory(e.target.checked)}
          />
          Actual trajectory
        </label>
        {stream.status ? (
          <span className={`badge ${stream.status === "success" ? "ok" : "err"}`}>
            {stream.status}
          </span>
        ) : null}
        {stream.reason ? <span className="muted">{stream.reason}</span> : null}
      </div>

      <div className="row">
        <div className="panel" style={{ flex: "1 1 auto" }}>
          {map ? (
            <MapCanvas
              map={map}
              startPose={scenario?.start_pose}
              goalPose={scenario?.goal_pose}
              goalTolerance={scenario?.goal_tolerance}
              robotRadius={scenario?.robot.radius}
              plannedPath={stream.planPath.length > 0 ? stream.planPath : plan?.path}
              trajectory={visibleTrajectory}
              robotPose={robotPose}
              collisionPoint={collisionPoint}
              showGrid={showGrid}
              showPlan={showPlan}
              showTrajectory={showTrajectory}
              onWorldClick={placePose}
            />
          ) : (
            <p className="muted">Select a map.</p>
          )}
        </div>

        <div style={{ flex: "0 0 300px", minWidth: 280 }}>
          <div className="panel">
            <h3>Scenario</h3>
            {scenario ? (
              <table>
                <tbody>
                  <tr>
                    <td className="muted">Start</td>
                    <td>
                      {scenario.start_pose.x.toFixed(2)}, {scenario.start_pose.y.toFixed(2)} m
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">Goal</td>
                    <td>
                      {scenario.goal_pose.x.toFixed(2)}, {scenario.goal_pose.y.toFixed(2)} m
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">Robot radius</td>
                    <td>{scenario.robot.radius} m</td>
                  </tr>
                  <tr>
                    <td className="muted">Max speed</td>
                    <td>{scenario.robot.max_linear_velocity} m/s</td>
                  </tr>
                  <tr>
                    <td className="muted">Timeout</td>
                    <td>{scenario.timeout_seconds} s</td>
                  </tr>
                  <tr>
                    <td className="muted">dt</td>
                    <td>{scenario.simulation_dt} s</td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p className="muted">—</p>
            )}
          </div>

          <div className="panel">
            <h3>Robot state</h3>
            {stream.currentFrame ? (
              <table>
                <tbody>
                  <tr>
                    <td className="muted">t</td>
                    <td>{stream.currentFrame.time.toFixed(2)} s</td>
                  </tr>
                  <tr>
                    <td className="muted">pose</td>
                    <td>
                      {stream.currentFrame.x.toFixed(2)}, {stream.currentFrame.y.toFixed(2)},{" "}
                      {stream.currentFrame.theta.toFixed(2)} rad
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">v</td>
                    <td>{stream.currentFrame.linear_velocity.toFixed(2)} m/s</td>
                  </tr>
                  <tr>
                    <td className="muted">ω</td>
                    <td>{stream.currentFrame.angular_velocity.toFixed(2)} rad/s</td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p className="muted">No episode streamed yet.</p>
            )}
          </div>
        </div>
      </div>

      <MetricsPanel metrics={stream.metrics} plan={plan} />
    </>
  );
}
