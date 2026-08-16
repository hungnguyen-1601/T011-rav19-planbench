import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton, PanelSkeleton, LoadingState } from "@/components/LoadingSkeleton";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const APP_DIR = join(__dirname, "..");
const COMPONENTS_DIR = join(__dirname, "..", "..", "components");

describe("Disabled, Loading, and Empty State Standardization", () => {
  describe("1. EmptyState Component Dual CTAs", () => {
    it("renders primary and secondary CTA links when provided", () => {
      const html = renderToStaticMarkup(
        <EmptyState
          icon="map"
          title="No maps found"
          body="Create a map or import from scenario library."
          actionHref="/maps"
          actionLabel="Create map"
          secondaryActionHref="/library"
          secondaryActionLabel="Open scenario library"
        />,
      );

      expect(html).toContain("No maps found");
      expect(html).toContain('href="/maps"');
      expect(html).toContain("Create map");
      expect(html).toContain('href="/library"');
      expect(html).toContain("Open scenario library");
    });
  });

  describe("2. LoadingSkeleton Components & Accessibility", () => {
    it("renders TableSkeleton with aria-busy and status role", () => {
      const html = renderToStaticMarkup(<TableSkeleton rows={3} columns={4} />);
      expect(html).toContain('role="status"');
      expect(html).toContain('aria-busy="true"');
      expect(html).toContain("skeleton");
    });

    it("renders PanelSkeleton with aria-busy and status role", () => {
      const html = renderToStaticMarkup(<PanelSkeleton height={150} />);
      expect(html).toContain('role="status"');
      expect(html).toContain('aria-busy="true"');
      expect(html).toContain("skeleton");
    });

    it("renders LoadingState with spinner and text", () => {
      const html = renderToStaticMarkup(<LoadingState message="Processing simulation..." />);
      expect(html).toContain('role="status"');
      expect(html).toContain('aria-busy="true"');
      expect(html).toContain("spinner");
      expect(html).toContain("Processing simulation...");
    });
  });

  describe("3. Code Audit for Tooltip Explanations on Disabled Buttons", () => {
    it("includes title tooltip explaining why Run Simulation button is disabled in simulate page", () => {
      const content = readFileSync(join(APP_DIR, "simulate", "page.tsx"), "utf8");
      expect(content).toContain("disabled={busy || !map}");
      expect(content).toContain("title={!map ? t(");
    });

    it("includes title tooltip explaining why Save Scenario button is disabled in scenarios editor", () => {
      const content = readFileSync(join(APP_DIR, "scenarios", "[id]", "page.tsx"), "utf8");
      expect(content).toContain("disabled={!canEdit || busy || !mapId || !draft.name}");
      expect(content).toContain("title={");
    });

    it("includes title tooltip explaining why Create Draft button is disabled in benchmarks page", () => {
      const content = readFileSync(join(APP_DIR, "benchmarks", "page.tsx"), "utf8");
      expect(content).toContain('selected.includes("astar+ppo") && !modelId');
      expect(content).toContain('title={');
    });

    it("includes title tooltip on ModelUpload primary button", () => {
      const content = readFileSync(join(COMPONENTS_DIR, "ModelUpload.tsx"), "utf8");
      expect(content).toContain("disabled={!ready}");
      expect(content).toContain("title={");
    });
  });
});
