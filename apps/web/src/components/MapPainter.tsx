"use client";

/** Paint occupancy cells on a grid. One editor, two callers.
 *
 * **Extracted rather than copied, and that is the whole point.** The map
 * editor at `/maps/[id]` has painted cells since Phase 1; the deployment
 * form needs the same thing inline, so somebody can draw a site without
 * leaving the page they are filing it from. Two editors would be two
 * definitions of what painting a map means, free to drift — the same
 * argument that kept the launch panel from growing its own.
 *
 * **Controlled, and it owns nothing but the brush.** The grid comes in
 * and the changed grid goes out; where it was loaded from and where it
 * is saved to belong to the caller. The two callers differ on exactly
 * that: `/maps/[id]` loads by id and PUTs a new version, while the
 * deployment form holds an unsaved grid until the profile is filed. A
 * component that knew about `api.updateMap` could only ever serve the
 * first.
 */

import type { ReactNode } from "react";
import { useCallback, useState } from "react";

import { MapCanvas } from "@/components/MapCanvas";
import { FREE, OCCUPIED, UNKNOWN } from "@/lib/demoMap";
import { useTranslation } from "@/lib/i18n";
import { worldToCell } from "@/lib/transform";
import type { MapData } from "@/lib/types";

export type Brush = "occupied" | "free" | "unknown";

const BRUSH_VALUE: Record<Brush, number> = {
  occupied: OCCUPIED,
  free: FREE,
  unknown: UNKNOWN,
};

export interface MapPainterProps {
  map: MapData;
  onChange: (next: MapData) => void;
  disabled?: boolean;
  /** Caller controls sharing the painter's toolbar row — the save
   *  button on `/maps/[id]`, nothing on the deployment form. Kept in the
   *  same row rather than above it so the page reads as one strip of
   *  tools instead of two competing ones. */
  actions?: ReactNode;
  width?: number;
  height?: number;
}

export function MapPainter({
  map,
  onChange,
  disabled = false,
  actions,
  width,
  height,
}: MapPainterProps) {
  const { t } = useTranslation();
  const [brush, setBrush] = useState<Brush>("occupied");

  const paint = useCallback(
    (x: number, y: number) => {
      if (disabled) return;
      const cell = worldToCell(map, x, y);
      if (!cell) return;
      const index = cell.row * map.width + cell.col;
      const value = BRUSH_VALUE[brush];
      // Nothing to emit when the cell already holds this value. Dragging
      // across a painted area would otherwise fire one update per pixel
      // of travel, and every one of them would mark the caller dirty.
      if (map.cells[index] === value) return;
      const cells = [...map.cells];
      cells[index] = value;
      onChange({ ...map, cells });
    },
    [brush, disabled, map, onChange],
  );

  return (
    <>
      <div className="toolbar">
        <span className="muted">{t("maps.brushLabel")}</span>
        {(["occupied", "free", "unknown"] as Brush[]).map((option) => (
          <button
            key={option}
            type="button"
            disabled={disabled}
            className={brush === option ? "primary" : ""}
            onClick={() => setBrush(option)}
          >
            {t(`maps.brush.${option}`)}
          </button>
        ))}
        {actions}
      </div>

      <MapCanvas
        map={map}
        width={width}
        height={height}
        onWorldClick={paint}
        onWorldDrag={paint}
      />
      <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
        {t("maps.editorHint", {
          width: map.width,
          height: map.height,
          resolution: map.resolution,
          worldWidth: (map.width * map.resolution).toFixed(1),
          worldHeight: (map.height * map.resolution).toFixed(1),
        })}
      </p>
    </>
  );
}
